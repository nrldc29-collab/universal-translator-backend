#!/usr/bin/env bash
# Linux/macOS counterpart to Start-Translator.ps1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5173}"
SKIP_SETUP=0
RESTART=0

for arg in "$@"; do
  case "$arg" in
    --skip-setup) SKIP_SETUP=1 ;;
    --restart) RESTART=1 ;;
  esac
done

cd "$ROOT"
mkdir -p logs

PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/venv/bin/python" ]]; then
  PYTHON="$ROOT/venv/bin/python"
fi

if [[ -f "$ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source <("$PYTHON" - <<'PY' "$ROOT/.env"
import shlex
import sys
from pathlib import Path

for raw_line in Path(sys.argv[1]).read_text(encoding="utf-8-sig", errors="replace").splitlines():
    line = raw_line.strip()
    if not line or line.startswith("#") or "=" not in line:
        continue
    key, _, value = line.partition("=")
    key = key.strip()
    value = value.strip().strip('"').strip("'")
    if key:
        print(f"export {key}={shlex.quote(value)}")
PY
)
  set +a
fi

export FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:${FRONTEND_PORT}}"
if [[ -z "${ALLOWED_ORIGIN_REGEX:-}" ]]; then
  export ALLOWED_ORIGIN_REGEX='https?://(localhost|127\.0\.0\.1|192\.168\.\d{1,3}\.\d{1,3}|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3})(:\d+)?|https://.*\.trycloudflare\.com'
fi
export TRANSLATION_BACKEND="${TRANSLATION_BACKEND:-marian}"
export WHISPER_MODEL_SIZE="${WHISPER_MODEL_SIZE:-small}"
export PRELOAD_MODELS="${PRELOAD_MODELS:-1}"
export HYBRID_ENABLE_REMOTE="${HYBRID_ENABLE_REMOTE:-0}"
export PREFER_CLOUD_TTS="${PREFER_CLOUD_TTS:-0}"
export PARTIAL_TTS_MODE="${PARTIAL_TTS_MODE:-true}"
export QUOTA_REQUESTS_PER_HOUR="${QUOTA_REQUESTS_PER_HOUR:-500}"
export MAX_ACTIVE_STREAMS_PER_USER="${MAX_ACTIVE_STREAMS_PER_USER:-5}"
if [[ "${MAX_ACTIVE_STREAMS_PER_USER}" -lt 5 ]]; then
  export MAX_ACTIVE_STREAMS_PER_USER=5
fi
export STT_PROVIDER="${STT_PROVIDER:-local}"
export REQUESTS_PER_MINUTE="${REQUESTS_PER_MINUTE:-120}"

if ! command -v "$PYTHON" >/dev/null 2>&1; then
  echo "Missing python3. Install requirements: pip install -r requirements.txt" >&2
  exit 1
fi

if ! command -v espeak-ng >/dev/null 2>&1 && ! command -v espeak >/dev/null 2>&1; then
  if [[ "${SKIP_ESPEAK_CHECK:-0}" != "1" ]]; then
    echo "Error: espeak-ng/espeak not found — Haitian Creole TTS requires espeak (apt install espeak-ng / brew install espeak)." >&2
    echo "Set SKIP_ESPEAK_CHECK=1 to bypass this check." >&2
    exit 1
  fi
  echo "Warning: espeak-ng/espeak not found — Haitian Creole TTS will be unavailable." >&2
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

kill_port() {
  local port="$1"
  if command -v fuser >/dev/null 2>&1; then
    fuser -k "${port}/tcp" >/dev/null 2>&1 || true
  elif command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -t -i:"${port}" 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      kill -9 $pids 2>/dev/null || true
    fi
  fi
  sleep 1
}

backend_health_ok() {
  curl -sf "http://127.0.0.1:${BACKEND_PORT}/health" >/dev/null 2>&1
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

if [[ "$RESTART" -eq 1 ]]; then
  echo "Restart requested — stopping listeners on ${BACKEND_PORT} and ${FRONTEND_PORT}..."
  kill_port "$BACKEND_PORT"
  kill_port "$FRONTEND_PORT"
fi

if [[ "$SKIP_SETUP" -eq 0 ]]; then
  echo "Running local model setup (first run downloads models)..."
  if ! "$PYTHON" "$ROOT/scripts/setup_models.py"; then
    echo "Model setup failed. Fix errors above or rerun with --skip-setup if models are already present." >&2
    exit 1
  fi
fi

if port_open "$BACKEND_PORT"; then
  if [[ "$RESTART" -eq 1 ]] || ! backend_health_ok; then
    echo "Replacing stale backend listener on port ${BACKEND_PORT}..."
    kill_port "$BACKEND_PORT"
  else
    echo "Backend already listening on port ${BACKEND_PORT}"
  fi
fi

if ! port_open "$BACKEND_PORT"; then
  echo "Starting backend on port ${BACKEND_PORT}..."
  nohup env \
    REQUESTS_PER_MINUTE="${REQUESTS_PER_MINUTE}" \
    QUOTA_REQUESTS_PER_HOUR="${QUOTA_REQUESTS_PER_HOUR:-500}" \
    MAX_ACTIVE_STREAMS_PER_USER="${MAX_ACTIVE_STREAMS_PER_USER}" \
    STT_PROVIDER="${STT_PROVIDER}" \
    TRANSLATION_BACKEND="${TRANSLATION_BACKEND}" \
    PARTIAL_TTS_MODE="${PARTIAL_TTS_MODE}" \
    "$PYTHON" -m uvicorn backend.api:app --host 0.0.0.0 --port "$BACKEND_PORT" \
    >"$ROOT/logs/backend.out.log" 2>"$ROOT/logs/backend.err.log" &
fi

if port_open "$FRONTEND_PORT"; then
  if [[ "$RESTART" -eq 1 ]]; then
    echo "Replacing frontend listener on port ${FRONTEND_PORT}..."
    kill_port "$FRONTEND_PORT"
  else
    echo "Frontend already listening on port ${FRONTEND_PORT}"
  fi
fi

if ! port_open "$FRONTEND_PORT"; then
  if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
    echo "Installing frontend dependencies..."
    if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]] && ! (cd "$ROOT/frontend" && npm ci); then
      echo "Missing frontend deps. Run: cd frontend && npm install" >&2
      exit 1
    fi
  fi
  if [[ ! -x "$ROOT/frontend/node_modules/.bin/vite" ]]; then
    echo "Missing frontend deps. Run: cd frontend && npm install" >&2
    exit 1
  fi
  echo "Starting frontend on port ${FRONTEND_PORT}..."
  nohup bash -c "cd '$ROOT/frontend' && exec '$ROOT/frontend/node_modules/.bin/vite' --host 0.0.0.0 --port '$FRONTEND_PORT'" \
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
