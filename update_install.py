"""Separate helper process for replacing a closed Windows one-file executable."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import tempfile

EXE_NAME='LisaMacroMagic.exe'


def destination_for(target):
    destination=target.with_name(EXE_NAME)
    if destination!=target and os.path.lexists(destination):
        raise FileExistsError(f'Файл {EXE_NAME} уже существует рядом с текущим EXE. Он не был заменён.')
    return destination


def launch(path,*args):
    env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'}
    subprocess.Popen([str(path),*map(str,args)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)


def valid_stage(stage,target):
    return stage.parent==target.parent and stage.name.startswith('.lisa-update-') and stage.is_dir() and not stage.is_symlink()


def start_install(stage,target):
    destination_for(target)
    helper=stage/'helper.exe'
    shutil.copyfile(target,helper)
    launch(helper,'--apply-update',stage,target)


def replace(stage,target):
    ready,backup=stage/'ready.exe',stage/'backup.exe'
    if not valid_stage(stage,target) or not ready.is_file() or backup.exists(): raise ValueError('Некорректная папка обновления.')
    destination=destination_for(target)
    deadline=time.monotonic()+30
    while True:
        try: os.replace(target,backup); break
        except PermissionError:
            if time.monotonic()>=deadline: raise
            time.sleep(.25)
    installed=False
    try:
        # On Windows rename fails if another file already occupies the destination.
        os.rename(ready,destination)
        installed=True
        launch(destination,'--update-cleanup',stage)
    except Exception:
        if installed: os.rename(destination,ready)
        os.rename(backup,target)
        launch(target)
        raise


def stage_name_migration(target):
    destination_for(target)
    stage=Path(tempfile.mkdtemp(prefix='.lisa-update-',dir=target.parent))
    try: shutil.copyfile(target,stage/'ready.exe')
    except OSError:
        cleanup(stage,target)
        raise
    return stage


def helper_main(stage,target):
    stage,target=Path(stage).resolve(),Path(target).resolve()
    if Path(sys.executable).resolve()!=stage/'helper.exe': return 1
    try: replace(stage,target); return 0
    except Exception as exc:
        ctypes.windll.user32.MessageBoxW(None,f'Не удалось завершить обновление.\n{exc}', 'Lisa Macro Magic',0x10)
        return 1


def cleanup(stage,target):
    stage=Path(stage).absolute()
    if not valid_stage(stage,target): return False
    try:
        for name in ('helper.exe','backup.exe','ready.exe'): (stage/name).unlink(missing_ok=True)
        stage.rmdir()
        return True
    except OSError: return False
