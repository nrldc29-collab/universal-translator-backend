# Railway Backend Deployment

This repo is ready for Railway using the root `Dockerfile`. The Docker build
now bundles `frontend/dist` into the FastAPI service, so the generated Railway
domain can open the PWA directly and also host the backend API/WebSocket routes.

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

After Railway generates a domain, the main app opens at the same URL:

```text
https://YOUR-RAILWAY-DOMAIN.up.railway.app
```

The browser will use:

```text
wss://YOUR-RAILWAY-DOMAIN.up.railway.app/ws/audio
```

for live audio because Railway serves the page over HTTPS.

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

If you only use the bundled Railway URL and not a separate Vercel frontend, you
can leave `ALLOWED_ORIGINS` unset.

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

If you are using the single Railway URL, skip the Vercel step and run:

```powershell
.\Test-Translator.ps1 -BaseUrl https://YOUR-RAILWAY-DOMAIN.up.railway.app
```
