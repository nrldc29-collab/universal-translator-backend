# Architecture

Anai Translator is split into three active surfaces:

```text
Web PWA / Expo Mobile
        ↓
FastAPI HTTP + WebSocket backend
        ↓
STT → context/refinement → translation → TTS
```

## Backend

- `backend/api.py` exposes HTTP endpoints, health checks, metrics, and WebSockets.
- `backend/streaming.py` handles live audio frames, VAD, partial/final STT, translation, and TTS chunks.
- `backend/pipeline.py` wires STT, translation, context, and TTS components.
- `backend/security.py` handles JWT/API-key auth, quotas, and usage accounting.
- `backend/sessions.py`, `backend/memory.py`, `backend/profile_memory.py`, and `backend/speakers.py` store conversation context.

## Clients

- `frontend/` is the Vite React PWA.
- `translator-mobile/` is the Expo mobile client.

## Model/data directories

- `models/whisper/` for STT caches.
- `models/translation/` for translation caches/models.
- `models/tts/` for Piper voices and generated TTS cache.
- `models/uploads/` for temporary request files.

Downloaded models, generated audio, profiles, uploads, and logs should not be committed.
