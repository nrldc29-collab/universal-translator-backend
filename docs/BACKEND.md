# Backend Guide

The backend is a FastAPI service in `backend/` that orchestrates a real-time
speech → translation → speech pipeline. It supports HTTP, Server-Sent updates,
and WebSocket clients (web + mobile).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs are available at <http://localhost:8000/docs>.

## Run tests

```bash
pytest                  # all tests
pytest tests/test_security_limiter.py -q
pytest -k assistant     # match-by-name
```

Test layout lives under `tests/`. CI runs on Python 3.11 (see
`.github/workflows/ci.yml`).

## Endpoint surface

### Health and diagnostics
- `GET /` — liveness root.
- `GET /health` — lightweight liveness probe.
- `GET /ready` — readiness + warmup status.
- `GET /diagnostics` — extended diagnostics.
- `GET /metrics` — JSON metrics snapshot.
- `GET /metrics/prometheus` — Prometheus exposition.
- `GET /analytics` — aggregated usage view.
- `GET /debug/version`, `GET /api/debug/version` — build/version info.
- `GET /languages` — supported language pairs.

### Auth
- `POST /auth/login` — exchange username/password for a JWT.

### Translation
- `POST /translate/text` — translate text, optionally synthesize audio.
- `POST /translate/audio` — multipart audio → STT → translate → optional TTS.
- `POST /translate/image` — OCR (Tesseract) → translate → optional TTS.
- `POST /tts` — synthesize text to audio.
- `POST /vad` — voice activity detection on an uploaded clip.
- `GET /tts/audio/{cache_key}.wav` — fetch cached TTS.
- `GET /debug/tts-sample.wav` — fixed sample for debugging.

### WebSockets
- `WS /ws/audio` — primary live audio stream.
- `WS /ws/audio/streaming` — alternate live audio path.
- `WS /ws/translate` — text translation stream.
- `WS /ws/ping` — connectivity check.
- `WS /ws/assistant` — NAIA assistant chat stream.

### NAIA assistant
- `GET /api/assistant/health` — assistant availability + reason.
- `POST /api/assistant/chat` — single-turn chat with optional translation
  context.

### Static
- `GET /{full_path:path}` — serves `frontend/dist/` when
  `SERVE_FRONTEND_DIST=1`.

## Module map

| Module | Responsibility |
| --- | --- |
| `api.py` | FastAPI app factory + HTTP/WebSocket routes. |
| `streaming.py` | Live audio + text translation WebSocket logic. |
| `pipeline.py` | STT → translation → TTS orchestration. |
| `conversation.py` | Conversation memory and turn shaping. |
| `communication_brain.py` | High-level brain that decides next action. |
| `cip_engine.py`, `cip_client.py`, `cip_bridge.py` | Communication Intent Processor. |
| `confidence.py` | STT/translation confidence + ambiguity detection. |
| `refine.py` | Post-translation refinement (formality, dialect). |
| `memory.py`, `profile_memory.py` | Conversation memory + per-profile preferences. |
| `sessions.py` | Session registry (TTL, history caps). |
| `speakers.py` | Speaker tracking, language heuristic. |
| `audio.py` | WAV processing helpers and RMS. |
| `tts_pacing.py` | TTS chunking and pacing for low latency. |
| `latency.py` | Latency budget tracking. |
| `circuit_breaker.py` | Trip on cascading failure of an upstream. |
| `service_health.py` | Per-service health and warmup. |
| `security.py` | Auth (HTTP + WebSocket), rate limits, quotas. |
| `observability.py` | Metrics, event logging, Prometheus. |
| `config.py` | Env parsing — see `docs/ENVIRONMENT.md`. |
| `assistant.py` | NAIA assistant integration. |
| `stt_bridge.py`, `stt_client/` | Adapter for the off-process STT provider. |
| `cli.py` | Operational CLI helpers. |

## Concurrency & lifecycle

- App startup pre-warms STT, translation, and TTS models if
  `PRELOAD_MODELS=1`.
- Heavy CPU work (STT, MarianMT) runs on a threadpool via FastAPI's
  `run_in_threadpool`.
- WebSocket handlers track active streams per identity
  (`MAX_ACTIVE_STREAMS_PER_USER`) and per-user audio quota.
- Per-call timeouts (`PIPELINE_STEP_TIMEOUT_SECONDS`) cut off slow stages.
- A circuit breaker shields downstream calls that have been failing.

## Auth model

- HTTP requests: `Authorization: Bearer <jwt>` or an `X-API-Key` header.
- WebSocket requests: token passed via subprotocol or query param. See
  `authenticate_websocket()` in `security.py`.
- Tokens are minted by `POST /auth/login` and have a lifetime of
  `SESSION_MINUTES`.
- API keys live in `API_KEYS` and bypass per-user quotas (intended for
  trusted server-to-server callers).

## Observability

- `observability.py` exposes counters for HTTP, WebSocket, errors, latency
  histograms.
- Structured events are appended to `EVENT_LOG_PATH` (`logs/events.jsonl`).
- Use `GET /metrics` for JSON, `GET /metrics/prometheus` for scraping.

## Adding a route

1. Decide which module owns the behavior (translate, auth, websocket,
   assistant, diagnostics).
2. Add the route handler in `backend/api.py` (or in a sibling module
   imported by `api.py`).
3. Update validation / Pydantic models in the same place — keep them close
   to the route.
4. Wire auth + rate limiting via `Depends(authenticate_http)` and the
   `usage_limiter`.
5. Add tests under `tests/` (use existing tests as templates).
6. Update `docs/API.md` and this guide if the surface changes.
