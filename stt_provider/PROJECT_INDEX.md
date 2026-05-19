# Project Index

This index points to the main docs, scripts, clients, SDK, and deployment files for the True Streaming STT Provider.

## Start here

| File | Purpose |
|---|---|
| `README.md` | Main setup, API, deployment, and operations guide |
| `RELEASE_CHECKLIST.md` | Release checklist before shipping |
| `TROUBLESHOOTING.md` | Common deployment and streaming fixes |
| `SECURITY_HARDENING.md` | Security checklist before public launch |
| `PRODUCTION_RUNBOOK.md` | Production operations runbook |
| `DEPLOYMENT_OPTIONS.md` | VPS vs Render vs Railway vs Fly.io comparison |

## Core server

| File | Purpose |
|---|---|
| `server/stt_server/main.py` | FastAPI app, WebSocket endpoint, HTTP endpoints |
| `server/stt_server/config.py` | Environment-driven settings |
| `server/stt_server/streaming.py` | Streaming transcription session logic |
| `server/stt_server/model.py` | faster-whisper model loading, transcription, warmup |
| `server/stt_server/vad.py` | Voice activity detection |
| `server/stt_server/auth.py` | API key validation and labels |
| `server/stt_server/security.py` | Secret hashing and redaction helpers |
| `server/stt_server/metrics.py` | Prometheus-style metrics |
| `server/stt_server/usage.py` | Persistent usage counters |
| `server/stt_server/logging_utils.py` | Event and admin audit logging |

## Local app and clients

| File | Purpose |
|---|---|
| `client/index.html` | Browser microphone test client |
| `client/stream_mic.py` | CLI microphone streaming client |
| `client/transcribe_file.py` | CLI batch transcription client |
| `client/convert_audio.py` | Audio conversion helper |

## Python SDK

| File | Purpose |
|---|---|
| `sdk/python/true_streaming_stt/client.py` | SDK client implementation |
| `sdk/python/true_streaming_stt/__init__.py` | SDK exports |
| `sdk/python/pyproject.toml` | SDK package metadata |
| `sdk/python/examples/stream_pcm_file.py` | SDK streaming WAV example |

## Testing and verification

| File | Purpose |
|---|---|
| `server/scripts/smoke_test_http.py` | HTTP smoke tests |
| `server/scripts/load_test_ws.py` | WebSocket load test |
| `deploy/scripts/verify-deployment.sh` | Full deployment verification |
| `deploy/scripts/verify-websocket.py` | WebSocket verification |
| `.github/workflows/ci.yml` | GitHub Actions CI |

## Deployment

| File | Purpose |
|---|---|
| `docker-compose.yml` | Local/server Docker Compose stack |
| `server/Dockerfile` | Server container image |
| `deploy/nginx/stt-provider.conf` | Nginx config for UI, API, and WSS |
| `deploy/nginx/HTTPS_CERTBOT.md` | HTTPS/WSS Certbot guide |
| `deploy/scripts/deploy-vps.sh` | VPS deployment script |
| `deploy/scripts/preflight.sh` | Deployment preflight checks |
| `deploy/scripts/set-domain.sh` | Replace Nginx domain placeholder |
| `render.yaml` | Render deployment blueprint |
| `railway.json` | Railway deployment config |
| `fly.toml` | Fly.io deployment config |
| `DEPLOY_RENDER.md` | Render guide |
| `DEPLOY_RAILWAY.md` | Railway guide |
| `DEPLOY_FLY.md` | Fly.io guide |

## Operations scripts

| File | Purpose |
|---|---|
| `deploy/scripts/list-api-keys.sh` | List key labels and fingerprints safely |
| `deploy/scripts/print-api-key.sh` | Print client API key on VPS when needed |
| `deploy/scripts/print-admin-key.sh` | Print admin API key on VPS when needed |
| `deploy/scripts/rotate-api-key.sh` | Rotate client API key |
| `deploy/scripts/rotate-admin-key.sh` | Rotate admin API key |
| `deploy/scripts/revoke-api-key.sh` | Revoke old client API keys |
| `deploy/scripts/reset-usage.sh` | Reset usage when admin reset is enabled |
| `deploy/scripts/audit-admin-action.sh` | Append deploy-script admin audit events |

## Release files

| File | Purpose |
|---|---|
| `RELEASE_NOTES_v0.1.0.md` | GitHub release notes for v0.1.0 |
| `.gitignore` | Ignore secrets, logs, caches, audio files |
| `Makefile` | Common local commands |

## Common commands

Start locally:

```bash
docker compose up --build
```

Verify locally:

```bash
bash deploy/scripts/verify-deployment.sh http://localhost:8000 .env
```

Run smoke tests:

```bash
make smoke
```

Check metrics:

```bash
STT_API_KEY="$(grep '^STT_API_KEY=' .env | cut -d '=' -f 2-)"
curl http://localhost:8000/metrics \
  -H "Authorization: Bearer $STT_API_KEY"
```

List key fingerprints:

```bash
bash deploy/scripts/list-api-keys.sh .env
```

Deploy to VPS:

```bash
bash deploy/scripts/set-domain.sh your-domain.com
sudo bash deploy/scripts/deploy-vps.sh
sudo certbot --nginx -d your-domain.com
```

Verify production:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```
