#!/usr/bin/env bash
# Start the MyGPT WebUI.
# MyGPT Personal-Use License — see LICENSE. Personal, non-commercial use of
# unmodified copies only.
set -e
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  python3 -m venv .venv
  .venv/bin/pip install -r requirements.txt
fi

exec .venv/bin/python app.py
