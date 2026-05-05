# Railway Backend Deployment

This repo is ready for Railway using the root `Dockerfile`.

## Deploy From GitHub

1. Push this repository to GitHub.
2. Open https://railway.app
3. Create a new project.
4. Choose **Deploy from GitHub repo**.
5. Select this repo.
6. After the first successful deploy, open the service **Settings** tab.
7. In **Networking**, click **Generate Domain**.

Railway injects a `PORT` variable automatically. The backend now reads that
variable and binds to `0.0.0.0`, so no manual port wiring is needed.

## Required Variables

Set these in Railway service variables:

```text
ENVIRONMENT=production
USE_GPU=0
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPER_MODEL_SIZE=tiny
GPU_COST_MODE=low
ALLOWED_ORIGINS=https://frontend-one-henna-99jlsna6ki.vercel.app,http://localhost:5173,http://127.0.0.1:5173
JWT_SECRET=replace-with-a-long-random-secret
USERS=demo:replace-with-a-real-password
USER_TIERS=demo:free
```

## Verify

After Railway generates a domain:

```powershell
Invoke-WebRequest https://YOUR-RAILWAY-DOMAIN.up.railway.app/health
```

Then update `frontend/vercel.json`:

```json
{
  "env": {
    "VITE_API_URL": "https://YOUR-RAILWAY-DOMAIN.up.railway.app",
    "VITE_WS_AUDIO_URL": "wss://YOUR-RAILWAY-DOMAIN.up.railway.app/ws/audio"
  }
}
```

Redeploy the frontend so the PWA talks to the online backend.
