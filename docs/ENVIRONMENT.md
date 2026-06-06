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
| `JWT_SECRET` | Must be replaced. Sign auth tokens with a strong value. Generate with `python scripts/generate_secrets.py`. |
| `USERS` | `user:password` pairs separated by commas. Replace `demo:demo`. |
| `USER_TIERS` | `user:tier` mapping (e.g. `alice:pro,bob:free`). |
| `ALLOWED_ORIGINS` | Comma-separated list of frontend origins. |
| `ALLOWED_ORIGIN_REGEX` | Optional regex (LAN dev hosts default). |
| `API_KEYS` | Server-to-server keys for trusted callers. |

## Runtime

| Variable | Default | Notes |
| --- | --- | --- |
| `FRONTEND_URL` | `http://127.0.0.1:5173` | Used in CORS headers and links. |
| `SERVE_FRONTEND_DIST` | `0` | When `1`, FastAPI serves `frontend/dist/` directly. |
| `FRONTEND_DIST_DIR` | `frontend/dist` | Path the backend serves. |
| `EVENT_LOG_PATH` | `logs/events.jsonl` | Structured event log. |
| `PRELOAD_MODELS` | `1` | Warm STT/translation/TTS at startup. |

## Auth, quotas, and abuse limits

| Variable | Default | Notes |
| --- | --- | --- |
| `REQUESTS_PER_MINUTE` | `20` | Per-identity request ceiling. |
| `QUOTA_REQUESTS_PER_HOUR` | `120` | Hourly ceiling per identity. |
| `FREE_DAILY_AUDIO_MINUTES` | `10` | Audio quota for free-tier users. |
| `SESSION_MINUTES` | `480` | JWT lifetime. |
| `SESSION_TTL_SECONDS` | `1800` | In-memory session retention. |
| `SESSION_HISTORY_LIMIT` | `20` | Max turns retained per session. |

## Speech-to-text (Whisper)

| Variable | Default | Notes |
| --- | --- | --- |
| `USE_GPU` | `0` | `1` enables CUDA. |
| `WHISPER_DEVICE` | `cpu` | `cuda` for GPU. |
| `WHISPER_COMPUTE_TYPE` | `int8` | Use `float16` on GPU for quality. |
| `WHISPER_MODEL_SIZE` | `tiny` | `tiny`, `base`, `small`, `medium`, `large`. |
| `WHISPER_CPU_THREADS` | `4` | CPU-only inference threads. |
| `WHISPER_NUM_WORKERS` | `1` | Parallel decoders. |
| `WHISPER_BEAM_SIZE` | `1` | Higher → more accurate, slower. |
| `STT_MAX_CONCURRENCY` | `2` | Concurrent STT calls. |
| `STT_QUEUE_MAX_DEPTH` | `8` | Reject when queue is fuller than this. |

## Translation

| Variable | Default | Notes |
| --- | --- | --- |
| `TRANSLATION_BACKEND` | `hybrid` | `hybrid`, `marian`, `remote`. |
| `TRANSLATION_DEVICE` | `cpu` | `cuda` to use GPU MT. |
| `REMOTE_TRANSLATION_TIMEOUT_SECONDS` | `0.65` | When the remote path is enabled. |
| `HYBRID_ENABLE_MARIAN_FALLBACK` | `1` | Fall back to local MarianMT if remote is slow. |
| `CIP_MODE` / `CIP_DEFAULT_MODE` | `ut_first` | CIP brain mode. |
| `CIP_PROCESS_URL` | _(empty)_ | CIP brain URL when off-process. |
| `CIP_TIMEOUT_SECONDS` | `0.65` | Per-call timeout. |
| `CIP_RETRIES` | `0` | Retry budget. |
| `CIP_CONFIDENCE_THRESHOLD` | `0.42` | Below this the user is asked to clarify. |
| `CIP_AMBIGUITY_THRESHOLD` | `0.68` | Above this CIP issues a clarification. |

## Streaming & VAD

| Variable | Default | Notes |
| --- | --- | --- |
| `MAX_AUDIO_MB` | `25` | Upload ceiling. |
| `MAX_AUDIO_SECONDS` | `300` | Duration ceiling. |
| `CLIENT_VAD_MODE` | `1` | Use the browser-side VAD signal. |
| `CLIENT_VAD_THRESHOLD` | `0.055` | Energy threshold for client VAD. |
| `VAD_RECENT_CHUNKS` | `2` | Sliding window for server VAD. |
| `VAD_SILENT_CHECKS` | `1` | Silent chunks before flush. |
| `VAD_FORCE_FINAL_SECONDS` | `0.25` | Force end-of-utterance after silence. |
| `SPEECH_MERGE_MS` | `40` | Merge near-adjacent speech windows. |
| `MIN_SPEECH_BYTES` | `4000` | Reject too-small chunks. |
| `PARTIAL_STT_MIN_BYTES` | `1200` | When to emit a partial STT result. |
| `PARTIAL_STT_INTERVAL_MS` | `100` | Throttle partial STT emissions. |
| `PARTIAL_TRANSLATION_MIN_WORDS` | `1` | Min words before partial translation. |
| `PARTIAL_TTS_MODE` | `1` | `1` enables partial TTS playback. |
| `NEAR_ZERO_LATENCY_MODE` | `1` | Aggressive partial emit + caching. |
| `STREAM_BUFFER_MAX_MB` | `12` | Per-socket buffer cap. |
| `MAX_ACTIVE_STREAMS_PER_USER` | `4` | Per-identity concurrency cap (conversation uses 2). |
| `PIPELINE_STEP_TIMEOUT_SECONDS` | `10` | Cut off slow STT/translation/TTS calls. |
| `STREAM_HOT_PATH_LOGGING` | `0` | Verbose per-frame logging. |

## Text-to-speech (Piper / cloud)

| Variable | Default | Notes |
| --- | --- | --- |
| `TTS_CHUNK_CHARS` | `14` | Chunk size for streaming TTS. |
| `TTS_FIRST_CHUNK_CHARS` | `10` | Smaller first chunk to bring first audio earlier. |
| `PREFER_CLOUD_TTS` | `0` | Use cloud voices when available. |
| `GOOGLE_TTS_API_KEY` | _(empty)_ | Required for Google voices. |
| `ELEVENLABS_API_KEY` | _(empty)_ | Required for ElevenLabs voices. |

## STT provider service (optional, off-process)

When you run the streaming STT provider as a separate service (see
`docker-compose.yml`), the backend talks to it over WebSocket.

| Variable | Default | Notes |
| --- | --- | --- |
| `STT_PROVIDER` | `local` | `streaming` to use the off-process service. |
| `STT_PROVIDER_URL` | `http://127.0.0.1:8002` | HTTP base URL. |
| `STT_PROVIDER_WS_URL` | `ws://127.0.0.1:8002/stt/stream` | WebSocket URL. |
| `STT_PROVIDER_API_KEY` | _(empty)_ | Must match `STT_API_KEYS` on the provider. |

See `docs/STT_PROVIDER_CAPACITY.md` for capacity planning.

## Frontend variables (`frontend/.env.example`)

| Variable | Purpose |
| --- | --- |
| `VITE_API_URL` | Backend HTTP base URL. |
| `VITE_WS_URL` | Backend WebSocket base URL. |
| `VITE_WS_AUDIO_URL` | Override for `/ws/audio`. |
| `VITE_STREAM_PACKET_MS` | Audio chunk cadence. |
| `VITE_STREAM_AUDIO_BITRATE` | Opus bitrate. |
| `VITE_CLIENT_VAD_THRESHOLD` | Client-side VAD threshold. |
| `VITE_FAST_SPEECH_TIMEOUT_MS` | Fast-speech path timeout. |
| `VITE_FAST_TTS_TIMEOUT_MS` | Fast TTS path timeout. |
| `VITE_MIN_STREAM_CAPTURE_MS` | Minimum capture window. |
| `VITE_LIVE_SPEECH_TEXT_THROTTLE_MS` | Caption update throttle. |

## Mobile variables (`translator-mobile/.env.example`)

| Variable | Purpose |
| --- | --- |
| `EXPO_PUBLIC_API_URL` | Backend URL. |
| `EXPO_PUBLIC_DEBUG_LOGS` | `1` enables verbose logs in the mobile build. |

## Things that should never be committed

- Real `.env` files (`.env`, `.env.production`, `frontend/.env.local`, etc.).
- Downloaded model files under `models/`.
- Generated TTS audio cache, uploads, profiles, or `logs/`.

The provided `.gitignore` already excludes these.
