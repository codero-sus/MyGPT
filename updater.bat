@echo off
rem MyGPT updater (Windows) - manual, branch-pinned, confirmed.
rem
rem Checks the official codero-sus/MyGPT branch on GitHub and, only after your
rem confirmation, installs the pinned update. Your learned state in data\ is
rem never touched. Restart MyGPT afterwards to load the new version.
rem
rem   updater.bat              check, then ask before installing
rem   updater.bat --check      only check, never install
rem   updater.bat --yes        install without asking
rem
rem MyGPT Personal-Use License - see LICENSE. Personal, non-commercial use of
rem unmodified copies only.
setlocal
cd /d "%~dp0"

set "PY=python"
if exist ".venv\Scripts\python.exe" set "PY=.venv\Scripts\python.exe"

"%PY%" -m mygpt.updater %*
exit /b %ERRORLEVEL%
