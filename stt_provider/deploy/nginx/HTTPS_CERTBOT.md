# HTTPS/WSS setup with Nginx and Certbot

This guide assumes:

- Your app is running on the VPS at port `8000` 
- Nginx is installed
- Your DNS `A` record points your domain to the VPS
- You have replaced `your-domain.com` in `deploy/nginx/stt-provider.conf` 

## 1. Install Nginx and Certbot

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx
```

## 2. Copy the Nginx config

Replace your-domain.com with your real domain first.

```bash
sudo cp deploy/nginx/stt-provider.conf /etc/nginx/sites-available/stt-provider.conf
sudo ln -sf /etc/nginx/sites-available/stt-provider.conf /etc/nginx/sites-enabled/stt-provider.conf
sudo nginx -t
sudo systemctl reload nginx
```

## 3. Issue the HTTPS certificate

Replace your-domain.com with your real domain.

```bash
sudo certbot --nginx -d your-domain.com
```

Choose the redirect-to-HTTPS option when prompted.

## 4. Verify HTTPS

```bash
curl https://your-domain.com/health
```

Expected response:

```json
{
  "status": "ok"
}
```

## 5. Use secure WebSocket from the browser client

Use:

```
wss://your-domain.com/stt/stream
```

not:

```
ws://your-domain.com/stt/stream
```

## 6. Renewals

Certbot installs automatic renewal on most Ubuntu systems.

Verify:

```bash
sudo certbot renew --dry-run
```
