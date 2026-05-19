#!/usr/bin/env bash
set -euo pipefail

APP_DIR="/opt/true-streaming-stt-provider"
NGINX_CONF_NAME="stt-provider.conf"
NGINX_AVAILABLE="/etc/nginx/sites-available/$NGINX_CONF_NAME"
NGINX_ENABLED="/etc/nginx/sites-enabled/$NGINX_CONF_NAME"

if [ -f "./deploy/scripts/preflight.sh" ]; then
  bash ./deploy/scripts/preflight.sh
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this script with sudo:"
  echo "sudo bash deploy/scripts/deploy-vps.sh"
  exit 1
fi

if ! command -v docker >/dev/null 2>&1; then
  apt-get update
  apt-get install -y ca-certificates curl gnupg rsync nginx

  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg \
    | gpg --dearmor -o /etc/apt/keyrings/docker.gpg

  chmod a+r /etc/apt/keyrings/docker.gpg

  . /etc/os-release

  echo \
    "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" \
    > /etc/apt/sources.list.d/docker.list

  apt-get update
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
else
  apt-get update
  apt-get install -y rsync nginx
fi

mkdir -p "$APP_DIR"

rsync -a \
  --exclude ".git" \
  --exclude "server/.venv" \
  --exclude "__pycache__" \
  ./ "$APP_DIR/"

cd "$APP_DIR"

if [ ! -f ".env" ]; then
  GENERATED_KEY="$(python3 - <<'PYKEY'
import secrets
print(secrets.token_urlsafe(48))
PYKEY
)"

  GENERATED_ADMIN_KEY="$(python3 - <<'PYADMIN
import secrets
print(secrets.token_urlsafe(48))
PYADMIN
)"

  cp .env.example .env

  python3 - <<PYENV
from pathlib import Path

path = Path(".env")
text = path.read_text()

lines = []
saw_admin_key = False
saw_admin_reset = False

for line in text.splitlines():
    if line.startswith("STT_API_KEY="):
        lines.append("STT_API_KEY=${GENERATED_KEY}")
    elif line.startswith("STT_API_KEYS="):
        lines.append("STT_API_KEYS=default:${GENERATED_KEY}")
    elif line.startswith("ADMIN_API_KEY="):
        lines.append("ADMIN_API_KEY=${GENERATED_ADMIN_KEY}")
        saw_admin_key = True
    elif line.startswith("ENABLE_ADMIN_RESET="):
        lines.append("ENABLE_ADMIN_RESET=false")
        saw_admin_reset = True
    else:
        lines.append(line)

if not saw_admin_key:
    lines.append("ADMIN_API_KEY=${GENERATED_ADMIN_KEY}")

if not saw_admin_reset:
    lines.append("ENABLE_ADMIN_RESET=false")

path.write_text("\\n".join(lines) + "\\n")
PYENV

  echo "Created $APP_DIR/.env with generated STT_API_KEY and ADMIN_API_KEY."
  echo "Edit ALLOWED_ORIGINS before exposing this publicly."
fi

docker compose up -d --build

if [ -f "$APP_DIR/deploy/nginx/$NGINX_CONF_NAME" ]; then
  cp "$APP_DIR/deploy/nginx/$NGINX_CONF_NAME" "$NGINX_AVAILABLE"
  ln -sf "$NGINX_AVAILABLE" "$NGINX_ENABLED"

  nginx -t
  systemctl reload nginx
fi

echo "Deployment complete."
echo "Health check:"
echo "curl http://localhost:8000/health"
echo
echo "If this is first production setup, run Certbot next:"
echo "sudo certbot --nginx -d your-domain.com"
