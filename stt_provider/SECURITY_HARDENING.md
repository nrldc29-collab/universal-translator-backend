# Security Hardening Guide

Use this checklist before exposing the STT provider publicly.

## 1. Use strong secrets

Generate strong keys:

```bash
python3 - <<'PY'
import secrets
print("STT_API_KEY=" + secrets.token_urlsafe(48))
print("ADMIN_API_KEY=" + secrets.token_urlsafe(48))
PY
```

Set them in `.env`:

```
STT_API_KEY=your-strong-client-key
STT_API_KEYS=browser:your-strong-client-key,cli:another-client-key
ADMIN_API_KEY=your-strong-admin-key
```

Never commit `.env`.

## 2. Lock browser origins

Do not leave local origins in production.

Production example:

```
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

Avoid:

```
ALLOWED_ORIGINS=*
```

## 3. Keep dangerous admin actions disabled

Production default should be:

```
ENABLE_ADMIN_RESET=false
```

Only temporarily enable reset when you intentionally need to clear usage data.

## 4. Use HTTPS and WSS only

Production browser clients should use:

```
wss://your-domain.com/stt/stream
```

not:

```
ws://your-domain.com/stt/stream
```

Verify HTTPS:

```bash
curl https://your-domain.com/health
```

Verify WSS:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## 5. Protect metrics and usage endpoints

These endpoints require API keys:

- `/metrics`
- `/v1/usage`
- `/v1/usage/export`
- `/v1/usage/export.csv`

Verify unauthenticated access fails:

```bash
curl -i https://your-domain.com/metrics
curl -i https://your-domain.com/v1/usage
```

Expected result:

```
401 Unauthorized
```

## 6. Protect admin endpoints

These endpoints require `ADMIN_API_KEY`:

- `/v1/admin/health`
- `/v1/admin/audit`
- `/v1/admin/audit.csv`
- `/v1/usage/reset`

Verify client keys cannot access admin endpoints:

```bash
curl -i https://your-domain.com/v1/admin/health \
  -H "Authorization: Bearer YOUR_STT_API_KEY"
```

Expected result:

```
401 Unauthorized
```

## 7. Use connection limits

Recommended production defaults:

```
MAX_ACTIVE_CONNECTIONS=10
MAX_CONNECTIONS_PER_KEY=3
MAX_SESSION_SECONDS=1800
IDLE_TIMEOUT_SECONDS=60
MAX_AUDIO_FRAME_BYTES=262144
```

Lower these if the server is small.

## 8. Rotate keys regularly

Rotate client key:

```bash
sudo bash deploy/scripts/rotate-api-key.sh
```

Rotate admin key:

```bash
sudo bash deploy/scripts/rotate-admin-key.sh
```

Restart after rotation:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d --build
```

List fingerprints safely:

```bash
sudo bash deploy/scripts/list-api-keys.sh /opt/true-streaming-stt-provider/.env
```

## 9. Revoke old keys after migration

Remove old client keys by label:

```bash
sudo bash deploy/scripts/revoke-api-key.sh \
  /opt/true-streaming-stt-provider/.env \
  previous
```

Restart:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d --build
```

## 10. Watch logs for abuse

Event log:

```bash
tail -f logs/stt-events.jsonl
```

Admin audit log:

```bash
tail -f logs/admin-audit.jsonl
```

Look for:

- repeated invalid API key attempts
- too many active connections
- frequent idle timeouts
- large audio frame errors
- unexpected usage reset events

## 11. Back up secrets and usage data

Back up these files securely:

- `/opt/true-streaming-stt-provider/.env`
- `/opt/true-streaming-stt-provider/logs/usage-snapshot.json`
- `/opt/true-streaming-stt-provider/logs/admin-audit.jsonl`

Do not store backups in public repositories.

## 12. Keep the VPS patched

On Ubuntu:

```bash
sudo apt-get update
sudo apt-get upgrade -y
sudo reboot
```

After reboot:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d
sudo systemctl reload nginx
```

## 13. Firewall basics

Allow SSH, HTTP, and HTTPS only:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 80
sudo ufw allow 443
sudo ufw enable
sudo ufw status
```

Do not expose port 8000 publicly if Nginx is serving the app.

## 14. Production verification

Run after every deploy or security change:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## Final production security baseline

Before launch, confirm:

- `.env` is not committed
- `STT_API_KEY` is strong
- `ADMIN_API_KEY` is strong
- `ALLOWED_ORIGINS` uses production HTTPS domains only
- `ENABLE_ADMIN_RESET=false`
- HTTPS works
- WSS works
- `/metrics` requires auth
- `/v1/usage` requires auth
- `/v1/admin/*` requires admin auth
- Logs show fingerprints, not raw secrets
- Firewall is enabled
- Backups are secure
