#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "" ]; then
  echo "Usage:"
  echo "  bash deploy/scripts/set-domain.sh your-domain.com"
  exit 1
fi

DOMAIN="$1"
NGINX_CONF="deploy/nginx/stt-provider.conf"

if [ ! -f "$NGINX_CONF" ]; then
  echo "Missing Nginx config: $NGINX_CONF"
  exit 1
fi

python3 - <<PY
from pathlib import Path

domain = "$DOMAIN"
path = Path("$NGINX_CONF")
text = path.read_text()

text = text.replace("your-domain.com", domain)

path.write_text(text)

print(f"Updated {path} to use domain: {domain}")
PY

echo
echo "Recommended .env value:"
echo "ALLOWED_ORIGINS=https://$DOMAIN,https://www.$DOMAIN"
