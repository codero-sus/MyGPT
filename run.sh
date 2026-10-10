#!/usr/bin/env bash
# Start the MyGPT WebUI.
#
# The Python interpreter is read from python.env (PYTHON=...); if that file
# or path is missing, it falls back to the project .venv (creating it and
# installing requirements on first run).
#
# MyGPT Personal-Use License — see LICENSE. Personal, non-commercial use of
# unmodified copies only.
set -e
cd "$(dirname "$0")"

PY=""

# 1) python.env — the project's Python location
if [ -f python.env ]; then
  PY="$(grep -E '^[[:space:]]*PYTHON=' python.env | tail -n 1 | cut -d= -f2- \
        | tr -d '"' | tr -d "'" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if [ -n "$PY" ] && [ ! -x "$PY" ] && ! command -v "$PY" >/dev/null 2>&1; then
    echo "python.env points to '$PY', which was not found — falling back to the project .venv." >&2
    PY=""
  fi
fi

# 2) fallback: bootstrap the project venv
if [ -z "$PY" ]; then
  if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
  fi
  PY=.venv/bin/python
fi

exec "$PY" app.py
