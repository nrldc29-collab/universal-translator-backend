# Deploy on Railway

## 1. Push this repo to GitHub

```bash
git add railway.json DEPLOY_RAILWAY.md
git commit -m "Add Railway deployment option"
git push origin main
```

## 2. Create the Railway service

In Railway:

- New Project
- Deploy from GitHub repo
- Select this repo
- Railway should detect `railway.json`
- Deploy

## 3. Add environment variables

In Railway service variables, add:

```
STT_API_KEY=your-strong-client-key
ADMIN_API_KEY=your-strong-admin-key
STT_API_KEYS=browser:your-strong-client-key
ALLOWED_ORIGINS=https://your-client-domain.com
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
TRANSCRIPTION_LANGUAGE=en
SAMPLE_RATE=16000
CHANNELS=1
FRAME_MS=30
VAD_MODE=2
MAX_ACTIVE_CONNECTIONS=10
MAX_CONNECTIONS_PER_KEY=3
MAX_SESSION_SECONDS=1800
IDLE_TIMEOUT_SECONDS=60
MAX_AUDIO_FRAME_BYTES=262144
BILLING_RATE_PER_AUDIO_HOUR=0.0
ENABLE_ADMIN_RESET=false
```

For local browser testing against Railway, temporarily set:

```
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
```

## 4. Verify health

```bash
curl https://your-railway-domain.up.railway.app/health
```

## 5. Verify usage

```bash
curl https://your-railway-domain.up.railway.app/v1/usage \
  -H "Authorization: Bearer YOUR_STT_API_KEY"
```

## 6. Use streaming WebSocket

```
wss://your-railway-domain.up.railway.app/stt/stream
```

## Notes

- Use `wss://`, not `ws://`, for Railway.
- CPU transcription may be slow on small plans.
- First startup may take time while the Whisper model downloads and warms up.
- For serious production traffic, use a VPS or GPU-capable deployment.
