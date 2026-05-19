# v0.1.0 — True Streaming STT Provider

First release of the self-hosted true streaming speech-to-text provider.

## Included

- WebSocket streaming STT endpoint
- Partial transcript events
- Final transcript events
- API key authentication
- Multiple client API keys with labels
- Per-key usage tracking
- Persistent usage snapshots
- Prometheus-style metrics
- Batch transcription endpoint
- Browser microphone client
- Python CLI clients
- Python SDK
- Docker Compose deployment
- Nginx HTTPS/WSS deployment config
- Admin API key support
- Admin audit logs
- Deployment verification scripts
- Troubleshooting guide
- Production runbook
- Release checklist

## Local verification

```bash
docker compose up --build
bash deploy/scripts/verify-deployment.sh http://localhost:8000 .env
```

## Production deployment

```bash
bash deploy/scripts/set-domain.sh your-domain.com
sudo bash deploy/scripts/deploy-vps.sh
sudo certbot --nginx -d your-domain.com
```

Then verify:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## Important production settings

Keep this disabled unless intentionally resetting usage:

```
ENABLE_ADMIN_RESET=false
```

Set production browser origins:

```
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

Use secure WebSockets in production:

```
wss://your-domain.com/stt/stream
```
