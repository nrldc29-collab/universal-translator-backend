# Backend

FastAPI backend for Anai Translator.

## Main files

- `api.py` — HTTP endpoints, WebSocket routes, health, diagnostics, metrics.
- `streaming.py` — live audio streaming, VAD, partial/final translation, TTS chunks.
- `pipeline.py` — STT → context → translation → TTS orchestration.
- `security.py` — auth, JWTs, quotas, and usage accounting.
- `config.py` — environment parsing and runtime defaults.
- `sessions.py`, `memory.py`, `profile_memory.py`, `speakers.py` — conversation state.

Run locally from the repository root:

```bash
uvicorn backend.api:app --reload
```

More details: `docs/BACKEND.md` and `docs/API.md`.
