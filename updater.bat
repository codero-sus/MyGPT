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
rem The Python interpreter is read from python.env (PYTHON=...); if that file
rem or path is missing, it falls back to the project .venv, then python.
rem
rem MyGPT Personal-Use License - see LICENSE. Personal, non-commercial use of
rem unmodified copies only.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY="

rem 1) python.env - the project's Python location
if exist "python.env" (
  for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"PYTHON=" python.env 2^>nul') do set "PY=%%b"
)
if defined PY set "PY=!PY:"=!"
if defined PY (
  set "PYOK="
  if exist "!PY!" set "PYOK=1"
  if not defined PYOK where /q "!PY!" 2>nul && set "PYOK=1"
  if not defined PYOK (
    echo python.env points to "!PY!", which was not found - falling back to auto-detection.
    set "PY="
  )
)

rem 2) fallbacks: project venv, then python on PATH
if not defined PY (
  if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
)

"!PY!" -m mygpt.updater %*
exit /b %ERRORLEVEL%
