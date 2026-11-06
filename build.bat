@echo off
setlocal
cd /d "%~dp0"
if defined LISA_PYTHON (goto custom_python)
py -3.12 -m venv .venv
goto created
:custom_python
"%LISA_PYTHON%" -m venv .venv
:created
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -c "import sys,struct; assert sys.platform == 'win32' and struct.calcsize('P') == 8, 'Windows x64 Python required'"
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m unittest discover -s tests -v
if errorlevel 1 goto failed
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --noupx --hidden-import pynput.keyboard._win32 --hidden-import pynput.mouse._win32 --icon assets\fox.ico --add-data "assets;assets" --name LisaMacroMagic_v0.5.15 app.py
if errorlevel 1 goto failed
echo Ready: dist\LisaMacroMagic_v0.5.15.exe
exit /b 0
:failed
echo Build failed. See errors above.
exit /b 1


