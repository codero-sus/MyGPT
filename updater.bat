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
rem Python location (all optional, first valid one wins):
rem   1. python.env in the project root (PYTHON=<path>)
rem   2. the 2PY2 environment variable ("second python" - for portable /
rem      embeddable Python users; the name means a *second* python, not python2)
rem   3. the project .venv, then python on PATH
rem
rem MyGPT Personal-Use License - see LICENSE. Personal, non-commercial use of
rem unmodified copies only.
setlocal enabledelayedexpansion
cd /d "%~dp0"

set "PY="

rem 1) python.env - optional project file with the Python location
if exist "python.env" (
  for /f "tokens=1,* delims==" %%a in ('findstr /b /c:"PYTHON=" python.env 2^>nul') do set "CAND=%%b"
  if defined CAND (
    set "CAND=!CAND:"=!"
    set "OK="
    if exist "!CAND!" set "OK=1"
    if not defined OK where /q "!CAND!" 2>nul && set "OK=1"
    if defined OK (set "PY=!CAND!") else (
      echo python.env points to "!CAND!", which was not found - trying 2PY2 / auto-detection.
    )
    set "CAND="
  )
)

rem 2) 2PY2 environment variable - portable / embeddable Python
rem    (read with delayed expansion: !2PY2! because %2PY2% collides with %%2)
if not defined PY if defined 2PY2 (
  set "CAND=!2PY2!"
  set "OK="
  if exist "!CAND!" set "OK=1"
  if not defined OK where /q "!CAND!" 2>nul && set "OK=1"
  if defined OK (set "PY=!CAND!") else (
    echo 2PY2 points to "!CAND!", which was not found - falling back to auto-detection.
  )
  set "CAND="
)

rem 3) fallbacks: project venv, then python on PATH
if not defined PY (
  if exist ".venv\Scripts\python.exe" (set "PY=.venv\Scripts\python.exe") else (set "PY=python")
)

"!PY!" -m mygpt.updater %*
exit /b %ERRORLEVEL%
