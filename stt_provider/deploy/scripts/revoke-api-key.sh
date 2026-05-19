#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/true-streaming-stt-provider/.env}"
TARGET="${2:-}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this on the VPS with sudo:"
  echo "sudo bash deploy/scripts/revoke-api-key.sh /opt/true-streaming-stt-provider/.env label-or-key"
  exit 1
fi

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

if [ "$TARGET" = "" ]; then
  echo "Usage:"
  echo "sudo bash deploy/scripts/revoke-api-key.sh /opt/true-streaming-stt-provider/.env label-or-key"
  echo
  echo "Examples:"
  echo "sudo bash deploy/scripts/revoke-api-key.sh /opt/true-streaming-stt-provider/.env previous"
  echo "sudo bash deploy/scripts/revoke-api-key.sh /opt/true-streaming-stt-provider/.env old-secret-key-value"
  exit 1
fi

python3 - <<PY
from pathlib import Path

env_file = Path("$ENV_FILE")
target = "$TARGET"

text = env_file.read_text()
lines = text.splitlines()
updated = []

removed = []

for line in lines:
    if line.startswith("STT_API_KEYS="):
        raw = line.split("=", 1)[1].strip()
        entries = [item.strip() for item in raw.split(",") if item.strip()]
        kept = []

        for entry in entries:
            if ":" in entry:
                label, key = entry.split(":", 1)
                label = label.strip()
                key = key.strip()

                if target in {label, key, entry}:
                    removed.append(entry)
                    continue

            elif target in {entry}:
                removed.append(entry)
                continue

            kept.append(entry)

        updated.append("STT_API_KEYS=" + ",".join(kept))

    else:
        updated.append(line)

env_file.write_text("\\n".join(updated) + "\\n")

if removed:
    print("Removed entries:")
    for item in removed:
        print(f"- {item.split(':', 1)[0] if ':' in item else 'unlabeled'}")
else:
    print("No matching STT_API_KEYS entries found.")
PY

bash "$(dirname "$0")/audit-admin-action.sh" "api_key.revoked" "$ENV_FILE" "$(dirname "$ENV_FILE")"
echo
echo "Restart the server for changes to apply:"
echo "cd /opt/true-streaming-stt-provider && sudo docker compose up -d --build"
