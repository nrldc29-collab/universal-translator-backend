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

If this local repo is not pushed yet, create an empty GitHub repository named
`universal-translator`, then run:

```powershell
.\Publish-To-GitHub.ps1 -RepoUrl https://github.com/YOURNAME/universal-translator.git
```

If Git opens a browser sign-in window, finish the sign-in and rerun the command
if needed.

Before pushing or deploying, run:

```powershell
.\Test-DeploymentReady.ps1 -RunSmoke
```

This checks Git state, ignored secrets, Railway files, production frontend
serving, same-origin `wss://` support, generated variables, and the local app.

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

Generate fresh Railway variables with:

```powershell
.\Get-Railway-Variables.ps1
```

Paste the output into the Railway service **Variables** tab.

If you only use the bundled Railway URL and not a separate Vercel frontend, you
can leave `ALLOWED_ORIGINS` unset.

If you also deploy a separate Vercel frontend, generate variables with that
origin included:

```powershell
.\Get-Railway-Variables.ps1 -FrontendOrigin https://YOUR-VERCEL-APP.vercel.app
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

If you are using the single Railway URL, skip the Vercel step and run:

```powershell
.\Test-Translator.ps1 -BaseUrl https://YOUR-RAILWAY-DOMAIN.up.railway.app
```
