# Troubleshooting Guide

## Server does not start

Check logs:

```bash
docker compose logs -f stt-server
```

Common causes:

- `.env` is missing
- Docker image is still building
- Whisper model is downloading
- Port 8000 is already in use
- `WHISPER_DEVICE=cuda` is set on a machine without CUDA

Fix port conflict:

```bash
sudo lsof -i :8000
```

Then stop the conflicting process or change the exposed port in `docker-compose.yml`.

## Browser says WebSocket error

Check that the API key is correct.

For local testing, use:

```
ws://localhost:8000/stt/stream
```

For production HTTPS, use:

```
wss://your-domain.com/stt/stream
```

Check allowed origins:

```bash
curl http://localhost:8000/health
```

Your browser page origin must appear in `allowed_origins`.

## WebSocket closes immediately

Likely causes:

- Invalid API key
- Origin not allowed
- Too many active connections
- Too many active connections for that API key

Check server logs:

```bash
tail -f logs/stt-events.jsonl
```

Check usage and active connections:

```bash
curl http://localhost:8000/v1/usage \
  -H "Authorization: Bearer YOUR_KEY"
```

## Microphone permission denied

In the browser:

- Make sure the page is served from localhost or HTTPS
- Click the lock icon in the address bar
- Allow microphone access
- Reload the page

For production, microphone access generally requires HTTPS.

## No transcript appears

Check these first:

- Speak clearly for at least 2 seconds
- Confirm the server terminal has no errors
- Confirm the client is sending audio
- Confirm your microphone works in another app
- Try `WHISPER_MODEL_SIZE=base` or `small`

Check metrics:

```bash
curl http://localhost:8000/metrics \
  -H "Authorization: Bearer YOUR_KEY" \
  | grep audio
```

If `stt_audio_bytes_received_total` stays at 0, the server is not receiving audio.

## Transcription is slow

CPU transcription can be slow.

Try these settings:

```
WHISPER_MODEL_SIZE=tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

For better accuracy with more compute:

```
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

For NVIDIA GPU:

```
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

Then restart:

```bash
docker compose up -d --build
```

## First request is very slow

The model may be downloading or warming up.

Check logs:

```bash
docker compose logs -f stt-server
```

The Docker Compose file includes a Hugging Face cache volume so future restarts should be faster.

## Nginx returns 502 Bad Gateway

Check whether the app is running:

```bash
curl http://127.0.0.1:8000/health
```

Check Nginx config:

```bash
sudo nginx -t
```

Check Nginx logs:

```bash
sudo tail -n 100 /var/log/nginx/error.log
```

Restart services:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d --build
sudo systemctl reload nginx
```

## HTTPS works but WSS fails

Make sure Nginx has the WebSocket upgrade headers under `/stt/stream`:

```
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

Then reload:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

Verify the deployment:

```bash
sudo bash deploy/scripts/verify-deployment.sh https://your-domain.com /opt/true-streaming-stt-provider/.env
```

## Certbot fails

Check DNS first:

```bash
dig your-domain.com
```

Make sure the domain points to your VPS public IP.

Then run:

```bash
sudo certbot --nginx -d your-domain.com
```

## Usage reset returns 403

Usage reset is disabled unless this is set:

```
ENABLE_ADMIN_RESET=true
```

For production, keep it disabled unless you intentionally need a reset.

## Usage reset returns 401

You must use `ADMIN_API_KEY`, not `STT_API_KEY`.

Print it on the VPS only when needed:

```bash
sudo bash deploy/scripts/print-admin-key.sh
```

Then retry:

```bash
bash deploy/scripts/reset-usage.sh https://your-domain.com /opt/true-streaming-stt-provider/.env
```

## API key works locally but not in production

Check the deployed `.env`:

```bash
sudo bash deploy/scripts/list-api-keys.sh /opt/true-streaming-stt-provider/.env
```

Restart after changing `.env`:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d --build
```

## Deployment verification fails

Run:

```bash
sudo bash deploy/scripts/verify-deployment.sh https://your-domain.com /opt/true-streaming-stt-provider/.env
```

Then inspect:

```bash
sudo docker compose logs -f stt-server
sudo tail -n 100 /var/log/nginx/error.log
```

## Quick recovery commands

Restart app:

```bash
cd /opt/true-streaming-stt-provider
sudo docker compose up -d --build
```

Reload Nginx:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

List keys safely:

```bash
sudo bash deploy/scripts/list-api-keys.sh /opt/true-streaming-stt-provider/.env
```

Verify everything:

```bash
sudo bash deploy/scripts/verify-deployment.sh https://your-domain.com /opt/true-streaming-stt-provider/.env
```
