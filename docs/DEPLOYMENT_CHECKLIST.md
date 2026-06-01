# Deployment Checklist

## Pre-deploy: environment variables

- [ ] Copy \.env.example\ to \.env\ or configure equivalent platform env vars.
- [ ] Set ENVIRONMENT=production (server refuses to start without this when secrets are unsafe).
- [ ] Set JWT_SECRET to a strong random 64+ character string — run: python scripts/generate_secrets.py.
- [ ] Set USERS to real credentials **or** set DATA_DIR and seed users via POST /admin/users.
- [ ] Set ALLOWED_ORIGINS to your deployed frontend origin(s) — placeholder example.com is rejected.
- [ ] Set ADMIN_IDENTITIES (comma-separated usernames) to protect the /admin/users routes.
- [ ] Set DATA_DIR=data to enable SQLite persistence for quotas and users across restarts.
- [ ] Set GOOGLE_TTS_API_KEY if you want neural TTS voices (optional — Piper/eSpeak otherwise).
- [ ] Set CIP_PROCESS_URL if running the AI Comm System brain for ambiguity resolution (optional).

## Pre-deploy: scaling and GPU

- [ ] Keep WORKERS=1 if USE_GPU=1 — GPU models cannot be shared across OS processes.
- [ ] Scale horizontally with multiple containers/replicas rather than increasing WORKERS.
- [ ] Each worker/replica loads its own model copy — ensure sufficient RAM/VRAM.

## Pre-deploy: mobile app (before app store submission)

- [ ] Replace 
eplace-with-your-eas-project-id in 	ranslator-mobile/app.json with your EAS project ID.
- [ ] Update ios.bundleIdentifier and ndroid.package if you use a custom domain (currently com.anaitranslator.app).
- [ ] Set EXPO_PUBLIC_API_URL in 	ranslator-mobile/.env to your production backend URL.
- [ ] Update eas.json submit block with your Apple ID, Team ID, and Google service account key.

## Build validation

- [ ] python -m pytest tests/
- [ ] 
pm --prefix frontend run build
- [ ] 
pm --prefix translator-mobile run lint
- [ ] python -m py_compile backend/api.py backend/store.py backend/security.py backend/config.py

## Post-deploy checks

- [ ] GET /health returns status: ok and the expected 
elease ID.
- [ ] GET /ready shows model readiness and STT provider reachable (if streaming mode).
- [ ] GET /diagnostics shows:
  - 	ranslation.remote_translator_reachable: true
  - persistence.quota_store_available: true (when DATA_DIR set)
  - cip.reachable: true (when CIP brain configured)
- [ ] POST /login returns a JWT for a real user credential.
- [ ] Browser microphone permission works over HTTPS.
- [ ] WebSocket streaming reaches /ws/audio.
- [ ] TTS audio plays on web and mobile.
- [ ] GET /admin/users returns 403 without admin JWT (not 500).
