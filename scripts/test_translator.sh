#!/usr/bin/env bash
# Linux/macOS counterpart to Test-Translator.ps1
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASE_URL="${1:-http://127.0.0.1:8000}"
PYTHON="${PYTHON:-python3}"
if [[ -x "$ROOT/venv/bin/python" ]]; then
  PYTHON="$ROOT/venv/bin/python"
fi

exec "$PYTHON" "$ROOT/scripts/smoke_local.py" "${BASE_URL%/}"
