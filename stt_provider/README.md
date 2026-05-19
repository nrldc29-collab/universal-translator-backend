# True Streaming STT Provider

A self-hosted streaming speech-to-text provider.

> **Note on the "true streaming" naming.** The current implementation re-transcribes the
> entire accumulated speech buffer on every partial and final emission, so it is closer to
> near-real-time chunked transcription than fully incremental decoding. See
> [`docs/streaming-design.md`](docs/streaming-design.md) for a sketch of how to make it
> truly incremental.

It supports:

- Live WebSocket speech-to-text
- Partial transcript events
- Final transcript events
- API key authentication
- Per-key usage tracking
- Batch transcription endpoint
- Browser microphone client
- Python CLI clients
- Python SDK
- Docker Compose deployment
- Nginx HTTPS/WSS deployment
- Prometheus-style metrics
- Admin audit logs

## Architecture

```text
Browser / CLI / app
  -> WebSocket PCM16 audio
  -> FastAPI STT server
  -> Voice activity detection
  -> faster-whisper
  -> partial + final transcript events
```

## Local setup

```bash
cp .env.example .env
docker compose up --build
```

Open the browser client:

```
http://localhost:5173
```

Use this WebSocket URL:

```
ws://localhost:8000/stt/stream
```

Paste your `STT_API_KEY` from `.env`.

## Health check

```bash
curl http://localhost:8000/health
```

## Streaming WebSocket API

Endpoint:

```
ws://localhost:8000/stt/stream?api_key=YOUR_KEY
```

Production endpoint:

```
wss://your-domain.com/stt/stream?api_key=YOUR_KEY
```

Optional decoder query parameters:

- `hotwords`: comma-separated phrases to bias recognition
- `initial_prompt`: prompt text to guide decoding
- `beam_size`: decoder beam size
- `word_timestamps`: `true` or `false`
- `temperature`: decoder temperature

Send binary WebSocket frames containing raw audio:

```json
{
  "encoding": "pcm_s16le",
  "sample_rate": 16000,
  "channels": 1
}
```

### Session started

```json
{
  "session_id": "uuid",
  "sequence": 0,
  "created_at": "2026-01-01T00:00:00+00:00",
  "type": "session.started",
  "sample_rate": 16000,
  "channels": 1,
  "encoding": "pcm_s16le",
  "language": "en"
}
```

### Partial transcript

```json
{
  "session_id": "uuid",
  "sequence": 1,
  "created_at": "2026-01-01T00:00:01+00:00",
  "type": "transcript.partial",
  "text": "hello I need help with"
}
```

### Final transcript

```json
{
  "session_id": "uuid",
  "sequence": 2,
  "created_at": "2026-01-01T00:00:02+00:00",
  "type": "transcript.final",
  "text": "Hello, I need help with my account."
}
```

### Flush

```json
{
  "type": "flush"
}
```

## Batch transcription API

```bash
curl http://localhost:8000/v1/audio/transcriptions \
  -H "Authorization: Bearer YOUR_KEY" \
  -F "file=@sample.wav" \
  -F "model=base" \
  -F "language=en" \
  -F "hotwords=Acme,Jane Doe" \
  -F "initial_prompt=Customer support call" \
  -F "beam_size=4" \
  -F "word_timestamps=true" \
  -F "temperature=0.0"
```

## Models endpoint

```bash
curl http://localhost:8000/v1/models
```

## Usage endpoint

```bash
curl http://localhost:8000/v1/usage \
  -H "Authorization: Bearer YOUR_KEY"
```

## Metrics endpoint

```bash
curl http://localhost:8000/metrics \
  -H "Authorization: Bearer YOUR_KEY"
```

## Usage export

JSON:

```bash
curl http://localhost:8000/v1/usage/export \
  -H "Authorization: Bearer YOUR_KEY" \
  -o stt-usage-export.json
```

CSV:

```bash
curl http://localhost:8000/v1/usage/export.csv \
  -H "Authorization: Bearer YOUR_KEY" \
  -o stt-usage-export.csv
```

## Admin endpoints

Admin endpoints require `ADMIN_API_KEY`.

Admin health:

```bash
ADMIN_API_KEY="$(grep '^ADMIN_API_KEY=' .env | cut -d '=' -f 2-)"

curl http://localhost:8000/v1/admin/health \
  -H "Authorization: Bearer $ADMIN_API_KEY"
```

Admin audit export:

```bash
curl http://localhost:8000/v1/admin/audit \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -o admin-audit.jsonl
```

Admin audit CSV:

```bash
curl http://localhost:8000/v1/admin/audit.csv \
  -H "Authorization: Bearer $ADMIN_API_KEY" \
  -o admin-audit.csv
```

Usage reset is disabled by default. To enable locally:

```
ENABLE_ADMIN_RESET=true
```

Then:

```bash
bash deploy/scripts/reset-usage.sh http://localhost:8000 .env
```

Keep `ENABLE_ADMIN_RESET=false` in production unless intentionally resetting usage.

## CLI clients

Batch file transcription:

```bash
python3 client/transcribe_file.py sample.wav \
  --api-key YOUR_KEY \
  --base-url http://localhost:8000 \
  --model base \
  --language en
```

Streaming microphone client:

```bash
python3 client/stream_mic.py \
  --url ws://localhost:8000/stt/stream \
  --api-key YOUR_KEY \
  --language en
```

Convert common audio files to 16 kHz mono PCM WAV:

```bash
python3 client/convert_audio.py input.mp3 sample.wav
```

## Python SDK

Install locally:

```bash
cd sdk/python
python3 -m pip install -e .
cd ../..
```

Batch transcription:

```python
from true_streaming_stt import StreamingSTTClient

client = StreamingSTTClient(
    api_key="YOUR_KEY",
    base_url="http://localhost:8000",
)

result = client.transcribe_file("sample.wav", language="en")
print(result["text"])
```

Streaming a 16 kHz mono PCM WAV:

```bash
python3 sdk/python/examples/stream_pcm_file.py sample.wav \
  --api-key YOUR_KEY \
  --url ws://localhost:8000/stt/stream \
  --language en
```

## Environment variables

Common settings:

```
STT_API_KEY=your-client-key
STT_API_KEYS=browser:your-client-key,cli:another-client-key
ADMIN_API_KEY=your-admin-key
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
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

## Deployment

## Required production environment variables

Production and staging deployments must set an explicit `STT_API_KEY`.

The app will refuse to start outside `ENV=dev` when `STT_API_KEY` is empty.
Do not use the old development default `dev-secret-key` in deployed environments.

Set your domain:

```bash
bash deploy/scripts/set-domain.sh your-domain.com
```

Update `.env`:

```
ALLOWED_ORIGINS=https://your-domain.com,https://www.your-domain.com
```

Run preflight:

```bash
bash deploy/scripts/preflight.sh
```

Deploy on the VPS:

```bash
sudo bash deploy/scripts/deploy-vps.sh
```

Enable HTTPS/WSS:

```bash
sudo certbot --nginx -d your-domain.com
```

Verify production:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## Operations

View logs:

```bash
docker compose logs -f stt-server
```

View event log:

```bash
tail -f logs/stt-events.jsonl
```

View admin audit log:

```bash
tail -f logs/admin-audit.jsonl
```

List keys safely:

```bash
bash deploy/scripts/list-api-keys.sh .env
```

Rotate client API key on VPS:

```bash
sudo bash deploy/scripts/rotate-api-key.sh
```

Rotate admin API key on VPS:

```bash
sudo bash deploy/scripts/rotate-admin-key.sh
```

Revoke old client key on VPS:

```bash
sudo bash deploy/scripts/revoke-api-key.sh \
  /opt/true-streaming-stt-provider/.env \
  previous
```

## Verification

Local full verification:

```bash
bash deploy/scripts/verify-deployment.sh http://localhost:8000 .env
```

HTTP smoke tests:

```bash
make smoke
```

Metrics:

```bash
make metrics
```

## Release docs

Read these before shipping:

- `RELEASE_CHECKLIST.md`
- `TROUBLESHOOTING.md`
- `PRODUCTION_RUNBOOK.md`

## Status & known limitations

- **Streaming is chunk-based, not incremental.** Every partial and final event
  re-transcribes the whole speech buffer through `faster-whisper`. CPU cost and latency
  therefore grow with utterance length. See `docs/streaming-design.md` for the planned
  fix.
- **`auth.get_api_key_map()` is recomputed on every request.** Cheap to cache once the
  number of connections grows.
- **Mono PCM-16LE only.** Other encodings, sample rates, and channel counts are not
  supported by the WebSocket path.
- **No automatic log rotation.** Pair `logs/stt-events.jsonl` and `logs/admin-audit.jsonl`
  with `logrotate` or its Windows equivalent in production.
- **API keys must be configured explicitly.** Keep `.env` out of source control and
  use long random values before deploying.

## Recent fixes

- `2026-05` — CORS `allow_methods` widened from `GET` to `GET, POST, OPTIONS` so
  browser preflights succeed for `/v1/audio/transcriptions` and
  `/v1/usage/reset`.
- `2026-05` — Audio frame counters now increment **after** the empty-frame and
  oversized-frame validations, so rejected frames no longer count toward
  `audio_bytes_received`, `estimated_audio_seconds`, or `estimated_cost`.
