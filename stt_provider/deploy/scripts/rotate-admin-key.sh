#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/true-streaming-stt-provider/.env}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this on the VPS with sudo:"
  echo "sudo bash deploy/scripts/rotate-admin-key.sh"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

NEW_ADMIN_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

python3 - <<PY
from pathlib import Path

env_file = Path("$ENV_FILE")
new_admin_key = "$NEW_ADMIN_KEY"

text = env_file.read_text()
lines = []
saw_admin_key = False

for line in text.splitlines():
    if line.startswith("ADMIN_API_KEY="):
        lines.append(f"ADMIN_API_KEY={new_admin_key}")
        saw_admin_key = True
    else:
        lines.append(line)

if not saw_admin_key:
    lines.append(f"ADMIN_API_KEY={new_admin_key}")

env_file.write_text("\\n".join(lines) + "\\n")
PY

echo "Rotated ADMIN_API_KEY in: $ENV_FILE"
echo
echo "New ADMIN_API_KEY:"
echo "$NEW_ADMIN_KEY"
echo
bash "$(dirname "$0")/audit-admin-action.sh" "admin_api_key.rotated" "$ENV_FILE" "$(dirname "$ENV_FILE")"
echo "Restart the server for changes to apply:"
echo "cd /opt/true-streaming-stt-provider && sudo docker compose up -d --build"
