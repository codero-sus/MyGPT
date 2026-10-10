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
# MyGPT Personal-Use License — see LICENSE. Personal, non-commercial use of
# unmodified copies only.
set -e
cd "$(dirname "$0")"

if [ -x .venv/bin/python ]; then
  PY=.venv/bin/python
elif command -v python3 >/dev/null 2>&1; then
  PY=python3
else
  PY=python
fi

exec "$PY" -m mygpt.updater "$@"
