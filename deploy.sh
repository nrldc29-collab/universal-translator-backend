#!/bin/bash
# Universal Translator Backend Deployment Script
# Run this on your Linux server to deploy the backend

set -e  # Exit on error

echo "=== Universal Translator Backend Deployment ==="
echo ""

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
DEPLOY_DIR="/opt/universal-translator"
SERVICE_NAME="universal-translator"
DOMAIN="${1:-translator.local}"
PORT=8000

echo -e "${YELLOW}Step 1: Update system packages${NC}"
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get install -y \
  curl \
  wget \
  git \
  docker.io \
  docker-compose \
  certbot \
  nginx \
  htop

echo -e "${GREEN}✓ System packages installed${NC}"
echo ""

echo -e "${YELLOW}Step 2: Start Docker daemon${NC}"
sudo systemctl start docker
sudo systemctl enable docker
sudo usermod -aG docker $USER

echo -e "${GREEN}✓ Docker is running${NC}"
echo ""

echo -e "${YELLOW}Step 3: Clone/copy repository${NC}"
if [ ! -d "$DEPLOY_DIR" ]; then
  # If you want to clone from GitHub:
  # sudo git clone https://github.com/YOUR_USERNAME/universal-translator.git $DEPLOY_DIR
  
  # Or copy from local:
  if [ -d "./universal-translator" ]; then
    sudo cp -r ./universal-translator $DEPLOY_DIR
  else
    echo -e "${RED}Error: Could not find repository.${NC}"
    echo "Please either:"
    echo "  1. Uncomment git clone in this script and provide your repo URL"
    echo "  2. Copy the universal-translator directory to this server first"
    exit 1
  fi
fi

sudo chown -R $USER:$USER $DEPLOY_DIR
cd $DEPLOY_DIR

echo -e "${GREEN}✓ Repository ready at $DEPLOY_DIR${NC}"
echo ""

echo -e "${YELLOW}Step 4: Build Docker image${NC}"
sudo docker build -f Dockerfile.backend -t universal-translator-backend:latest .

echo -e "${GREEN}✓ Docker image built${NC}"
echo ""

echo -e "${YELLOW}Step 5: Create systemd service${NC}"
sudo tee /etc/systemd/system/$SERVICE_NAME.service > /dev/null <<EOF
[Unit]
Description=Universal Translator Backend
After=docker.service
Requires=docker.service

[Service]
Type=simple
User=$USER
WorkingDirectory=$DEPLOY_DIR
ExecStart=/usr/bin/docker run --rm \\
  --name $SERVICE_NAME \\
  -p 127.0.0.1:$PORT:8000 \\
  -e ENVIRONMENT=production \\
  -e BACKEND_HOST=0.0.0.0 \\
  -e BACKEND_PORT=8000 \\
  -e USE_GPU=0 \\
  -e WHISPER_DEVICE=cpu \\
  -e WHISPER_COMPUTE_TYPE=int8 \\
  -e WHISPER_MODEL_SIZE=tiny \\
  -e STT_MAX_CONCURRENCY=1 \\
  -v $DEPLOY_DIR/models:/app/models \\
  universal-translator-backend:latest

ExecStop=/usr/bin/docker stop $SERVICE_NAME
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable $SERVICE_NAME
sudo systemctl start $SERVICE_NAME

echo -e "${GREEN}✓ Systemd service created and started${NC}"
echo ""

echo -e "${YELLOW}Step 6: Wait for backend to be ready${NC}"
for i in {1..30}; do
  if curl -f http://127.0.0.1:$PORT/health 2>/dev/null > /dev/null; then
    echo -e "${GREEN}✓ Backend is healthy${NC}"
    break
  fi
  echo "  Waiting... ($i/30)"
  sleep 2
done

echo ""
echo -e "${YELLOW}Step 7: Configure Nginx reverse proxy${NC}"
sudo tee /etc/nginx/sites-available/$SERVICE_NAME > /dev/null <<'NGINX_CONF'
upstream backend {
    server 127.0.0.1:8000;
}

server {
    listen 80;
    server_name _;
    
    client_max_body_size 100M;
    
    # WebSocket support
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    
    # Timeouts for long-running requests (audio processing)
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    proxy_send_timeout 300s;
    
    location / {
        proxy_pass http://backend;
    }
}
NGINX_CONF

sudo ln -sf /etc/nginx/sites-available/$SERVICE_NAME /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx

echo -e "${GREEN}✓ Nginx reverse proxy configured${NC}"
echo ""

echo -e "${YELLOW}Step 8: Test backend${NC}"
HEALTH=$(curl -s http://127.0.0.1:$PORT/health)
echo "Health check: $HEALTH"

echo ""
echo -e "${GREEN}=== Deployment Complete ===${NC}"
echo ""
echo "Backend is running on:"
echo "  Local: http://127.0.0.1:$PORT"
echo "  Via Nginx: http://localhost"
echo ""
echo "Next steps:"
echo "1. Set up your domain/HTTPS"
echo "2. Update frontend VITE_API_URL to point to your server"
echo "3. Monitor logs: sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "View API docs at: http://YOUR_SERVER_IP/docs"
