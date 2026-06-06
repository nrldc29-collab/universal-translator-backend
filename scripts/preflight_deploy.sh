#!/usr/bin/env bash
# Linux/macOS counterpart to Test-DeploymentReady.ps1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${PREFLIGHT_URL:-http://127.0.0.1:8000}"
RUN_SMOKE=0

for arg in "$@"; do
  case "$arg" in
    --smoke) RUN_SMOKE=1 ;;
    http://*|https://*) BASE_URL="$arg" ;;
  esac
done

failures=()

check_file() {
  local path="$1"
  if [[ ! -f "$ROOT/$path" ]]; then
    failures+=("missing file: $path")
  fi
}

check_file Dockerfile
check_file railway.json
check_file requirements-railway.txt
check_file RAILWAY-DEPLOY.md
check_file scripts/smoke_local.py
check_file Get-Railway-Variables.ps1
check_file Get-Railway-Variables.sh

if ! grep -q "frontend-build" "$ROOT/Dockerfile" || ! grep -q "SERVE_FRONTEND_DIST=1" "$ROOT/Dockerfile"; then
  failures+=("Dockerfile must build frontend and set SERVE_FRONTEND_DIST=1")
fi

if ! grep -q "MAX_ACTIVE_STREAMS_PER_USER=5" "$ROOT/Dockerfile"; then
  failures+=("Dockerfile missing MAX_ACTIVE_STREAMS_PER_USER=5 for conversation mode")
fi

if ! grep -q "QUOTA_REQUESTS_PER_HOUR=500" "$ROOT/Dockerfile"; then
  failures+=("Dockerfile missing QUOTA_REQUESTS_PER_HOUR=500")
fi

if ! grep -q "\.up\.railway\.app" "$ROOT/frontend/src/utils.js"; then
  failures+=("frontend/src/utils.js missing Railway same-origin wss support")
fi

if ! grep -q "QUOTA_REQUESTS_PER_HOUR = \"500\"" "$ROOT/Get-Railway-Variables.ps1"; then
  failures+=("Get-Railway-Variables.ps1 missing QUOTA_REQUESTS_PER_HOUR=500")
fi

if ! grep -qE 'QUOTA_REQUESTS_PER_HOUR.*500' "$ROOT/Get-Railway-Variables.sh"; then
  failures+=("Get-Railway-Variables.sh missing QUOTA_REQUESTS_PER_HOUR=500")
fi

if [[ -f "$ROOT/.env.example" ]]; then
  bom_check="$(python3 - "$ROOT/.env.example" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
sys.exit(0 if path.read_bytes()[:3] != b"\xef\xbb\xbf" else 1)
PY
)"
  if [[ "$bom_check" -ne 0 ]]; then
    failures+=(".env.example must not contain a UTF-8 BOM (breaks cp .env.example .env on Linux)")
  fi
fi

if ! bash "$ROOT/Get-Railway-Variables.sh" demo test-password 2>/dev/null | grep -q "USERS=demo:test-password"; then
  failures+=("Get-Railway-Variables.sh did not emit expected USERS line")
fi

if ! grep -q "JWT_SECRET" "$ROOT/deploy.sh" || ! grep -q "scripts/smoke_local.py" "$ROOT/deploy.sh"; then
  failures+=("deploy.sh must set production JWT_SECRET/USERS and run smoke_local.py")
fi

if [[ ${#failures[@]} -gt 0 ]]; then
  echo "Deploy preflight failed:"
  for err in "${failures[@]}"; do
    echo "  - $err"
  done
  exit 1
fi

echo "Deploy preflight passed (files and production defaults)."

if [[ "$RUN_SMOKE" -eq 1 ]]; then
  echo "Running live smoke against $BASE_URL ..."
  python3 "$ROOT/scripts/smoke_local.py" "${BASE_URL%/}"
fi
