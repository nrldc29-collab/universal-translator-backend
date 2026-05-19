# Go-Live Commands

Use this as the final copy/paste checklist when launching the True Streaming STT Provider.

## 1. Confirm local repo is clean

```bash
git status --short
```

Expected output: empty.

## 2. Pull latest code on the VPS

```bash
cd /opt/true-streaming-stt-provider
sudo git pull
```

## 3. Set the production domain

Replace `your-domain.com` with your real domain:

```bash
sudo bash deploy/scripts/set-domain.sh your-domain.com
```

## 4. Check production `.env`

```bash
sudo sed -n '1,220p' /opt/true-streaming-stt-provider/.env
```

Confirm:

```
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
ENABLE_ADMIN_RESET=false
```

## 5. Run preflight

```bash
sudo bash deploy/scripts/preflight.sh
```

## 6. Deploy

```bash
sudo bash deploy/scripts/deploy-vps.sh
```

## 7. Enable or renew HTTPS

First-time setup:

```bash
sudo certbot --nginx -d your-domain.com
```

Renewal check:

```bash
sudo certbot renew --dry-run
```

## 8. Verify public health

```bash
curl https://your-domain.com/health
```

## 9. Verify full deployment

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## 10. Safely list key fingerprints

```bash
sudo bash deploy/scripts/list-api-keys.sh /opt/true-streaming-stt-provider/.env
```

## 11. Check logs

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose logs -f stt-server
```

## 12. Check event log

```bash
sudo tail -f /opt/true-streaming-stt-provider/logs/stt-events.jsonl
```

## 13. Check admin audit log

```bash
sudo tail -f /opt/true-streaming-stt-provider/logs/admin-audit.jsonl
```

## 14. Test browser client

Open:

```
https://your-domain.com
```

Leave WebSocket URL blank for same-origin mode.

Paste your `STT_API_KEY`.

Click Start microphone and speak.

## 15. Test production usage endpoint

```bash
STT_API_KEY="$(sudo grep '^STT_API_KEY=' /opt/true-streaming-stt-provider/.env | cut -d '=' -f 2-)"

curl https://your-domain.com/v1/usage \
  -H "Authorization: Bearer $STT_API_KEY"
```

## 16. Test production admin health

```bash
ADMIN_API_KEY="$(sudo grep '^ADMIN_API_KEY=' /opt/true-streaming-stt-provider/.env | cut -d '=' -f 2-)"

curl https://your-domain.com/v1/admin/health \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

## 17. Confirm unauthenticated sensitive endpoints fail

```bash
curl -i https://your-domain.com/metrics
curl -i https://your-domain.com/v1/usage
curl -i https://your-domain.com/v1/admin/health
```

Expected result: `401 Unauthorized`.

## 18. Final launch confirmation

Before sharing the URL, confirm:

- HTTPS works
- WSS works
- Browser microphone works
- `/metrics` requires auth
- `/v1/usage` requires auth
- `/v1/admin/*` requires admin auth
- `ENABLE_ADMIN_RESET=false`
- Logs do not expose raw API keys
- Usage snapshot is being written
- Admin audit log is being written

## 19. Share client connection details

Give client apps:

WebSocket URL:
```
wss://your-domain.com/stt/stream
```

Audio format:
```
pcm_s16le, 16000 Hz, mono
```

Auth:
```
?api_key=CLIENT_STT_API_KEY
```

## 20. Rollback command

If needed:

```bash
cd /opt/true-streaming-stt-provider
sudo git log --oneline -5
sudo git checkout PREVIOUS_COMMIT_SHA
sudo docker compose up -d --build
sudo systemctl reload nginx
```
