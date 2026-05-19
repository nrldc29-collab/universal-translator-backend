# Deployment Options

This project can run on:

- VPS with Docker Compose and Nginx
- Render
- Railway
- Fly.io

## Recommended choice

For the most control and best long-running WebSocket behavior, use:

```text
VPS + Docker Compose + Nginx + Certbot
```

For the easiest hosted deployment, use:

```text
Render
```

For fast app hosting experiments, use:

```text
Railway
```

For a good middle ground with persistent volumes and global regions, use:

```text
Fly.io
```

## Comparison

| Option | Best for | Pros | Cons |
|--------|----------|------|------|
| VPS | Production control | Full control, stable WebSockets, easy Nginx config, predictable cost | You manage server updates and security |
| Render | Simple hosted deploy | GitHub blueprint, generated secrets, simple HTTPS | CPU may be slow, model startup can be slow |
| Railway | Quick experiments | Simple GitHub deploy, easy env vars | Costs can grow, persistent storage needs planning |
| Fly.io | Regional deployment | Persistent volume, good HTTPS/WSS support, more infra control | More concepts to learn than Render/Railway |

## VPS

Use VPS when you want:

- Stable production deployment
- One domain serving both UI and API
- Nginx control
- Certbot HTTPS
- Persistent local logs
- Predictable WebSocket behavior

Deploy:

```bash
bash deploy/scripts/set-domain.sh your-domain.com
sudo bash deploy/scripts/deploy-vps.sh
sudo certbot --nginx -d your-domain.com
```

Verify:

```bash
sudo bash deploy/scripts/verify-deployment.sh \
  https://your-domain.com \
  /opt/true-streaming-stt-provider/.env
```

## Render

Use Render when you want:

- Fast hosted setup
- GitHub Blueprint deployment
- Managed HTTPS
- No VPS administration

Files:

- `render.yaml`
- `DEPLOY_RENDER.md`

Main limitation: CPU transcription can be slow on smaller plans.

## Railway

Use Railway when you want:

- Quick hosted experiments
- Simple environment variable management
- GitHub-based deploys

Files:

- `railway.json`
- `DEPLOY_RAILWAY.md`

Main limitation: persistent usage/log storage needs extra planning.

## Fly.io

Use Fly.io when you want:

- Managed HTTPS/WSS
- Persistent volume for logs and usage snapshots
- Region selection
- More control than Render/Railway

Files:

- `fly.toml`
- `DEPLOY_FLY.md`

Main limitation: more operational complexity than Render.

## Audio/model performance guidance

For cheapest CPU deployment:

```
WHISPER_MODEL_SIZE=tiny
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

For better CPU accuracy:

```
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
```

For stronger production performance with NVIDIA GPU:

```
WHISPER_MODEL_SIZE=small
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

## Security checklist for every deployment

- Use strong `STT_API_KEY`
- Use strong `ADMIN_API_KEY`
- Set `ALLOWED_ORIGINS` to the real HTTPS client domains
- Keep `ENABLE_ADMIN_RESET=false` unless intentionally resetting usage
- Use `wss://` for production WebSockets
- Do not expose raw API keys in logs
- Use `deploy/scripts/list-api-keys.sh` to inspect fingerprints safely

## Verification checklist

Run this after every deployment:

```bash
bash deploy/scripts/verify-deployment.sh https://your-domain.com /path/to/.env
```

Check:

```bash
curl https://your-domain.com/health
```

Check usage:

```bash
curl https://your-domain.com/v1/usage \
  -H "Authorization: Bearer YOUR_STT_API_KEY"
```

Check admin health:

```bash
curl https://your-domain.com/v1/admin/health \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY"
```

## My recommendation

Start with VPS if this will be a real provider.

Start with Render if you just want to prove the API works from a hosted URL.

Move to GPU hosting later if transcription latency becomes the bottleneck.
