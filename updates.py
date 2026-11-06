"""Manual, read-only checks against this project's public GitHub Releases."""
import json
import re
import hashlib
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject,QTimer,QUrl,Signal
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkReply,QNetworkRequest

REPOSITORY='Able1337/LisaMacroMagic'
API_URL=f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASE_URL=f'https://github.com/{REPOSITORY}/releases/tag/'
MAX_BYTES=256*1024
DOWNLOAD_HOSTS={'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}


def trusted_download(url):
    return (url.isValid() and url.scheme()=='https' and url.host() in DOWNLOAD_HOSTS
            and url.port(443)==443 and not url.userInfo())


def version(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?[0-9]{1,6}\.[0-9]{1,6}\.[0-9]{1,6}',value):
        raise ValueError('Не удалось прочитать версию релиза GitHub.')
    return tuple(map(int,value.removeprefix('v').split('.')))


def available_release(body,current):
    data=json.loads(body)
    if not isinstance(data,dict) or data.get('draft') is not False or data.get('prerelease') is not False:
        raise ValueError('Ответ GitHub не содержит стабильного релиза.')
    tag=data.get('tag_name')
    if version(tag)<=version(current): return None
    names=('LisaMacroMagic.exe',f'LisaMacroMagic_v{tag.removeprefix("v")}.exe')
    assets=data.get('assets')
    if not isinstance(assets,list): raise ValueError('Missing assets')
    for name in names:
        for asset in assets:
            if not isinstance(asset,dict) or asset.get('name')!=name or asset.get('state')!='uploaded': continue
            digest=asset.get('digest'); size=asset.get('size')
            if isinstance(digest,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',digest) and type(size) is int and 0<size<=150*1024*1024:
                return tag.removeprefix('v'),f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}',digest[7:],size
    raise ValueError('Нет проверяемого EXE для релиза.')


class UpdateCheck(QObject):
    finished=Signal(object,str)
    downloaded=Signal(object,str)
    progress=Signal(int,int)

    def __init__(self,current,parent=None):
        super().__init__(parent)
        self.current=current
        self.network=QNetworkAccessManager(self)
        self.reply=None

    def check(self):
        if self.reply is not None: return
        request=QNetworkRequest(QUrl(API_URL))
        request.setRawHeader(b'Accept',b'application/vnd.github+json')
        request.setRawHeader(b'User-Agent',b'LisaMacroMagic/'+self.current.encode('ascii'))
        request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
        reply=self.reply=self.network.get(request)
        timer=QTimer(reply); timer.setSingleShot(True); timer.timeout.connect(reply.abort); timer.start(8000)
        reply.downloadProgress.connect(lambda received,total: reply.abort() if received>MAX_BYTES or total>MAX_BYTES else None)
        reply.finished.connect(lambda:self.complete(reply))

    def complete(self,reply):
        self.reply=None
        status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
        result=(None,'Не удалось проверить обновления. Проверь соединение и попробуй ещё раз.')
        try:
            if status==404:
                result=(None,'На GitHub пока нет опубликованного релиза.')
            elif status==200 and reply.error()==QNetworkReply.NetworkError.NoError:
                body=bytes(reply.read(MAX_BYTES+1))
                if len(body)>MAX_BYTES: raise ValueError('Ответ GitHub слишком большой.')
                release=available_release(body,self.current)
                result=(release,f'Доступна версия {release[0]} ♡') if release else (None,'У тебя актуальная версия ♡')
        except (ValueError,UnicodeError):
            result=(None,'Не удалось проверить EXE опубликованного релиза.')
        finally:
            reply.deleteLater()
        self.finished.emit(*result)

    def download(self,release,target):
        _,url,digest,size=release
        stage=None
        try:
            stage=Path(tempfile.mkdtemp(prefix='.lisa-update-',dir=target.parent))
            out=(stage/'ready.exe').open('xb')
        except OSError as exc:
            if stage:
                try: stage.rmdir()
                except OSError: pass
            self.downloaded.emit(None,f'Не удалось подготовить файл рядом с EXE: {exc}')
            return
        checksum=hashlib.sha256()
        count=0
        error=''

        def finish(message=''):
            try: out.close()
            except OSError as exc: message=message or f'Ошибка записи файла: {exc}'
            if message:
                try: (stage/'ready.exe').unlink(missing_ok=True); stage.rmdir()
                except OSError: pass
            self.downloaded.emit(None if message else stage,message)

        def get(endpoint,redirects=0):
            nonlocal error
            if redirects>5 or not trusted_download(endpoint):
                finish('GitHub перенаправил загрузку на неожиданный адрес.'); return
            request=QNetworkRequest(endpoint)
            request.setRawHeader(b'User-Agent',b'LisaMacroMagic/'+self.current.encode('ascii'))
            request.setAttribute(QNetworkRequest.Attribute.RedirectPolicyAttribute,QNetworkRequest.RedirectPolicy.ManualRedirectPolicy)
            reply=self.network.get(request)
            timer=QTimer(reply); timer.setSingleShot(True); timer.timeout.connect(reply.abort); timer.start(120000)

            def read(abort=True):
                nonlocal count,error
                status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                if status!=200 or error:
                    reply.readAll(); return
                while reply.bytesAvailable():
                    chunk=bytes(reply.read(256*1024))
                    if not chunk: break
                    count+=len(chunk)
                    if count>size:
                        error='Размер файла не совпадает с релизом.'
                        if abort: reply.abort()
                        return
                    try: out.write(chunk)
                    except OSError as exc:
                        error=f'Ошибка записи файла: {exc}'
                        if abort: reply.abort()
                        return
                    checksum.update(chunk)
                self.progress.emit(count,size)

            def completed():
                timer.stop()
                status=reply.attribute(QNetworkRequest.Attribute.HttpStatusCodeAttribute)
                redirect=reply.attribute(QNetworkRequest.Attribute.RedirectionTargetAttribute)
                reply.deleteLater()
                if error: finish(error); return
                if status in (301,302,303,307,308) and isinstance(redirect,QUrl):
                    get(endpoint.resolved(redirect),redirects+1); return
                if status!=200 or reply.error()!=QNetworkReply.NetworkError.NoError:
                    finish(f'Не удалось загрузить EXE с GitHub ({status or "сеть"}): {reply.errorString()}'); return
                read(False)
                finish(error or ('Контрольная сумма или размер не совпадают с релизом.'
                                  if count!=size or checksum.hexdigest()!=digest else ''))

            reply.readyRead.connect(read)
            reply.finished.connect(completed)

        get(QUrl(url))
