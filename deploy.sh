#!/bin/bash
# Anai Translator full-stack deployment (bundled frontend + backend)
# Run on Ubuntu 20.04+ / Debian with Docker available.
#
# Usage:
#   ./deploy.sh [domain]
#
# Example:
#   ./deploy.sh translator.example.com

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

DEPLOY_DIR="${DEPLOY_DIR:-/opt/anai-translator}"
SERVICE_NAME="${SERVICE_NAME:-anai-translator}"
DOMAIN="${1:-}"
PORT=8000
DOCKERFILE="${DOCKERFILE:-Dockerfile}"
IMAGE_TAG="${IMAGE_TAG:-anai-translator:latest}"
DEPLOY_USER="${DEPLOY_USER:-$USER}"

health_ready() {
  local payload="$1"
  python3 - <<'PY' "$payload"
import json
import sys

try:
    data = json.loads(sys.argv[1])
except json.JSONDecodeError:
    sys.exit(1)
sys.exit(0 if data.get("ready") else 1)
PY
}

generate_secret() {
  python3 -c "import secrets; print(secrets.token_urlsafe("$1"))"
}

echo "=== Anai Translator Deployment ==="
echo ""

if [[ -z "${JWT_SECRET:-}" ]]; then
  JWT_SECRET="$(generate_secret 48)"
fi
if [[ -z "${APP_USERNAME:-}" ]]; then
  APP_USERNAME="admin"
fi
if [[ -z "${APP_PASSWORD:-}" ]]; then
  APP_PASSWORD="$(generate_secret 18)"
fi
USERS="${APP_USERNAME}:${APP_PASSWORD}"

if [[ -n "$DOMAIN" && "$DOMAIN" != "translator.local" ]]; then
  ALLOWED_ORIGINS="https://${DOMAIN},http://${DOMAIN}"
else
  ALLOWED_ORIGINS="http://127.0.0.1:${PORT},http://localhost:${PORT}"
fi

echo -e "${YELLOW}Step 1: Install system packages${NC}"
sudo apt-get update
sudo apt-get install -y curl wget git docker.io nginx certbot python3
if command -v docker-compose >/dev/null 2>&1; then
  echo "docker-compose already installed"
else
  sudo apt-get install -y docker-compose || true
fi
echo -e "${GREEN}✓ System packages installed${NC}"
echo ""

echo -e "${YELLOW}Step 2: Start Docker daemon${NC}"
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker "$DEPLOY_USER" || true
echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

echo -e "${YELLOW}Step 3: Prepare deployment directory${NC}"
if [[ "$ROOT" != "$DEPLOY_DIR" ]]; then
  sudo mkdir -p "$DEPLOY_DIR"
  sudo rsync -a --delete --exclude '.git' --exclude 'venv' --exclude 'node_modules' "$ROOT/" "$DEPLOY_DIR/"
  sudo chown -R "$DEPLOY_USER:$DEPLOY_USER" "$DEPLOY_DIR"
fi
cd "$DEPLOY_DIR"
echo -e "${GREEN}✓ Repository ready at $DEPLOY_DIR${NC}"
echo ""

echo -e "${YELLOW}Step 4: Build Docker image (${DOCKERFILE})${NC}"
sudo docker build -f "$DOCKERFILE" -t "$IMAGE_TAG" .
echo -e "${GREEN}✓ Docker image built${NC}"
echo ""

CREDENTIALS_FILE="$DEPLOY_DIR/deploy-credentials.txt"
umask 077
cat >"$CREDENTIALS_FILE" <<EOF
username=$APP_USERNAME
password=$APP_PASSWORD
jwt_secret=$JWT_SECRET
allowed_origins=$ALLOWED_ORIGINS
EOF
chmod 600 "$CREDENTIALS_FILE"
echo -e "${GREEN}✓ Credentials saved to $CREDENTIALS_FILE${NC}"
echo ""

echo -e "${YELLOW}Step 5: Create systemd service${NC}"
sudo tee "/etc/systemd/system/${SERVICE_NAME}.service" > /dev/null <<EOF
[Unit]
Description=Anai Translator (bundled frontend + backend)
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$DEPLOY_USER
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/bin/docker run --rm \\
  --name $SERVICE_NAME \\
  -p 127.0.0.1:$PORT:8000 \\
  -e ENVIRONMENT=production \\
  -e BACKEND_HOST=0.0.0.0 \\
  -e BACKEND_PORT=8000 \\
  -e SERVE_FRONTEND_DIST=1 \\
  -e FRONTEND_DIST_DIR=frontend/dist \\
  -e JWT_SECRET=$JWT_SECRET \\
  -e USERS=$USERS \\
  -e USER_TIERS=${APP_USERNAME}:free \\
  -e ALLOWED_ORIGINS=$ALLOWED_ORIGINS \\
  -e USE_GPU=0 \\
  -e WHISPER_DEVICE=cpu \\
  -e WHISPER_COMPUTE_TYPE=int8 \\
  -e WHISPER_MODEL_SIZE=small \\
  -e PRELOAD_MODELS=1 \\
  -e TRANSLATION_BACKEND=marian \\
  -e TRANSLATION_DEVICE=cpu \\
  -e HYBRID_ENABLE_MARIAN_FALLBACK=1 \\
  -e HYBRID_ENABLE_REMOTE=0 \\
  -e PREFER_CLOUD_TTS=0 \\
  -e STT_PROVIDER=local \\
  -e MAX_ACTIVE_STREAMS_PER_USER=5 \\
  -e REQUESTS_PER_MINUTE=120 \\
  -e QUOTA_REQUESTS_PER_HOUR=500 \\
  -e STT_MAX_CONCURRENCY=2 \\
  -v $DEPLOY_DIR/models:/app/models \\
  $IMAGE_TAG

ExecStop=/usr/bin/docker stop $SERVICE_NAME
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"
echo -e "${GREEN}✓ Systemd service created and started${NC}"
echo ""

echo -e "${YELLOW}Step 6: Wait for backend to be ready${NC}"
READY=0
for i in $(seq 1 90); do
  HEALTH="$(curl -s "http://127.0.0.1:${PORT}/health" 2>/dev/null || true)"
  if [[ -n "$HEALTH" ]] && health_ready "$HEALTH"; then
    echo -e "${GREEN}✓ Backend is ready (models loaded)${NC}"
    READY=1
    break
  fi
  if [[ -n "$HEALTH" ]]; then
    echo "  Warming up models... ($i/90)"
  else
    echo "  Waiting for health endpoint... ($i/90)"
  fi
  sleep 5
done
if [[ "$READY" -ne 1 ]]; then
  echo -e "${RED}Backend did not become ready in time. Check: sudo journalctl -u ${SERVICE_NAME} -n 100${NC}" >&2
  exit 1
fi

echo ""
echo -e "${YELLOW}Step 7: Configure Nginx reverse proxy${NC}"
sudo tee "/etc/nginx/sites-available/${SERVICE_NAME}" > /dev/null <<'NGINX_CONF'
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;

    client_max_body_size 100M;

    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    proxy_send_timeout 300s;

    location / {
        proxy_pass http://backend;
    }
}
NGINX_CONF

sudo ln -sf "/etc/nginx/sites-available/${SERVICE_NAME}" "/etc/nginx/sites-enabled/${SERVICE_NAME}"
sudo nginx -t
sudo systemctl restart nginx
echo -e "${GREEN}✓ Nginx reverse proxy configured${NC}"
echo ""

echo -e "${YELLOW}Step 8: Smoke test${NC}"
if python3 scripts/smoke_local.py "http://127.0.0.1:${PORT}"; then
  echo -e "${GREEN}✓ EN↔HT smoke test passed${NC}"
else
  echo -e "${RED}Smoke test failed${NC}" >&2
  exit 1
fi

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "App URL:     http://127.0.0.1:${PORT}/"
echo "Credentials: $CREDENTIALS_FILE"
echo "Login:       username=$APP_USERNAME"
echo ""
if [[ -n "$DOMAIN" && "$DOMAIN" != "translator.local" ]]; then
  echo "Next: run ./setup-https.sh $DOMAIN and update ALLOWED_ORIGINS to https://$DOMAIN"
else
  echo "Next: rerun with your domain — ./deploy.sh your-domain.com"
fi
echo "Logs: sudo journalctl -u ${SERVICE_NAME} -f"
