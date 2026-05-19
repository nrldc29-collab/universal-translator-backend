# Deployment Checklist

## Before deploy

- [ ] Copy `.env.example` to `.env` or configure equivalent platform variables.
- [ ] Set `ENVIRONMENT=production`.
- [ ] Set a strong `JWT_SECRET`.
- [ ] Configure `USERS`, `USER_TIERS`, or external auth.
- [ ] Set `ALLOWED_ORIGINS` to deployed frontend origins.
- [ ] Confirm model/TTS voice files are available or downloadable.
- [ ] Confirm HTTPS/WSS is enabled.

## Build validation

- [ ] `pytest`
- [ ] `cd frontend && npm run build`
- [ ] `cd translator-mobile && npm run lint && npm run build`

## After deploy

- [ ] `/health` returns status and release.
- [ ] `/ready` shows expected model readiness.
- [ ] `/diagnostics` has no unexpected failures.
- [ ] Browser microphone permission works over HTTPS.
- [ ] WebSocket streaming reaches `/ws/audio`.
- [ ] TTS audio plays on web and mobile.
