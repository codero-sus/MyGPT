#!/usr/bin/env bash
# Rebuild the whole MyGPT stack after a sandbox / disk reset.
#
# Everything this script does has been needed at least once in practice: a
# wiped .venv, a wiped /tmp, a wiped Cortex clone, a wiped demo model, and a
# git HEAD that a sandbox reset dropped back onto the initial commit while the
# working files survived. Run it, get a working stack again.
#
#   bash tools/restore_stack.sh            rebuild + verify (safe, idempotent)
#   bash tools/restore_stack.sh --serve    also start app:8000, cortex:8625
#                                          and the dashboard proxy:8624
#
# Python location (all optional, first valid one wins — same rule as run.sh):
#   1. python.env in the project root (PYTHON=<path>)
#   2. the 2PY2 environment variable ("second python", not python2)
#   3. python3
#
# MyGPT Personal-Use License — see LICENSE. Personal, non-commercial use of
# unmodified copies only. All credit to codero-sus — https://github.com/codero-sus
set -e
cd "$(dirname "$0")/.."
ROOT="$(pwd)"
SERVE=0
[ "${1:-}" = "--serve" ] && SERVE=1

check_py() {
  [ -n "$1" ] || return 1
  [ -x "$1" ] && return 0
  command -v "$1" >/dev/null 2>&1
}

say() { printf '\n== %s\n' "$*"; }

# ---------------------------------------------------------------- 0. git HEAD
# A sandbox reset can move the branch pointer back to the initial commit while
# the working tree survives. Move HEAD forward to the last pushed commit of the
# current branch; --mixed keeps every working file exactly as it is.
say "git state"
BRANCH="$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo '')"
if [ -n "$BRANCH" ] && [ "$BRANCH" != "HEAD" ]; then
  git fetch -q origin "$BRANCH" 2>/dev/null || true
  if git rev-parse --verify -q "origin/$BRANCH" >/dev/null; then
    LOCAL="$(git rev-parse HEAD)"
    REMOTE="$(git rev-parse "origin/$BRANCH")"
    if [ "$LOCAL" != "$REMOTE" ]; then
      git reset -q --mixed "origin/$BRANCH"
      echo "HEAD moved $LOCAL -> $REMOTE (working files untouched)"
    else
      echo "branch $BRANCH is at the pushed commit"
    fi
  else
    echo "no origin/$BRANCH — leaving HEAD alone"
  fi
else
  echo "detached HEAD — leaving it alone"
fi

# ---------------------------------------------------------------- 1. python
say "python resolution"
BASE_PY=""
if [ -f python.env ]; then
  CAND="$(grep -E '^[[:space:]]*PYTHON=' python.env | tail -n 1 | cut -d= -f2- \
          | tr -d '"' | tr -d "'" | sed -e 's/^[[:space:]]*//' -e 's/[[:space:]]*$//')"
  check_py "$CAND" && BASE_PY="$CAND"
fi
if [ -z "$BASE_PY" ]; then
  CAND="$(printenv 2PY2 2>/dev/null || true)"
  check_py "$CAND" && BASE_PY="$CAND"
fi
if [ -z "$BASE_PY" ]; then
  check_py python3 && BASE_PY=python3
fi
if [ -z "$BASE_PY" ]; then
  echo "Error: no usable python found (python.env / 2PY2 / python3)." >&2
  exit 1
fi
echo "base interpreter: $BASE_PY ($($BASE_PY -V 2>&1))"

# ---------------------------------------------------------------- 2. venv
say "project venv"
if [ ! -x .venv/bin/python ]; then
  "$BASE_PY" -m venv .venv
  echo "created .venv"
else
  echo ".venv already present"
fi
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
# The extras the model engines need. llama-cpp-python builds from source —
# several minutes the first time, cached wheels afterwards.
.venv/bin/pip install -q llama-cpp-python transformers gguf
.venv/bin/python - <<'PY'
import flask, numpy  # noqa: F401
print("core imports ok")
try:
    import llama_cpp, transformers, gguf           # noqa: F401
    print("engine imports ok (llama-cpp, transformers, gguf)")
except ImportError as exc:
    print(f"engine imports missing: {exc}")
PY

# ------------------------------------------------------------- 3. demo GGUF
say "demo model"
if [ ! -s models/mygpt-tiny-test.gguf ]; then
  mkdir -p models
  .venv/bin/python -c "import sys; sys.path.insert(0, 'tests'); \
from gguf_fixture import build_tiny_gguf; \
print('built', build_tiny_gguf('models/mygpt-tiny-test.gguf'))"
else
  echo "models/mygpt-tiny-test.gguf already present"
fi

# ---------------------------------------------------------------- 4. cortex
say "Cortex LLMHoster"
CORTEX_DIR="${HOME}/.cache/llmhoster"
CORTEX_BRANCH="arena/b3072048-cortex-llmhoster"
if [ ! -d "$CORTEX_DIR/.git" ]; then
  mkdir -p "$(dirname "$CORTEX_DIR")"
  git clone -q --branch "$CORTEX_BRANCH" \
    https://github.com/codero-sus/Cortex_LLMHoster "$CORTEX_DIR"
  echo "cloned $CORTEX_BRANCH"
else
  echo "clone already present ($(git -C "$CORTEX_DIR" log --oneline -1))"
fi
# The upstream updater handles branch pinning and JSON backup. Its install
# path is git-only now, so the runtime dependencies go in here — installing
# the package from its unmodified source, exactly what its own updater did.
env 2PY2="$ROOT/.venv/bin/python" bash "$CORTEX_DIR/updater.sh" \
  || echo "warning: cortex updater returned non-zero — clone may be current"
.venv/bin/pip install -q --editable "$CORTEX_DIR" \
  || echo "warning: could not install cortex dependencies"
.venv/bin/python -c "import dotenv, uvicorn, starlette  # cortex runtime" \
  && echo "cortex runtime dependencies ok"

# ---------------------------------------------------------------- 5. verify
say "verify"
.venv/bin/python -c "import sys; sys.path.insert(0, '.'); \
from mygpt import __version__; print('mygpt', __version__)"
git log --oneline -1

if [ "$SERVE" = "1" ]; then
  say "starting services"
  # cortex (loopback only) -> proxy on 0.0.0.0:8624 (frames + headers) ->
  # mygpt on 0.0.0.0:8000
  # setsid --fork, not plain setsid: without the fork, setsid execs in place
  # and the "detached" service stays this script's child — bash then blocks in
  # wait4 at exit for a service that runs forever (found the hard way).
  ( cd "$CORTEX_DIR" && PYTHONPATH=src setsid -f nohup \
      "$ROOT/.venv/bin/python" -m cortex_llmhoster \
      --host 127.0.0.1 --port 8625 >/tmp/cortex.log 2>&1 </dev/null & )
  ( setsid -f nohup "$ROOT/.venv/bin/python" "$ROOT/tools/cortex_proxy.py" \
      >/tmp/cortex_proxy.log 2>&1 </dev/null & )
  ( MYGPT_CORTEX_URL=http://127.0.0.1:8624 PORT=8000 setsid -f nohup \
      "$ROOT/.venv/bin/python" "$ROOT/app.py" >/tmp/mygpt.log 2>&1 </dev/null & )
  # Poll, don't guess: a cold first boot observes the whole corpus before it
  # answers, so three seconds was a coin flip on slower machines.
  probe() {  # $1 = url, $2 = label
    code=000
    for _ in $(seq 1 45); do
      code=$(timeout 3 curl -s -o /dev/null -w '%{http_code}' --max-time 2 "$1" || echo 000)
      [ "$code" = "200" ] && break
      sleep 1
    done
    printf '%-7s %-26s (%s)\n' "$2" "$1" "$code"
  }
  probe http://127.0.0.1:8000/api/ping app
  probe http://127.0.0.1:8625/health cortex
  probe http://127.0.0.1:8624/health proxy
  echo "logs: /tmp/mygpt.log /tmp/cortex.log /tmp/cortex_proxy.log"
else
  say "next: start the stack"
  echo "  bash tools/restore_stack.sh --serve"
  echo "  # or individually:"
  echo "  MYGPT_CORTEX_URL=http://127.0.0.1:8624 PORT=8000 .venv/bin/python app.py"
  echo "  (cd ${CORTEX_DIR} && PYTHONPATH=src ../../MyGPT/.venv/bin/python -m cortex_llmhoster --host 127.0.0.1 --port 8625)"
  echo "  .venv/bin/python tools/cortex_proxy.py"
fi

say "restore complete"
