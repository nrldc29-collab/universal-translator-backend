# 🚀 Deploy Universal Translator Backend to Your Linux Server

This guide will get your backend running on your own Linux server with HTTPS in ~10 minutes.

## 📋 Prerequisites

- Linux server (Ubuntu 20.04+, Debian, CentOS)
- Root or sudo access
- Docker installed (we'll install it for you)
- Static IP or dynamic DNS for your server
- (Optional) Domain name for HTTPS

## ⚡ Quick Start (5 minutes)

### 1. Copy the code to your server

```bash
# From your local machine
scp -r universal-translator/ root@YOUR_SERVER_IP:/opt/

# Or if you have SSH key:
scp -r universal-translator/ -i ~/.ssh/id_rsa user@YOUR_SERVER_IP:/home/user/
```

### 2. SSH into your server

```bash
ssh root@YOUR_SERVER_IP
# or
ssh -i ~/.ssh/id_rsa user@YOUR_SERVER_IP
```

### 3. Run the deployment script

```bash
cd universal-translator
chmod +x deploy.sh
./deploy.sh
```

This script will:
- ✅ Install Docker, Nginx, Certbot
- ✅ Build the backend Docker image
- ✅ Start the backend service
- ✅ Configure Nginx reverse proxy
- ✅ Set up auto-restart

**Done!** Your backend is now running at `http://YOUR_SERVER_IP`

### 4. Set up HTTPS (optional but recommended)

If you have a domain name:

```bash
chmod +x setup-https.sh
./setup-https.sh your-domain.com
```

This will:
- ✅ Request a free SSL certificate from Let's Encrypt
- ✅ Configure Nginx for HTTPS
- ✅ Set up auto-renewal (runs daily)

Now your backend is at `https://your-domain.com`

## 📊 Verify Deployment

Test your backend:

```bash
# Health check
curl http://YOUR_SERVER_IP/health

# Full API docs (interactive)
curl http://YOUR_SERVER_IP/docs

# Test WebSocket (requires frontend connection)
# Go to https://frontend-one-henna-99jlsna6ki.vercel.app
# Update VITE_API_URL to http://YOUR_SERVER_IP (or https://your-domain.com)
```

## 🔧 Configuration Options

Edit the environment variables in `deploy.sh` to customize:

```bash
# CPU performance (currently set for CPU-only to reduce costs)
USE_GPU=0                    # Set to 1 if your server has NVIDIA GPU
WHISPER_DEVICE=cpu           # or cuda for GPU
WHISPER_MODEL_SIZE=tiny      # tiny (fastest), base, small, medium, large

# Concurrency
STT_MAX_CONCURRENCY=1        # How many requests to process in parallel
WHISPER_BEAM_SIZE=1          # 1 (fast), 5 (accurate)
```

Edit these in `deploy.sh` before running the deployment.

## 📝 Update Frontend

Once your backend is running, update the frontend to point to your server:

**Option 1: Use the production frontend on Vercel**
1. Go to your Vercel project: https://vercel.com/dashboard
2. Select the `frontend` project
3. Go to Settings → Environment Variables
4. Add: `VITE_API_URL=http://YOUR_SERVER_IP` (or `https://your-domain.com`)
5. Redeploy

**Option 2: Run frontend locally against your server**
```bash
# Edit frontend/vercel.local.json
{
  "env": {
    "VITE_API_URL": "http://YOUR_SERVER_IP"
  }
}

# Then run
cd frontend
npm run dev
# Visit http://localhost:5173
```

## 📊 Monitoring & Logs

```bash
# View backend logs in real-time
sudo journalctl -u universal-translator -f

# Check if service is running
sudo systemctl status universal-translator

# View resource usage
docker stats

# Check Nginx logs
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

## 🚨 Troubleshooting

### Backend not starting?
```bash
# Check service status
sudo systemctl status universal-translator

# View logs
sudo journalctl -u universal-translator -n 50

# Restart service
sudo systemctl restart universal-translator
```

### Port already in use?
```bash
# Find what's using port 8000
sudo lsof -i :8000

# Or change port in deploy.sh and rerun
```

### HTTPS certificate not working?
```bash
# Check certificate status
sudo certbot certificates

# Manually renew
sudo certbot renew

# Check Nginx config
sudo nginx -t
```

### Frontend can't connect to backend?

1. Check backend is running: `curl http://YOUR_SERVER_IP/health`
2. Check Nginx is running: `sudo systemctl status nginx`
3. Check firewall allows port 80/443:
   ```bash
   sudo ufw allow 80
   sudo ufw allow 443
   sudo ufw allow 8000
   ```
4. Update frontend `VITE_API_URL` to your server IP

## 🔒 Security

### Firewall (UFW)
```bash
# Allow HTTP/HTTPS only
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp  # SSH
sudo ufw enable
```

### Update regularly
```bash
sudo apt-get update
sudo apt-get upgrade
```

### Check logs for attacks
```bash
sudo tail -f /var/log/nginx/access.log | grep "POST\|PUT\|DELETE"
```

## 📈 Performance Tuning

### For faster inference (CPU)
```bash
WHISPER_MODEL_SIZE=tiny      # Fastest
WHISPER_COMPUTE_TYPE=int8    # Quantized
STT_MAX_CONCURRENCY=1        # Single request
```

### For better accuracy (slower)
```bash
WHISPER_MODEL_SIZE=base      # Good balance
WHISPER_COMPUTE_TYPE=float16 # If GPU available
STT_MAX_CONCURRENCY=2        # Process 2 at a time
WHISPER_BEAM_SIZE=5          # More accurate
```

### For high concurrency
```bash
STT_MAX_CONCURRENCY=4        # Process 4 simultaneously
# Requires good CPU/GPU and more RAM
```

## 🆘 Support

Check the main [DEPLOYMENT.md](./DEPLOYMENT.md) for more options and details.

---

**You're ready to go!** Once the backend is deployed, your frontend will automatically connect and start translating audio in real-time. 🎉
