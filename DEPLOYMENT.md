# Backend Deployment Guide

Your Universal Translator backend is ready for production deployment to `https://anai.wok`.

## Prerequisites

- Docker + Docker Compose installed
- GPU with NVIDIA drivers (for CUDA support)
- HTTPS/SSL certificate for `anai.wok`
- A server or cloud instance (AWS, Google Cloud, DigitalOcean, etc.)

## Option 1: Deploy on Your Own GPU Server

### Local Testing (Before Production)

```bash
# Build and run locally
docker-compose up --build

# Test the API
curl -X GET http://localhost:8000/docs  # Swagger UI
curl -X GET http://localhost:8000/health

# Test WebSocket
# Use your frontend at http://localhost:5173 or https://frontend-one-henna-99jlsna6ki.vercel.app
```

### Deploy to Production Server

1. **Copy code to server:**
   ```bash
   scp -r . user@anai.wok:/opt/universal-translator
   ssh user@anai.wok
   ```

2. **Set up on server:**
   ```bash
   cd /opt/universal-translator
   
   # Create models directory for caching
   mkdir -p models
   
   # Load environment variables
   export $(cat .env.production | xargs)
   
   # Build and run with GPU support
   docker-compose up -d
   
   # Check logs
   docker-compose logs -f backend
   ```

3. **Configure Reverse Proxy (Nginx)**
   
   Create `/etc/nginx/sites-available/anai.wok`:
   ```nginx
   upstream backend {
       server 127.0.0.1:8000;
   }
   
   server {
       listen 80;
       server_name anai.wok;
       
       # Redirect HTTP to HTTPS
       return 301 https://$server_name$request_uri;
   }
   
   server {
       listen 443 ssl http2;
       server_name anai.wok;
       
       # SSL certificates (use Let's Encrypt via certbot)
       ssl_certificate /etc/letsencrypt/live/anai.wok/fullchain.pem;
       ssl_certificate_key /etc/letsencrypt/live/anai.wok/privkey.pem;
       
       # WebSocket support
       proxy_set_header Upgrade $http_upgrade;
       proxy_set_header Connection "upgrade";
       proxy_set_header Host $host;
       proxy_set_header X-Real-IP $remote_addr;
       proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
       proxy_set_header X-Forwarded-Proto $scheme;
       
       # API timeout for large audio files
       proxy_read_timeout 300s;
       proxy_connect_timeout 75s;
       
       location / {
           proxy_pass http://backend;
       }
   }
   ```

4. **Enable Nginx:**
   ```bash
   sudo ln -s /etc/nginx/sites-available/anai.wok /etc/nginx/sites-enabled/
   sudo nginx -t
   sudo systemctl reload nginx
   ```

5. **Set up HTTPS with Let's Encrypt:**
   ```bash
   sudo apt-get install certbot python3-certbot-nginx
   sudo certbot certonly --nginx -d anai.wok
   ```

## Option 2: Cloud Deployment (AWS ECS / Google Cloud Run)

### AWS ECS with GPU
```bash
# Push Docker image to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin YOUR_ECR_URI
docker build -f Dockerfile.backend -t universal-translator-backend .
docker tag universal-translator-backend:latest YOUR_ECR_URI/universal-translator-backend:latest
docker push YOUR_ECR_URI/universal-translator-backend:latest

# Create ECS task definition with GPU support and deploy
# (Use AWS Console or CLI)
```

### Google Cloud Run (CPU - no GPU, lower cost)
```bash
# For CPU-only version (slower, but runs on Cloud Run)
gcloud builds submit --tag gcr.io/YOUR_PROJECT/universal-translator-backend
gcloud run deploy universal-translator-backend \
  --image gcr.io/YOUR_PROJECT/universal-translator-backend \
  --platform managed \
  --memory 4Gi \
  --timeout 3600 \
  --set-env-vars ENVIRONMENT=production,WHISPER_DEVICE=cpu,WHISPER_MODEL_SIZE=tiny
```

## Option 3: Docker Hub + VPS (Simple & Cheap)

1. Push to Docker Hub:
   ```bash
   docker build -f Dockerfile.backend -t YOUR_USERNAME/universal-translator:latest .
   docker push YOUR_USERNAME/universal-translator:latest
   ```

2. On VPS (Linode, DigitalOcean, Hetzner):
   ```bash
   # SSH into VPS
   ssh root@anai.wok
   
   # Install Docker
   curl -fsSL https://get.docker.com -o get-docker.sh
   sh get-docker.sh
   
   # Run container
   docker run -d \
     -p 8000:8000 \
     -e ENVIRONMENT=production \
     -e USE_GPU=1 \
     --gpus all \
     --restart unless-stopped \
     YOUR_USERNAME/universal-translator:latest
   ```

## Verify Deployment

Once deployed, test these endpoints:

```bash
# Health check
curl -X GET https://anai.wok/health

# Swagger API docs
curl -X GET https://anai.wok/docs

# Test WebSocket (from your frontend)
# The frontend will auto-connect to wss://anai.wok/ws/audio
```

## Performance Tuning

### For High Concurrency
```bash
# Increase worker count and concurrency
STT_MAX_CONCURRENCY=4      # Up from 2
WHISPER_BEAM_SIZE=5        # Better accuracy, slower
```

### For Low Latency
```bash
WHISPER_MODEL_SIZE=tiny    # Fastest
WHISPER_COMPUTE_TYPE=int8  # Quantized
STT_MAX_CONCURRENCY=1      # Single request at a time
```

### For Cost Optimization (CPU-only)
```bash
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_MODEL_SIZE=tiny
```

## Monitoring

```bash
# Monitor CPU/GPU/Memory
docker stats

# View logs
docker-compose logs -f backend

# Check WebSocket connections
# Monitor /ws/audio endpoint via your frontend UI
```

## Security

- Always use HTTPS (configured above with Let's Encrypt)
- Set `ALLOWED_ORIGINS` to only your frontend domain
- Use environment variables for sensitive config (not in code)
- Keep Docker images updated

## Next Steps

1. **Choose deployment option** (self-hosted, cloud, or VPS)
2. **Set up domain** `anai.wok` to point to your server
3. **Deploy** using the steps above
4. **Test** from your frontend at https://frontend-one-henna-99jlsna6ki.vercel.app
5. **Monitor** logs and metrics

Questions? Check the backend API docs at `https://anai.wok/docs` once deployed.
