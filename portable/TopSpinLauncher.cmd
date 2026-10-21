@echo off
setlocal
cd /d "%~dp0"
if exist "%~dp0TopSpinLauncher.exe" goto packaged
if exist "%~dp0runtime\python\pythonw.exe" goto private_python
where pyw >nul 2>nul
if errorlevel 1 goto missing
pyw -3 -m launcher --game-dir "%~dp0." %*
exit /b %errorlevel%
:packaged
start "" /wait "%~dp0TopSpinLauncher.exe" %*
exit /b %errorlevel%
:private_python
start "" /wait "%~dp0runtime\python\pythonw.exe" -m launcher --game-dir "%~dp0." %*
exit /b %errorlevel%
:missing
echo The packaged launcher runtime was not found. This source build requires Python with Tk.
pause
exit /b 1
