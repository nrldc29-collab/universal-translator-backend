# AGENTS.md

## Cursor Cloud specific instructions

### Product overview

**Anai Translator** is a self-hosted real-time speech → translation → speech stack. For typical web development you need:

| Service | Port | Required? |
|---------|------|-----------|
| FastAPI backend (`uvicorn backend.api:app`) | 8000 | Yes |
| Vite frontend (`npm run dev` in `frontend/`) | 5173 | Yes for UI |
| `stt_provider` | 8002 | Only when `STT_PROVIDER=streaming` or root `docker-compose.yml` |

Default `.env.example` uses `STT_PROVIDER=local` (in-process Whisper), so no separate STT container is needed for local E2E.

### One-time system packages (Ubuntu)

`python3 -m venv` fails until `python3.12-venv` is installed:

```bash
sudo apt-get update -qq && sudo apt-get install -y -qq python3.12-venv python3.12-dev build-essential
```

### Environment files

Copy examples before first run (not committed):

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env.local
```

Set local frontend API URLs in `frontend/.env.local`:

- `VITE_API_URL=http://127.0.0.1:8000`
- `VITE_WS_URL=ws://127.0.0.1:8000`
- `VITE_WS_AUDIO_URL=ws://127.0.0.1:8000/ws/audio`

**Do not** `source .env` in bash: `ALLOWED_ORIGIN_REGEX` contains parentheses and will break the shell. The backend loads `.env` via `backend/config.py`.

`.env.example` is UTF-8 with BOM. After `cp`, strip BOM or the first line may confuse shell tools:

```bash
sed -i '1s/^\xEF\xBB\xBF//' .env
```

Demo login (from `.env.example`): `demo` / `demo`.

### Starting dev servers

Use **tmux** (or separate terminals). Do **not** put these in the VM update script.

Backend (from repo root, with `venv` activated):

```bash
uvicorn backend.api:app --host 127.0.0.1 --port 8000
```

Frontend:

```bash
cd frontend && npm run dev -- --host 127.0.0.1 --port 5173
```

`PRELOAD_MODELS=0` in `.env` speeds startup; Marian/Whisper/Piper weights download on first use. Piper TTS may warn until voice ONNX files exist under `models/tts/`; `espeak-ng` is an optional fallback.

### Lint / test / build (see also `Makefile`)

| Area | Command |
|------|---------|
| Backend tests (CI-like) | `pytest --ignore=tests/test_websocket_integration.py --ignore=tests/test_stt_integration.py` |
| Backend compile smoke | `make backend-compile` |
| Backend lint | `pip install ruff && ruff check backend translation speech tts llm tests` (many existing findings) |
| Frontend unit tests | `cd frontend && npm run test` |
| Frontend production build | `cd frontend && npm run build` |
| Full validate (no pytest) | `make validate` |

Nine pytest cases in `test_circuit_breaker.py` and `test_stream_session.py` expect `pytest-asyncio` (not in `requirements.txt`) and fail without it; the rest of the suite passes.

### API smoke test (no browser)

```bash
curl -sS http://127.0.0.1:8000/health
TOKEN=$(curl -sS -X POST http://127.0.0.1:8000/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","password":"demo"}' | python3 -c 'import sys,json; print(json.load(sys.stdin)["access_token"])')
curl -sS -X POST http://127.0.0.1:8000/translate/text \
  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' \
  -d '{"text":"Hello","source_language":"en","target_language":"es","synthesize_audio":false}'
```

### Frontend runtime note

As of this setup session, `frontend/src/main.jsx` calls `useAutoConversation({ authToken, ... })` before `useAuth()` declares `authToken`, which triggers `ReferenceError: Cannot access 'authToken' before initialization` in the browser. The dev server and Vitest still pass; use the API smoke test above until that hook order is fixed.
