#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/true-streaming-stt-provider/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

python3 - <<PY
from pathlib import Path
import hashlib

env_file = Path("$ENV_FILE")
text = env_file.read_text()

primary = ""
extra = ""
admin = ""

for line in text.splitlines():
    if line.startswith("STT_API_KEY="):
        primary = line.split("=", 1)[1].strip()
    elif line.startswith("STT_API_KEYS="):
        extra = line.split("=", 1)[1].strip()
    elif line.startswith("ADMIN_API_KEY="):
        admin = line.split("=", 1)[1].strip()

def fingerprint(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()[:12]

print("API keys:")
print()

if primary:
    print("- label: primary")
    print(f"  fingerprint: {fingerprint(primary)}")
    print("  source: STT_API_KEY")
    print("  type: client")
else:
    print("- primary key missing")

if extra:
    for item in [part.strip() for part in extra.split(",") if part.strip()]:
        if ":" in item:
            label, key = item.split(":", 1)
            label = label.strip() or "unnamed"
            key = key.strip()
        else:
            label = "unnamed"
            key = item.strip()

        if not key:
            continue

        print(f"- label: {label}")
        print(f"  fingerprint: {fingerprint(key)}")
        print("  source: STT_API_KEYS")
        print("  type: client")

print()
print("Admin key:")
print()

if admin:
    print("- label: admin")
    print(f"  fingerprint: {fingerprint(admin)}")
    print("  source: ADMIN_API_KEY")
    print("  type: admin")
else:
    print("- admin key missing")
PY
