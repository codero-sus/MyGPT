#!/usr/bin/env bash
# Start the MyGPT WebUI.
#
# Python location (all optional, first valid one wins):
#   1. python.env in the project root (PYTHON=<path>)
#   2. the 2PY2 environment variable ("second python" — for portable /
#      embeddable Python users; the name means a *second* python, not python2)
#   3. the project .venv (created + installed on first run), then python3
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
    echo "python.env points to '$CAND', which was not found — trying 2PY2 / the project .venv." >&2
  fi
fi

# 2) 2PY2 environment variable — portable / embeddable Python
#    (name starts with a digit, so it must be read via printenv)
if [ -z "$PY" ]; then
  CAND="$(printenv 2PY2 2>/dev/null || true)"
  if check_py "$CAND"; then
    PY="$CAND"
  elif [ -n "$CAND" ]; then
    echo "2PY2 points to '$CAND', which was not found — falling back to the project .venv." >&2
  fi
fi

# 3) fallback: bootstrap the project venv
if [ -z "$PY" ]; then
  if [ ! -d .venv ]; then
    python3 -m venv .venv
    .venv/bin/pip install -r requirements.txt
  fi
  PY=.venv/bin/python
fi

exec "$PY" app.py
