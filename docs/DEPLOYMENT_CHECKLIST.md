# Deployment Checklist

## Pre-deploy: environment variables

- [ ] Copy `.env.example` to `.env` or configure equivalent platform env vars.
- [ ] Set `ENVIRONMENT=production` (server refuses to start without this when secrets are unsafe).
- [ ] Set `JWT_SECRET` to a strong random 64+ character string — run: `python scripts/generate_secrets.py`.
- [ ] Set `USERS` to real credentials **or** set `DATA_DIR` and seed users via `POST /admin/users`.
- [ ] Set `ALLOWED_ORIGINS` to your deployed frontend origin(s) — placeholder example.com is rejected.
- [ ] Set `ADMIN_IDENTITIES` (comma-separated usernames) to protect the `/admin/users` routes.
- [ ] Set `DATA_DIR=data` to enable SQLite persistence for quotas and users across restarts.
- [ ] Set `GOOGLE_TTS_API_KEY` if you want neural TTS voices (optional — Piper/eSpeak otherwise).
- [ ] Set `CIP_PROCESS_URL` if running the AI Comm System brain for ambiguity resolution (optional).
- [ ] Set `MAX_ACTIVE_STREAMS_PER_USER=5`, `REQUESTS_PER_MINUTE=120`, `QUOTA_REQUESTS_PER_HOUR=500` for EN↔HT conversation mode.

## Pre-deploy: scaling and GPU

- [ ] Keep `WORKERS=1` if `USE_GPU=1` — GPU models cannot be shared across OS processes.
- [ ] Scale horizontally with multiple containers/replicas rather than increasing `WORKERS`.
- [ ] Each worker/replica loads its own model copy — ensure sufficient RAM/VRAM.

## Pre-deploy: mobile app (before app store submission)

- [ ] Replace `replace-with-your-eas-project-id` in `translator-mobile/app.json` with your EAS project ID.
- [ ] Update `ios.bundleIdentifier` and `android.package` if you use a custom domain (currently `com.anaitranslator.app`).
- [ ] Set `EXPO_PUBLIC_API_URL` in `translator-mobile/.env` to your production backend URL.
- [ ] Update `eas.json` submit block with your Apple ID, Team ID, and Google service account key.

## Build validation

- [ ] `make release-ready` (validate + verify-all + deploy preflight — run before tagging or Railway deploy)
- [ ] `make validate` (pytest + frontend build + mobile lint)
- [ ] `make verify-all` (offline imports + bundled production smoke)
- [ ] `make preflight-deploy` (Railway/Docker production file checks)
- [ ] `python -m py_compile backend/api.py backend/store.py backend/security.py backend/config.py`

## Post-deploy checks

- [ ] `GET /health` returns `status: ok` and the expected release ID.
- [ ] `GET /ready` shows model readiness, `espeak_available: true`, and STT provider reachable.
- [ ] `python scripts/smoke_local.py https://YOUR-SERVICE-URL` passes (full EN↔HT smoke; remote URL needs only `websockets` installed)
- [ ] Or: `make smoke-production URL=https://YOUR-SERVICE-URL`
- [ ] Or: GitHub Actions → **Production smoke** workflow (enter your deployed URL)
- [ ] `GET /diagnostics` shows:
  - `translation.remote_translator_reachable: true`
  - `persistence.quota_store_available: true` (when `DATA_DIR` set)
  - `cip.reachable: true` (when CIP brain configured)
- [ ] `POST /login` returns a JWT for a real user credential.
- [ ] Browser microphone permission works over HTTPS.
- [ ] WebSocket streaming reaches `/ws/audio`.
- [ ] TTS audio plays on web and mobile (HT uses eSpeak when no Piper voice).
- [ ] `GET /admin/users` returns 403 without admin JWT (not 500).

See also `RAILWAY-DEPLOY.md` for Railway-specific steps.
