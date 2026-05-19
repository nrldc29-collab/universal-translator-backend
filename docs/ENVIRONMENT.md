# Environment Reference

The backend reads configuration from environment variables. Copy
`.env.example` to `.env` for local development.

This document groups the most important variables. The exhaustive list with
defaults lives in `backend/config.py`.

## Critical for production

| Variable | Why it matters |
| --- | --- |
| `ENVIRONMENT=production` | Enables strict origin checks and disables debug noise. |
| `BACKEND_HOST=0.0.0.0` | Required to accept off-host connections. |
| `BACKEND_PORT` | TCP port (Railway / Heroku inject this automatically). |
| `JWT_SECRET` | Must be replaced. Sign auth tokens with a strong value. Generate with `p