#!/usr/bin/env bash
# MyGPT updater (Linux / macOS) — manual, branch-pinned, confirmed.
#
# Checks the official codero-sus/MyGPT branch on GitHub and, only after your
# confirmation, installs the pinned update. Your learned state in data/ is
# never touched. Restart MyGPT afterwards to load the new version.
#
#   ./updater.sh              check, then ask before installing
#   ./updater.sh --check      only check, never install
#   ./updater.sh --yes        install without asking
#
# The Python interpreter is read from python.env (PYTHON=...); if that file
# or path is missing, it falls back to the project .venv, then python3/python.
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
    echo "python.env points to '$PY', which was not found — falling back to auto-detection." >&2
    PY=""
  fi
fi

# 2) fallbacks: project venv, then system python
if [ -z "$PY" ]; then
  if [ -x .venv/bin/python ]; then
    PY=.venv/bin/python
  elif command -v python3 >/dev/null 2>&1; then
    PY=python3
  else
    PY=python
  fi
fi

exec "$PY" -m mygpt.updater "$@"
