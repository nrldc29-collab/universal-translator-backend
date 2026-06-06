# Railway Deployment

Deploy the bundled **English ↔ Haitian Creole** stack (frontend + FastAPI backend) from this repo using the root `Dockerfile`.

## Quick deploy

1. Create a Railway project and connect this GitHub repository.
2. Railway uses `railway.json` and builds the root `Dockerfile` (CPU, bundled `frontend/dist`, espeak-ng for HT TTS).
3. **Enable public access:** Service → **Settings** → **Networking** → **Generate Domain**. Copy the `https://….up.railway.app` URL (required for browser access; deploy can succeed before this step).
4. Generate production variables:

```powershell
powershell -ExecutionPolicy Bypass -File .\Get-Railway-Variables.ps1 -Username demo -FrontendOrigin https://YOUR-SERVICE.up.railway.app
```

Linux/macOS:

```bash
chmod +x Get-Railway-Variables.sh
./Get-Railway-Variables.sh demo "" https://YOUR-SERVICE.up.railway.app
```

5. Paste the output into Railway **Variables**. Replace `JWT_SECRET`, `USERS`, and set `ALLOWED_ORIGINS` to your service URL.
6. Deploy. Wait for `/health` to report `"ready": true`.

If you skip steps 4–5 on first deploy, Railway auto-bootstrap derives `JWT_SECRET`, `USERS`, and `ALLOWED_ORIGINS` when `RAILWAY_PUBLIC_DOMAIN` is available (login credentials are logged once in Railway deploy logs). After you **Generate Domain**, redeploy once or paste vars from `Get-Railway-Variables.sh`.

**Important:** Do not set `BACKEND_PORT` in Railway Variables — Railway injects `PORT` automatically. The app binds to `PORT`. Use `PRELOAD_MODELS=0` (default in Dockerfile) so the service passes healthchecks immediately; EN↔HT models download on the first translation request.

## Required variables

| Variable | Notes |
| --- | --- |
| `ENVIRONMENT` | `production` |
| `JWT_SECRET` | Strong random string (`python scripts/generate_secrets.py`) |
| `USERS` | `user:password` pairs |
| `ALLOWED_ORIGINS` | Your Railway URL, e.g. `https://your-app.up.railway.app` |
| `SERVE_FRONTEND_DIST` | `1` (set in Dockerfile) |
| `STT_PROVIDER` | `local` |
| `MAX_ACTIVE_STREAMS_PER_USER` | `5` (conversation uses 3 WebSockets) |
| `REQUESTS_PER_MINUTE` | `120` |
| `QUOTA_REQUESTS_PER_HOUR` | `500` |

`Get-Railway-Variables.ps1` emits the full recommended set.

## Post-deploy verification

From your machine (replace URL; only needs `pip install websockets` when testing a remote deploy):

```bash
python scripts/smoke_local.py https://YOUR-SERVICE.up.railway.app
# or
make smoke-production URL=https://YOUR-SERVICE.up.railway.app
```

Or locally before push:

```bash
make validate
make verify-all
```

Windows preflight (optional):

```powershell
powershell -ExecutionPolicy Bypass -File .\Test-DeploymentReady.ps1 -RunSmoke
```

Linux/macOS preflight:

```bash
make preflight-deploy
make preflight-deploy-live   # includes full EN↔HT smoke on :8000
```

## Notes

- **HT TTS** uses eSpeak (installed in the Docker image). Piper handles English.
- **GPU** is not used on Railway CPU builds; use `docker-compose.gpu.yml` or `Dockerfile.backend` for GPU hosts.
- **Mobile app**: set `EXPO_PUBLIC_API_URL` to your Railway HTTPS URL.

See also `docs/DEPLOYMENT_CHECKLIST.md`.
