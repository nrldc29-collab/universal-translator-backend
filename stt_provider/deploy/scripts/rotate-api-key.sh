#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/true-streaming-stt-provider/.env}"
LABEL="${2:-rotated}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this on the VPS with sudo:"
  echo "sudo bash deploy/scripts/rotate-api-key.sh"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

NEW_KEY="$(python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
)"

python3 - <<PY
from pathlib import Path

env_file = Path("$ENV_FILE")
label = "$LABEL"
new_key = "$NEW_KEY"

text = env_file.read_text()
lines = text.splitlines()

current_primary = ""
for line in lines:
    if line.startswith("STT_API_KEY="):
        current_primary = line.split("=", 1)[1].strip()
        break

updated = []
saw_primary = False
saw_keys = False

for line in lines:
    if line.startswith("STT_API_KEY="):
        updated.append(f"STT_API_KEY={new_key}")
        saw_primary = True

    elif line.startswith("STT_API_KEYS="):
        existing = line.split("=", 1)[1].strip()
        entries = []

        if existing:
            entries.extend([item.strip() for item in existing.split(",") if item.strip()])

        if current_primary:
            entries.append(f"previous:{current_primary}")

        entries.append(f"{label}:{new_key}")

        deduped = []
        seen = set()
        for entry in entries:
            if entry not in seen:
                deduped.append(entry)
                seen.add(entry)

        updated.append("STT_API_KEYS=" + ",".join(deduped))
        saw_keys = True

    else:
        updated.append(line)

if not saw_primary:
    updated.append(f"STT_API_KEY={new_key}")

if not saw_keys:
    if current_primary:
        updated.append(f"STT_API_KEYS=previous:{current_primary},{label}:{new_key}")
    else:
        updated.append(f"STT_API_KEYS={label}:{new_key}")

env_file.write_text("\\n".join(updated) + "\\n")
PY

echo "Rotated API key in: $ENV_FILE"
echo
echo "New STT_API_KEY:"
echo "$NEW_KEY"
echo
echo "Existing clients using the previous key will continue to work through STT_API_KEYS."
bash "$(dirname "$0")/audit-admin-action.sh" "api_key.rotated" "$ENV_FILE" "$(dirname "$ENV_FILE")"
echo "Restart the server for changes to apply:"
echo "cd /opt/true-streaming-stt-provider && docker compose up -d --build"
