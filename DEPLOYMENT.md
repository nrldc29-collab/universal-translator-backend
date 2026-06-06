# Anai Translator — Deployment Guide

This is the single, authoritative deployment guide for the Anai Translator
backend (FastAPI + WebSocket) and the optional Hugging Face Spaces demo
(`hf-space/`).

It covers, in order:

1. [Choosing a target](#choosing-a-target)
2. [Hugging Face Spaces](#hugging-face-spaces-free-demo)
3. [Railway](#railway-managed-docker-host)
4. [Your own Linux server](#your-own-linux-server)
5. [Google Cloud Run](#google-cloud-run-serverless-cpu)
6. [AWS ECS with GPU](#aws-ecs-with-gpu)
7. [Reverse proxy, HTTPS, and CORS](#reverse-proxy-https-and-cors)
8. [Verification](#verification)
9. [Performance tuning](#performance-tuning)
10. [Troubleshooting](#troubleshooting)

## Choosing a target

| Target | Cost | Time | Always-on | GPU | WebSocket |
| --- | --- | --- | --- | --- | --- |
| HF Spaces (Gradio demo) | Free | 5 min | No (sleeps) | Paid upgrade | Limited |
| Railway | Free → $5–20/mo | 5 min | Yes | Limited | Yes |
| DigitalOcean / Hetzner / Linode (`deploy.sh`) | $3–50/mo | 15 min | Yes | Yes (GPU droplet) | Yes |
| Google Cloud Run | Free tier → pay-per-use | 10 min | Cold starts | No | Yes |
| AWS ECS + GPU | Pay-per-use | 30 min | Yes | Yes | Yes |

Recommendations:

- For a quick public demo: **Hugging Face Spaces** (Gradio).
- For real production with WebSocket streaming: **Railway** or a **GPU VPS**.
- For maximum control or custom hardware: **your own Linux server**.

## Hugging Face Spaces (free demo)

The `hf-space/` folder is a self-contained Gradio app for English↔Haitian Creole
speech and text translation. It is the only artifact you need for HF Spaces.

### Option A: deploy in the browser

1. Go to <https://huggingface.co/spaces> and create a new Space.
2. Name: `anai-translator`. SDK: **Gradio**. Hardware: free CPU is fine.
3. In the Files tab, upload everything in `hf-space/`:
   - `app.py`
   - `requirements.txt`
   - `packages.txt`
   - `README.md`
4. Commit and wait for the build (first run downloads models — a few minutes).

### Option B: deploy from this machine

Create a Hugging Face write token at
<https://huggingface.co/settings/tokens>, then run from the repo root:

```powershell
$env:HF_TOKEN = "hf_your_write_token_here"
./deploy-hf-space.ps1 -SpaceId "YOUR_USERNAME/anai-translator"
```

Add `-Private` to make the Space private.

### What the Space supports

- Record/upload audio, transcribe with `faster-whisper` (tiny, CPU).
- Translate English↔Haitian Creole via NLLB-200 (CPU).
- Runs on the free CPU tier.

### What the Space does NOT do

- No WebSocket streaming, no Piper TTS, no auth/quotas, no NAIA assistant.
- Do not point the Vite frontend at the Gradio Space — the frontend expects
  the FastAPI routes in `backend/api.py`.

## Railway (managed Docker host)

The repo's root `Dockerfile` is a multi-stage build that compiles
`frontend/dist` and bakes it into the FastAPI image, so a single Railway
service serves both the PWA and the API.

1. Push the repo to GitHub (use `./Publish-To-GitHub.ps1 -RepoUrl …` if you
   have not pushed yet).
2. Open <https://railway.app>, create a project, and choose **Deploy from
   GitHub repo**.
3. After the first deploy, open **Settings → Networking → Generate Domain**.

Railway injects `PORT`; the backend reads it and binds to `0.0.0.0`. No manual
port wiring needed.

### Required variables

Generate variables with `./Get-Railway-Variables.ps1` and paste them into
**Variables** in the Railway service. See also `RAILWAY-DEPLOY.md` for the
full Railway checklist (quota limits, post-deploy smoke).

Required for EN↔HT conversation mode:

```bash
MAX_ACTIVE_STREAMS_PER_USER=5
REQUESTS_PER_MINUTE=120
QUOTA_REQUESTS_PER_HOUR=500
STT_PROVIDER=local
```

If you keep both the frontend and backend on the Railway URL, you can leave
`ALLOWED_ORIGINS` unset. If you also deploy a separate Vercel/Netlify
frontend, include its origin:

```powershell
./Get-Railway-Variables.ps1 -FrontendOrigin https://YOUR-VERCEL-APP.vercel.app
```

### Pre-flight check

Before pushing or deploying, run:

```powershell
./Test-DeploymentReady.ps1 -RunSmoke
```

Linux/macOS:

```bash
make preflight-deploy
make preflight-deploy-live   # includes full EN↔HT smoke on :8000
```

This validates Railway files, production frontend serving, same-origin
`wss://` support, quota defaults in the Dockerfile, and the local smoke suite.

### After deploy

```bash
python scripts/smoke_local.py https://YOUR-RAILWAY-DOMAIN.up.railway.app
```

Or on Windows:

```powershell
./Test-Translator.ps1 -BaseUrl https://YOUR-RAILWAY-DOMAIN.up.railway.app
```

Quick health check:

```powershell
Invoke-WebRequest https://YOUR-RAILWAY-DOMAIN.up.railway.app/health
```

If you also use a separate frontend host, update `frontend/vercel.json` with
the Railway URL and redeploy the frontend; otherwise visit the Railway URL
directly.

## Your own Linux server

For a self-hosted deploy (DigitalOcean, Hetzner, Linode, bare metal — anything
running Ubuntu 20.04+ or Debian), use the bundled `deploy.sh`.

```bash
# 1. Copy the repo to the server
scp -r anai-translator/ user@YOUR_SERVER_IP:/opt/

# 2. SSH in
ssh user@YOUR_SERVER_IP
cd /opt/anai-translator

# 3. Run the deploy script
chmod +x deploy.sh
./deploy.sh
```

`deploy.sh` installs Docker, Nginx, and Certbot, builds the backend image,
starts the service, configures the Nginx reverse proxy, and sets up
auto-restart.

### Set up HTTPS

Once the service is running and DNS resolves to your server:

```bash
chmod +x setup-https.sh
./setup-https.sh your-domain.com
```

This requests a Let's Encrypt certificate, configures HTTPS on Nginx, and
enables automatic renewal.

### Update the frontend

Point the frontend at your backend by setting `VITE_API_URL`:

- **Vercel/Netlify:** add `VITE_API_URL=https://your-domain.com` in the
  environment variables and redeploy.
- **Local dev:** edit `frontend/vercel.local.json` and run
  `npm run dev` in `frontend/`.

### Configuration knobs

Edit `deploy.sh` (or your service's environment variables) before deploy:

```bash
USE_GPU=0                  # 1 if the host has an NVIDIA GPU
WHISPER_DEVICE=cpu         # or "cuda"
WHISPER_MODEL_SIZE=tiny    # tiny | base | small | medium | large
WHISPER_COMPUTE_TYPE=int8  # float16 on GPU, int8 on CPU
STT_MAX_CONCURRENCY=1      # parallel STT requests
WHISPER_BEAM_SIZE=1        # 1 (fast) — 5 (accurate)
MAX_ACTIVE_STREAMS_PER_USER=5
REQUESTS_PER_MINUTE=120
QUOTA_REQUESTS_PER_HOUR=500
STT_PROVIDER=local
```

## Google Cloud Run (serverless, CPU)

CPU-only deploy that scales to zero. Good for low-volume demos.

```bash
gcloud builds submit --tag gcr.io/YOUR_PROJECT/anai-translator-backend
gcloud run deploy anai-translator-backend \
  --image gcr.io/YOUR_PROJECT/anai-translator-backend \
  --platform managed \
  --memory 4Gi \
  --timeout 3600 \
  --set-env-vars ENVIRONMENT=production,WHISPER_DEVICE=cpu,WHISPER_MODEL_SIZE=tiny
```

Trade-offs: cold starts, no GPU, no persistent in-process state for long
WebSocket sessions.

## AWS ECS with GPU

```bash
# Build and push to ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin YOUR_ECR_URI
docker build -f Dockerfile.backend -t anai-translator-backend .
docker tag anai-translator-backend:latest \
  YOUR_ECR_URI/anai-translator-backend:latest
docker push YOUR_ECR_URI/anai-translator-backend:latest
```

Create an ECS task definition with GPU resources and a service in front of an
ALB. Use the ALB for HTTPS termination and WebSocket support (`Upgrade` /
`Connection` headers must be forwarded).

## Reverse proxy, HTTPS, and CORS

Minimum Nginx config for the FastAPI service (WebSocket-aware):

```nginx
upstream backend { server 127.0.0.1:8000; }

server {
    listen 80;
    server_name your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com;

    ssl_certificate     /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;

    proxy_set_header Upgrade           $http_upgrade;
    proxy_set_header Connection        "upgrade";
    proxy_set_header Host              $host;
    proxy_set_header X-Real-IP         $remote_addr;
    proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;

    proxy_read_timeout 300s;
    proxy_connect_timeout 75s;

    location / { proxy_pass http://backend; }
}
```

Then on Ubuntu:

```bash
sudo apt-get install certbot python3-certbot-nginx
sudo certbot certonly --nginx -d your-domain.com
```

### CORS / ALLOWED_ORIGINS

Set `ALLOWED_ORIGINS` to the exact origin(s) of your frontend:

```bash
ALLOWED_ORIGINS=https://your-frontend.example.com,https://app.your-domain.com
```

If frontend and backend share a host (Railway, single-VPS), this can be left
unset.

## Verification

```bash
curl https://your-backend-url/health
curl https://your-backend-url/ready    # confirm espeak_available for HT TTS
curl https://your-backend-url/docs      # interactive Swagger UI
```

Full EN↔HT smoke (auth, translate, WebSocket, conversation triple-socket):

```bash
python scripts/smoke_local.py https://your-backend-url
```

Manual translate check (login first, or use demo credentials from `USERS`):

```bash
TOKEN=$(curl -s -X POST https://your-backend-url/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"demo","password":"demo"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl -X POST https://your-backend-url/translate/text \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"text":"I need help","source_language":"en","target_language":"ht"}'
```

Windows wrapper:

```powershell
./Test-Translator.ps1 -BaseUrl https://your-backend-url
```

## Performance tuning

### Low latency

```bash
WHISPER_MODEL_SIZE=tiny
WHISPER_COMPUTE_TYPE=int8
STT_MAX_CONCURRENCY=1
WHISPER_BEAM_SIZE=1
```

### Better accuracy

```bash
WHISPER_MODEL_SIZE=base
WHISPER_COMPUTE_TYPE=float16   # GPU only
WHISPER_BEAM_SIZE=5
STT_MAX_CONCURRENCY=2
```

### High concurrency

```bash
STT_MAX_CONCURRENCY=4
```

Requires more RAM and a capable CPU or GPU.

## Troubleshooting

### Service won't start

```bash
sudo systemctl status anai-translator
sudo journalctl -u anai-translator -n 100
sudo systemctl restart anai-translator
```

### Port 8000 already in use

```bash
sudo lsof -i :8000
```

Pick a different port in `deploy.sh` and rerun.

### HTTPS cert errors

```bash
sudo certbot certificates
sudo certbot renew
sudo nginx -t
```

### Frontend can't reach backend

1. `curl https://your-backend-url/health` — does the backend respond?
2. `sudo systemctl status nginx` — proxy up?
3. Firewall:
   ```bash
   sudo ufw allow 80/tcp
   sudo ufw allow 443/tcp
   ```
4. Verify `VITE_API_URL` in the frontend matches the backend origin.
5. Check `ALLOWED_ORIGINS` includes the frontend origin.

### Logs

```bash
docker compose logs -f backend
docker stats
sudo tail -f /var/log/nginx/error.log
sudo tail -f /var/log/nginx/access.log
```

---

For backend internals see `docs/BACKEND.md`. For API surface see
`docs/API.md`. For environment variables see `docs/ENVIRONMENT.md`.
