#!/usr/bin/env bash
# Linux/macOS counterpart to Start-Translator.ps1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SKIP_SETUP=0

for arg in "$@"; do
  case "$arg" in
    --skip-setup) SKIP_SETUP=1 ;;
  esac
done

cd "$ROOT"
mkdir -p logs

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source <(sed 's/^\uFEFF//' "$ROOT/.env" | grep -v '^#' | grep -v '^$' | sed 's/^/export /')
  set +a
fi

export FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:${FRONTEND_PORT}}"
export ALLOWED_ORIGIN_REGEX="${ALLOWED_ORIGIN_REGEX:-https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?|https://.*\.trycloudflare\.com}"
export TRANSLATION_BACKEND="${TRANSLATION_BACKEND:-marian}"
export WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-small}"
export PRELOAD_MODELS="${PRELOAD_MODELS:-1}"
export HYBRID_ENABLE_REMOTE="${HYBRID_ENABLE_REMOTE:-0}"
export PREFER_CLOUD_TTS="${PREFER_CLOUD_TTS:-0}"
export PARTIAL_TTS_MODE="${PARTIAL_TTS_MODE:-true}"

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/venv/bin/python" ]]; then
  PYTHON="$ROOT/venv/bin/python"
fi
if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Missing python3. Install requirements: pip install -r requirements.txt" >&2
  exit 1
fi

port_open() {
  "$PYTHON" - <<PY "$1"
import socket, sys
port = int(sys.argv[1])
s = socket.socket()
s.settimeout(0.5)
try:
    s.connect(("127.0.0.1", port))
except OSError:
    sys.exit(1)
finally:
    s.close()
PY
}

wait_ready() {
  for _ in $(seq 1 120); do
    if curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" | "$PYTHON" -c "import json,sys; sys.exit(0 if json.load(sys.stdin).get('ready') else 1)" 2>/dev/null; then
      return 0
    fi
    sleep 2
  done
  return 1
}

if [[ "$SKIP_SETUP" -eq 0 ]]; then
  echo "Running local model setup (first run downloads models)..."
  "$PYTHON" "$ROOT/scripts/setup_models.py"
fi

if ! port_open "$BACKEND_PORT"; then
  echo "Starting backend on port ${BACKEND_PORT}..."
  nohup "$PYTHON" -m uvicorn backend.api:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    >"$ROOT/logs/backend.out.log" 2>"$ROOT/logs/backend.err.log" &
fi

if ! port_open "$FRONTEND_PORT"; then
  if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
    echo "Missing frontend deps. Run: cd frontend && npm install" >&2
    exit 1
  fi
  echo "Starting frontend on port ${FRONTEND_PORT}..."
  nohup "$ROOT/frontend/node_modules/.bin/vite" --host 0.0.0.0 --port "$FRONTEND_PORT" \
    >"$ROOT/logs/frontend.out.log" 2>"$ROOT/logs/frontend.err.log" &
fi

echo "Waiting for backend models to finish loading..."
if wait_ready; then
  echo "Status:     LIVE (models ready)"
else
  echo "Status:     WARMING (check logs/backend.err.log)"
fi

echo ""
echo "Local app:  http://127.0.0.1:${FRONTEND_PORT}/"
echo "Backend:    http://127.0.0.1:${BACKEND_PORT}/"
echo "Health:     http://127.0.0.1:${BACKEND_PORT}/health"
echo "Verify:     make verify-local-live"
echo ""
echo "Logs:"
echo "  Backend:  $ROOT/logs/backend.err.log"
echo "  Frontend: $ROOT/logs/frontend.err.log"
