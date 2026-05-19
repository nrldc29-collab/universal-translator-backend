# API Reference

Interactive docs are available at `/docs` when the backend is running.

## Health

- `GET /health` — lightweight runtime status.
- `GET /ready` — readiness, model, and voice warmup details.
- `GET /diagnostics` — expanded diagnostics.

## Translation

- `POST /translate/text` — translate text and optionally synthesize audio.
- `POST /translate/audio` — upload audio for STT, translation, and optional TTS.
- `POST /translate/image` — OCR image text, translate, and optionally synthesize audio.
- `POST /tts` — synthesize text to speech.
- `POST /vad` — voice activity detection for uploaded audio.

## WebSockets

- `WS /ws/audio` — live audio streaming.
- `WS /ws/translate` — text translation stream.
- `WS /ws/ping` — connectivity check.

## Auth

Use `/auth/login` for JWT credentials or provide configured API keys. Development mode allows local anonymous access when no API keys are configured.
