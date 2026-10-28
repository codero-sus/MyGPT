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
# Python location (all optional, first valid one wins):
#   1. python.env in the project root (PYTHON=<path>)
#   2. the 2PY2 environment variable ("second python" — for portable /
#      embeddable Python users; the name means a *second* python, not python2)
#   3. the project .venv, then python3 / python on PATH
#
# MyGPT Personal-Use License — see LICENSE. Personal, non-commercial use of
# unmodified copies only.
set -e
cd "$(dirname "$0")"

check_py() {  # $1 = candidate path or command
  [ -n "$1" ] || return 1
  [ -x "$1" ] && return 0
  command -v "$1" >/dev/null 2>&1
}

PY=""

# 1) python.env — optional project file with the Python location
if [ -f python.env ]; then
  CAND="$(grep -E '^[[:space:]]*PYTHON=' python.env | tail -n 1 | cut -d= -f2- \
          | tr -d '"' | tr -d "'" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  if check_py "$CAND"; then
    PY="$CAND"
  elif [ -n "$CAND" ]; then
    echo "python.env points to '$CAND', which was not found — trying 2PY2 / auto-detection." >&2
  fi
fi

# 2) 2PY2 environment variable — portable / embeddable Python
#    (name starts with a digit, so it must be read via printenv)
if [ -z "$PY" ]; then
  CAND="$(printenv 2PY2 2>/dev/null || true)"
  if check_py "$CAND"; then
    PY="$CAND"
  elif [ -n "$CAND" ]; then
    echo "2PY2 points to '$CAND', which was not found — falling back to auto-detection." >&2
  fi
fi

# 3) fallbacks: project venv, then system python
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
