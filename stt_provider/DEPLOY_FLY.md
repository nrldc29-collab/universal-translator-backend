# Deploy on Fly.io

## 1. Install and log in to Fly

```bash
fly auth login
```

## 2. Create the app

```bash
fly launch --no-deploy
```

Use the existing `fly.toml` when prompted.

## 3. Create the persistent volume

Replace `iad` with your chosen region if needed.

```bash
fly volumes create stt_data --region iad --size 1
```

## 4. Set secrets

Generate strong values first:

```bash
python3 - <<'PY'
import secrets
print("STT_API_KEY=" + secrets.token_urlsafe(48))
print("ADMIN_API_KEY=" + secrets.token_urlsafe(48))
PY
```

Set them:

```bash
fly secrets set \
  STT_API_KEY="your-strong-client-key" \
  ADMIN_API_KEY="your-strong-admin-key" \
  STT_API_KEYS="browser:your-strong-client-key" \
  ALLOWED_ORIGINS="https://your-fly-app.fly.dev"
```

For local browser testing against Fly, temporarily use:

```bash
fly secrets set ALLOWED_ORIGINS="http://localhost:5173,http://127.0.0.1:5173"
```

## 5. Deploy

```bash
fly deploy
```

## 6. Verify health

```bash
curl https://your-fly-app.fly.dev/health
```

## 7. Verify usage

```bash
curl https://your-fly-app.fly.dev/v1/usage \
  -H "Authorization: Bearer YOUR_STT_API_KEY"
```

## 8. Use streaming WebSocket

```
wss://your-fly-app.fly.dev/stt/stream
```

## Notes

- Use `wss://`, not `ws://`, for Fly.io.
- The mounted volume persists logs and usage snapshots at `/app/logs`.
- CPU transcription may be slow on shared CPUs.
- First deploy can be slow while the Whisper model downloads and warms up.
