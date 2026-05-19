# Production Runbook

## 1. Configure environment

Create `.env` from the example:

```bash
cp .env.example .env
```

Generate a strong API key:

```bash
python3 - <<'PY'
import secrets
print(secrets.token_urlsafe(48))
PY
```

Put it in .env:

```
STT_API_KEY=your-generated-secret
```

## 2. Run locally with Docker Compose

```bash
docker compose up --build
```

Health check:

```bash
curl http://localhost:8000/health
```

Models endpoint:

```bash
curl http://localhost:8000/v1/models
```

## 3. Test browser streaming

Open:

```
http://localhost:5173
```

Use:

```
ws://localhost:8000/stt/stream
```

Paste your `STT_API_KEY`.

## 4. Test batch transcription

```bash
curl http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer your-generated-secret" \
  -F "file=@sample.wav" \
  -F "model=base" \
  -F "language=en"
```

## 5. Deploy to VPS

From the project root on the VPS:

```bash
sudo bash deploy/scripts/deploy-vps.sh
```

Then check:

```bash
curl http://localhost:8000/health
```

## 6. Enable HTTPS/WSS

Follow:

```
deploy/nginx/HTTPS_CERTBOT.md
```

Production WebSocket URL should be:

```
wss://your-domain.com/stt/stream
```

## 7. Logs

View server logs:

```bash
docker compose logs -f stt-server
```

View client logs:

```bash
docker compose logs -f stt-client
```

## 8. Restart

```bash
docker compose restart
```

## 9. Update deployment

```bash
git pull
docker compose up -d --build
```

## 10. Recommended production values

For CPU:

```
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

For NVIDIA GPU:

```
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

## 11. API event contract

Streaming clients receive:

```json
{
  "session_id": "uuid",
  "sequence": 1,
  "created_at": "2026-01-01T00:00:00+00:00",
  "type": "transcript.partial",
  "text": "hello world"
}
```

Final transcript event:

```json
{
  "session_id": "uuid",
  "sequence": 2,
  "created_at": "2026-01-01T00:00:01+00:00",
  "type": "transcript.final",
  "text": "Hello world."
}
```
