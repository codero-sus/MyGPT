@echo off
rem Start the MyGPT WebUI (Windows).
rem
rem Python location (all optional, first valid one wins):
rem   1. python.env in the project root (PYTHON=<path>)
rem   2. the 2PY2 environment variable ("second python" - for portable /
rem      embeddable Python users; the name means a *second* python, not python2)
rem   3. the project .venv (created + installed on first run), then python
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
      echo python.env points to "!CAND!", which was not found - trying 2PY2 / the project .venv.
    )
    set "CAND="
  )
)

rem 2) 2PY2 environment variable - portable / embeddable Python
if not defined PY if defined 2PY2 (
  set "CAND=!2PY2!"
  set "OK="
  if exist "!CAND!" set "OK=1"
  if not defined OK where /q "!CAND!" 2>nul && set "OK=1"
  if defined OK (set "PY=!CAND!") else (
    echo 2PY2 points to "!CAND!", which was not found - falling back to the project .venv.
  )
  set "CAND="
)

rem 3) project venv (bootstrap on first run), then python on PATH
if not defined PY (
  if exist ".venv\Scripts\python.exe" (
    set "PY=.venv\Scripts\python.exe"
  ) else (
    python -m venv .venv && .venv\Scripts\python.exe -m pip install -r requirements.txt && set "PY=.venv\Scripts\python.exe"
  )
)

if not defined PY (
  echo Python was not found. Install Python 3.11+ or point python.env / 2PY2 at it.
  exit /b 1
)

"!PY!" app.py
exit /b %ERRORLEVEL%
