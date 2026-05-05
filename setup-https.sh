#!/bin/bash
# Set up HTTPS for Universal Translator backend using Let's Encrypt
# Usage: ./setup-https.sh your-domain.com

set -e

DOMAIN=$1
SERVICE_NAME="universal-translator"
NGINX_CONFIG="/etc/nginx/sites-available/$SERVICE_NAME"

if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <your-domain.com>"
  echo "Example: $0 translator.example.com"
  exit 1
fi

echo "=== Setting up HTTPS for $DOMAIN ==="
echo ""

# Step 1: Update Nginx config with domain
echo "Step 1: Updating Nginx configuration..."
sudo tee $NGINX_CONFIG > /dev/null <<EOF
upstream backend {
    server 127.0.0.1:8000;
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name $DOMAIN;
    
    location /.well-known/acme-challenge/ {
        root /var/www/certbot;
    }
    
    location / {
        return 301 https://\$server_name\$request_uri;
    }
}

# HTTPS server
server {
    listen 443 ssl http2;
    server_name $DOMAIN;
    
    # SSL certificates (will be created by certbot)
    ssl_certificate /etc/letsencrypt/live/$DOMAIN/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/$DOMAIN/privkey.pem;
    
    # SSL security settings
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;
    ssl_prefer_server_ciphers on;
    ssl_session_timeout 1d;
    ssl_session_cache shared:SSL:50m;
    ssl_stapling on;
    ssl_stapling_verify on;
    
    client_max_body_size 100M;
    
    # WebSocket support
    proxy_set_header Upgrade \$http_upgrade;
    proxy_set_header Connection "upgrade";
    proxy_set_header Host \$host;
    proxy_set_header X-Real-IP \$remote_addr;
    proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto \$scheme;
    
    # Timeouts for long-running requests
    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;
    proxy_send_timeout 300s;
    
    # CORS headers
    add_header 'Access-Control-Allow-Origin' '*' always;
    add_header 'Access-Control-Allow-Methods' 'GET, POST, OPTIONS' always;
    add_header 'Access-Control-Allow-Headers' 'Content-Type, Authorization' always;
    
    if (\$request_method = 'OPTIONS') {
        return 204;
    }
    
    location / {
        proxy_pass http://backend;
    }
}
EOF

sudo nginx -t

# Step 2: Request SSL certificate
echo "Step 2: Requesting SSL certificate from Let's Encrypt..."
sudo mkdir -p /var/www/certbot

# Install certbot if not already installed
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx

# Request certificate
sudo certbot certonly \
  --webroot \
  -w /var/www/certbot \
  -d $DOMAIN \
  --email admin@$DOMAIN \
  --agree-tos \
  --non-interactive \
  --rsa-key-size 4096

# Step 3: Reload Nginx with SSL config
echo "Step 3: Reloading Nginx with SSL..."
sudo systemctl reload nginx

# Step 4: Set up auto-renewal
echo "Step 4: Setting up certificate auto-renewal..."
sudo systemctl enable certbot.timer
sudo systemctl start certbot.timer

echo ""
echo "=== HTTPS Setup Complete ===" 
echo ""
echo "✓ SSL certificate installed for: $DOMAIN"
echo "✓ Auto-renewal configured (runs daily)"
echo "✓ HTTPS is now active at: https://$DOMAIN"
echo ""
echo "Test your setup:"
echo "  curl https://$DOMAIN/health"
echo "  curl https://$DOMAIN/docs"
echo ""
echo "Update your frontend VITE_API_URL to:"
echo "  https://$DOMAIN"
