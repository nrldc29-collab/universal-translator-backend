#!/usr/bin/env bash
set -euo pipefail

ACTION="${1:-}"
ENV_FILE="${2:-/opt/true-streaming-stt-provider/.env}"
APP_DIR="${3:-/opt/true-streaming-stt-provider}"

if [ "$ACTION" = "" ]; then
  echo "Usage:"
  echo "  bash deploy/scripts/audit-admin-action.sh action-name /path/to/.env /app/dir"
  exit 1
fi

mkdir -p "$APP_DIR/logs"

ADMIN_API_KEY=""
if [ -f "$ENV_FILE" ]; then
  ADMIN_API_KEY="$(grep '^ADMIN_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d '=' -f 2- || true)"
fi

python3 - <<PY
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os

action = "$ACTION"
admin_key = "$ADMIN_API_KEY"
log_path = Path("$APP_DIR/logs/admin-audit.jsonl")

fingerprint = ""
if admin_key:
    fingerprint = hashlib.sha256(admin_key.encode("utf-8")).hexdigest()[:12]

payload = {
    "created_at": datetime.now(timezone.utc).isoformat(),
    "event_type": action,
    "admin_api_key_fingerprint": fingerprint,
    "source": "deploy_script",
    "actor_uid": os.getuid(),
}

log_path.parent.mkdir(parents=True, exist_ok=True)

with log_path.open("a", encoding="utf-8") as file:
    file.write(json.dumps(payload, ensure_ascii=False) + "\n")
PY
