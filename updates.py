"""Manual, read-only checks against this project's public GitHub Releases."""
import json
import re
import hashlib
import tempfile
import threading
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.parse import urlsplit

from PySide6.QtCore import QObject,QTimer,QUrl,Signal
from PySide6.QtNetwork import QNetworkAccessManager,QNetworkReply,QNetworkRequest

REPOSITORY='Able1337/LisaMacroMagic'
API_URL=f'https://api.github.com/repos/{REPOSITORY}/releases/latest'
RELEASE_URL=f'https://github.com/{REPOSITORY}/releases/tag/'
MAX_BYTES=256*1024


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
    name=f'LisaMacroMagic_v{tag.removeprefix("v")}.exe'
    assets=data.get('assets')
    if not isinstance(assets,list): raise ValueError('Missing assets')
    for asset in assets:
        if not isinstance(asset,dict) or asset.get('name')!=name or asset.get('state')!='uploaded': continue
        digest=asset.get('digest'); size=asset.get('size')
        if isinstance(digest,str) and re.fullmatch(r'sha256:[0-9a-f]{64}',digest) and type(size) is int and 0<size<=150*1024*1024:
            return tag.removeprefix('v'),f'https://github.com/{REPOSITORY}/releases/download/{tag}/{name}',digest[7:],size
    raise ValueError('Нет проверяемого EXE для релиза.')


class UpdateCheck(QObject):
    finished=Signal(object,str)
    downloaded=Signal(object,str)

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
        def run():
            stage=None
            try:
                _,url,digest,size=release
                stage=Path(tempfile.mkdtemp(prefix='.lisa-update-',dir=target.parent))
                request=Request(url,headers={'User-Agent':'LisaMacroMagic/'+self.current})
                with urlopen(request,timeout=12) as response, (stage/'ready.exe').open('wb') as out:
                    endpoint=urlsplit(response.geturl())
                    if endpoint.scheme!='https' or endpoint.hostname not in {'github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:
                        raise ValueError('Неожиданный адрес загрузки.')
                    checksum=hashlib.sha256(); count=0
                    while chunk:=response.read(256*1024):
                        count+=len(chunk)
                        if count>size: raise ValueError('Размер файла не совпадает с релизом.')
                        checksum.update(chunk); out.write(chunk)
                if count!=size or checksum.hexdigest()!=digest:
                    raise ValueError('Контрольная сумма не совпадает с релизом.')
                self.downloaded.emit(stage,'')
            except Exception as exc:
                if stage:
                    try: (stage/'ready.exe').unlink(missing_ok=True); stage.rmdir()
                    except OSError: pass
                self.downloaded.emit(None,str(exc))
        threading.Thread(target=run,daemon=True).start()
