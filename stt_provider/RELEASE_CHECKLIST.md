# Release Checklist

## Code readiness

- [ ] `main` branch is up to date
- [ ] GitHub Actions CI passes
- [ ] WebSocket verification passes
- [ ] HTTP smoke tests pass
- [ ] Docker Compose starts cleanly
- [ ] No secrets are committed

## Local verification

```bash
docker compose up --build
bash deploy/scripts/verify-deployment.sh http://localhost:8000 .env
```

## Environment

- [ ] `.env` exists on the server
- [ ] `STT_API_KEY` is strong and private
- [ ] `ADMIN_API_KEY` is strong and private
- [ ] `STT_API_KEYS` labels are correct
- [ ] `ALLOWED_ORIGINS` uses production HTTPS origins
- [ ] `ENABLE_ADMIN_RESET=false` in production
- [ ] `BILLING_RATE_PER_AUDIO_HOUR` is correct

## Domain and HTTPS

- [ ] DNS points to the VPS
- [ ] `deploy/scripts/set-domain.sh your-domain.com` has been run
- [ ] Nginx config no longer contains `your-domain.com`
- [ ] Certbot certificate is installed
- [ ] HTTPS health check works
- [ ] WSS streaming works

## Production verification

```bash
sudo bash deploy/scripts/verify-deployment.sh https://your-domain.com /opt/true-streaming-stt-provider/.env
```

## Security

- [ ] `/metrics` requires client API key
- [ ] `/v1/usage` requires client API key
- [ ] `/v1/admin/health` requires admin API key
- [ ] `/v1/admin/audit` requires admin API key
- [ ] Usage reset is disabled unless intentionally enabled
- [ ] Logs contain fingerprints only, not raw keys

## Observability

- [ ] `logs/stt-events.jsonl` is written
- [ ] `logs/admin-audit.jsonl` is written
- [ ] `logs/usage-snapshot.json` is written
- [ ] `/metrics` returns Prometheus metrics
- [ ] `/v1/usage/export.csv` downloads usage CSV

## Backup

- [ ] `.env` is backed up securely
- [ ] Admin key recovery process is documented
- [ ] Usage snapshot backup plan is defined

## Final deploy

```bash
sudo bash deploy/scripts/preflight.sh
sudo bash deploy/scripts/deploy-vps.sh
```

## Post-deploy checks

```bash
curl https://your-domain.com/health
sudo bash deploy/scripts/list-api-keys.sh /opt/true-streaming-stt-provider/.env
sudo docker compose logs -f stt-server
```
