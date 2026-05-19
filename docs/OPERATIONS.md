# Operations Guide

## Health checks

- `/health` reports release, readiness, and uptime.
- `/ready` includes model warmup and voice cache details.
- `/diagnostics` includes frontend, streaming, limits, queue, session, and CIP status.

## Logs and metrics

- Event logs default to `logs/events.jsonl`.
- Prometheus metrics are available at `/metrics/prometheus`.
- Set `STREAM_HOT_PATH_LOGGING=1` only for short debugging sessions because it can include live transcript details.

## Runtime storage

- `models/uploads/` is temporary upload storage.
- `models/tts/cache/` stores generated voice cache files.
- `models/profiles.json` stores local user profile memory and should be backed up if profile history matters.

## Safe deployment checklist

- Use HTTPS/WSS in production.
- Set a strong `JWT_SECRET`.
- Configure `ALLOWED_ORIGINS`.
- Confirm `/health` and `/ready` pass after deploy.
- Keep downloaded model files out of git.
