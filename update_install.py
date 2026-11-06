"""Separate helper process for replacing a closed Windows one-file executable."""
import ctypes
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time


def launch(path,*args):
    env={**os.environ,'PYINSTALLER_RESET_ENVIRONMENT':'1'}
    subprocess.Popen([str(path),*map(str,args)],env=env,creationflags=subprocess.CREATE_NO_WINDOW)


def valid_stage(stage,target):
    return stage.parent==target.parent and stage.name.startswith('.lisa-update-') and stage.is_dir() and not stage.is_symlink()


def start_install(stage,target):
    helper=stage/'helper.exe'
    shutil.copyfile(target,helper)
    launch(helper,'--apply-update',stage,target)


def replace(stage,target):
    ready,backup=stage/'ready.exe',stage/'backup.exe'
    if not valid_stage(stage,target) or not ready.is_file() or backup.exists(): raise ValueError('Некорректная папка обновления.')
    deadline=time.monotonic()+30
    while True:
        try: os.replace(target,backup); break
        except PermissionError:
            if time.monotonic()>=deadline: raise
            time.sleep(.25)
    try:
        os.replace(ready,target)
        launch(target,'--update-cleanup',stage)
    except Exception:
        os.replace(backup,target)
        launch(target)
        raise


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
