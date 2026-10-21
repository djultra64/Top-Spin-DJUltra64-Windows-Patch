@echo off
setlocal
cd /d "%~dp0"
call "%~dp0TopSpinLauncher.cmd" --play %*
exit /b %errorlevel%
