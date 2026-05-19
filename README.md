# Anai Translator

A futuristic, self-hosted real-time translation system designed to reduce language barriers without relying on external APIs or usage quotas.

## Missing-files checklist

This repo now includes the operational files needed for safer local setup and CI:

- `.env.example` — copy to `.env` and customize local secrets/settings.
- `pytest.ini` — standard test discovery config.
- `models/**/.gitkeep` — keeps required model directories present without committing downloaded models.
- `requirements.txt` — includes runtime dependencies plus `pytest` for local validation.

## Design Rule

From this point onward, do not add more main-screen UI elements. Only refine spacing, animation, smoothness, and speed. Keep the primary experience focused on the app title, language direction, microphone, transcript, and translation.

## Project Goal

Build a local pipeline that can:

- Convert speech to text
- Translate text into another language
- Convert translated text into natural speech
- Run locally or on your own server without API dependency

The **NAIA Assistant** (bundled in `naia/`) provides an in-app conversational AI that can rephrase translations, explain idioms, and answer language questions. It is optional — the translator works fully without it, and the backend returns HTTP 503 for assistant endpoints when the naia kernel is unavailable.

## Architecture

```text
Microphone Input
      ↓
Speech-to-Text (STT)
      ↓
Translation Engine
      ↓
Text-to-Speech (TTS)
      ↓
Audio Output
```

## Project Structure

```text
anai-translator/
├── backend/            # Production FastAPI backend and streaming pipeline
├── speech/             # Speech-to-text models and adapters
├── translation/        # Translation models and adapters
├── tts/                # Text-to-speech models and adapters
├── llm/                # Optional context model integration
├── naia/               # NAIA AI assistant runtime (governed cognition, memory, tools)
├── frontend/           # PWA user interface
├── translator-mobile/  # Expo mobile app
├── tests/              # Backend and integration checks
├── scripts/            # Setup and utility scripts
├── hf-space/           # Hugging Face Space deployment files
├── research/           # Experimental code kept off the production import path
├── archive/            # Legacy deploy/mobile artifacts kept out of production builds
├── models/             # Downloaded local model files
└── README.md
```

## Core Components

- **Speech-to-Text:** `speech/whisper_stt.py` uses `faster-whisper` to convert audio files into text.
- **Translation Engine:** `translation/marian_translator.py` uses MarianMT models from Hugging Face.
- **Text-to-Speech:** `tts/piper_tts.py` uses Piper to convert translated text into audio.
- **Optional LLM Layer:** `llm/context_layer.py` currently passes text through unchanged and can be replaced with a local LLM enhancer later.

## Backend Pipeline

The components are connected in `backend/pipeline.py`.

```text
Audio file or text input
      ↓
WhisperSpeechToText
      ↓
PassthroughContextLayer
      ↓
MarianTranslator
      ↓
PiperTextToSpeech
```

## Setup Instructions

### Step 1: Clone the Repository

```bash
git clone https://github.com/nrldc29-collab/universal-translator-backend.git universal-translator
cd universal-translator
```

If you already have this folder locally, open it instead:

```bash
cd universal-translator
```

### Step 2: Set Up Python Environment

Create a virtual environment:

```bash
python -m venv venv
```

Activate it on Mac/Linux:

```bash
source venv/bin/activate
```

Activate it on Windows:

```bash
venv\Scripts\activate
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

Copy the environment template and edit values as needed:

```bash
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

### Step 4: Download Models

Create the local model folders:

```bash
mkdir models\whisper models\translation models\tts
```

Expected model layout:

```text
models/
├── whisper/
├── translation/
└── tts/
```

Download or cache the models used by each component:

- **Speech model:** Whisper or `faster-whisper`
- **Translation model:** MarianMT or NLLB
- **TTS model:** Piper or Coqui TTS

The current implementation loads most models through Python packages and may download/cache them automatically on first use.

Piper is the default TTS backend. The default voice is downloaded to:

```text
models/tts/en_US-lessac-medium.onnx
```

Download the default Piper voice manually if needed:

```bash
python -m piper.download_voices --download-dir models\tts en_US-lessac-medium
```

Coqui TTS is optional because it does not currently support every Python version.

Optional Coqui install on a compatible Python version:

```bash
pip install -r requirements-tts.txt
```

### Step 5: Start Backend

```bash
cd backend
python app.py
```

### Step 6: Start Frontend

```bash
cd frontend
npm install
npm run dev
```

## Run from CLI

Translate text:

```bash
python -m backend.cli --text "Hello, how are you?" --source en --target es
```

Translate audio and generate speech:

```bash
python -m backend.cli --audio input.wav --source en --target es --output models/output.wav
```

## Run API Server

```bash
uvicorn backend.api:app --reload
```

Then open:

```text
http://127.0.0.1:8000/docs
```

## Validation

Run backend checks:

```bash
pytest
```

Run frontend build:

```bash
cd frontend
npm install
npm run build
```

Run mobile checks:

```bash
cd translator-mobile
npm install
npm run lint
npm run build
```

More references:

- `docs/ENVIRONMENT.md`
- `docs/OPERATIONS.md`
- `docs/TESTING.md`
- `docs/LOCAL_DEVELOPMENT.md`
- `docs/API.md`
- `docs/ARCHITECTURE.md`
- `docs/DEPLOYMENT_CHECKLIST.md`
- `docs/BACKEND.md`
- `docs/FRONTEND.md`
- `docs/MOBILE.md`
- `docs/TROUBLESHOOTING.md`
- `docs/RELEASE_CHECKLIST.md`

## Frontend

The React frontend lives in `frontend/` and includes:

- **Mic button:** records browser microphone audio and uploads it to `/translate/audio`.
- **Text translation:** sends text to `/translate/text`.
- **Streaming text mode:** connects to `/ws/translate` with WebSocket messages.
- **Language dropdowns:** loads supported languages from `/languages`.

Install Node.js first, then run:

```bash
cd frontend
npm install
npm run dev
```

Then open:

```text
http://127.0.0.1:5173
```

## Real-Time Streaming

The backend includes a WebSocket endpoint:

```text
ws://127.0.0.1:8000/ws/translate
```

Text streaming uses `/ws/translate`.

Audio streaming uses:

```text
ws://127.0.0.1:8000/ws/audio
```

Audio WebSocket flow:

```text
Client JSON: {"type":"start","source_language":"en","target_language":"es"}
Client binary: WebM audio chunks
Server: Silero VAD checks incoming chunks
Server JSON: {"type":"vad","speech_detected":true}
Server: when VAD detects speech end, run STT
Server JSON: {"type":"final_transcription","text":"..."}
Server JSON: {"type":"live_translation","text":"..."}
Server JSON: {"type":"final", ...}
```

The frontend `Stream Audio` button sends microphone chunks over WebSocket. The backend owns VAD, finalization, STT, translation, and TTS in one streaming pipeline.

Manual finalization is still supported:

```text
Client JSON: {"type":"finalize"}
```

## Step 8A: Perceived Speed

The streaming pipeline sends useful updates as soon as each stage is ready instead of waiting for the entire pipeline to finish.

Perception-speed flow:

```text
VAD detects speech
↓
UI shows "Speech detected"
↓
VAD finalizes speech
↓
Backend sends STT stage update
↓
Backend sends final transcription immediately
↓
Backend translates
↓
Backend sends live translation immediately
↓
Backend creates TTS audio
↓
Backend sends final result
```

WebSocket stage messages:

```json
{"type":"stage","stage":"stt","message":"Speech finalized. Transcribing now..."}
{"type":"stage","stage":"translation","message":"Transcription ready. Translating..."}
{"type":"stage","stage":"tts","message":"Translation ready. Creating voice..."}
```

The frontend displays a `Pipeline` status so the app feels active even while heavier model work is running.

## Step 8B: Streaming TTS

The app streams translated speech output in chunks instead of waiting for one full TTS file.

Streaming TTS flow:

```text
Translation ready
↓
Split translated text into chunks
↓
Generate Piper audio for chunk 1
↓
Send chunk 1 to frontend and play immediately
↓
Generate Piper audio for chunk 2
↓
Send chunk 2 while chunk 1 is playing
↓
Continue until all chunks are sent
```

WebSocket TTS messages:

```json
{"type":"tts_start","chunks":2}
{"type":"tts_audio_chunk","index":1,"total":2,"mime_type":"audio/wav","audio_base64":"..."}
{"type":"tts_audio_chunk","index":2,"total":2,"mime_type":"audio/wav","audio_base64":"..."}
{"type":"tts_end"}
```

The frontend queues audio chunks and plays them as soon as they arrive, so the user hears translated speech while later chunks are still being generated.

## Step 9: Full Duplex Conversation

The app supports two active speaker directions:

```text
Speaker A → System → Speaker B
Speaker B → System → Speaker A
```

Frontend duplex controls:

- **Speaker A → Speaker B:** uses the selected source language as A and target language as B.
- **Speaker B → Speaker A:** reverses the selected languages.
- **Both streams can be active:** each speaker gets an independent microphone WebSocket stream.

Backend duplex behavior:

- Each audio WebSocket sends a `speaker` field.
- The same `/ws/audio` pipeline handles both directions.
- Every result is tagged with the speaker:

```json
{"type":"final_transcription","speaker":"A","text":"..."}
{"type":"live_translation","speaker":"A","text":"..."}
{"type":"final","speaker":"A","source_text":"...","translated_text":"..."}
```

Duplex mode still uses:

- **Silero VAD**
- **faster-whisper STT**
- **MarianMT/NLLB translation**
- **Piper streaming TTS**

## Step 10: Conversation Brain

The duplex system includes a central arbitration layer:

```text
backend/conversation.py
```

The `ConversationBrain` acts as a traffic controller for live conversation.

It coordinates:

- **Turn ownership:** prevents both speakers from being processed as the active turn at the same time.
- **Playback ownership:** prevents double playback while translated speech is being spoken.
- **Denied turns:** blocks a speaker if the other side currently owns the floor or playback.
- **Turn completion:** releases the lock after final translation/TTS completes.

Turn messages are sent over WebSocket:

```json
{"type":"turn","speaker":"A","allowed":true,"reason":"Turn granted","active_speaker":"A","playback_owner":null}
{"type":"turn","speaker":"B","allowed":false,"reason":"Other speaker has the floor","active_speaker":"A","playback_owner":null}
{"type":"turn","speaker":"A","allowed":true,"reason":"Turn complete","active_speaker":null,"playback_owner":null}
```

The frontend displays the current `Conversation Brain` status and stops a denied speaker stream automatically.

## Step 11: Human-Like Conversation Behavior

The Conversation Brain now behaves less like a rigid lock and more like a live interpreter.

Human-like policies:

- **Soft overlap:** a brief overlap window is allowed instead of immediately blocking the second speaker.
- **Natural interruption:** if playback has been going long enough, the other speaker can interrupt naturally.
- **Playback grace period:** very early interruptions are briefly held so audio does not instantly collide.
- **Turn shift after pause:** if the first speaker has held the floor long enough, a new speaker can take over.
- **Behavior labels:** turn events include a `behavior` field so the UI can show what happened.

Example behavior events:

```json
{"type":"turn","speaker":"B","allowed":true,"reason":"Soft overlap allowed","behavior":"overlap"}
{"type":"turn","speaker":"B","allowed":true,"reason":"Natural interruption accepted","behavior":"interruption"}
{"type":"turn","speaker":"B","allowed":false,"reason":"Briefly holding for playback","behavior":"hold"}
{"type":"turn","speaker":"B","allowed":true,"reason":"Turn shifted after pause","behavior":"turn_shift"}
```

This makes interruptions, pauses, and slight overlap feel more natural while still preventing chaotic double playback.

## Step 12: Semantic Conversation Layer

The system now tracks meaning across the conversation, not just timing.

Semantic state is stored in the `ConversationBrain` and updated after each transcription.

It tracks:

- **Intent:** question, request, apology, gratitude, agreement, disagreement, statement.
- **Tone:** neutral, polite, urgent, emphatic.
- **Topics:** recurring important words from recent turns.
- **Mood:** neutral, polite, urgent, tense.
- **Recent semantic turns:** compact context from the last few speaker turns.

Backend semantic message:

```json
{
  "type": "semantic_context",
  "speaker": "A",
  "last_intent": "question",
  "conversation_mood": "polite",
  "topics": ["help", "schedule"],
  "recent_turns": []
}
```

Final streaming results also include `semantic_context`, allowing the interpreter layer to adapt future translation behavior using evolving meaning.

The frontend displays the current semantic layer:

```text
intent question, mood polite, topics help, schedule
```

## Step 13: Production Deployment Architecture

Production layout:

```text
Global static frontend
        ↓ HTTPS/WSS
GPU backend server
        ↓
Models loaded once in process
        ↓
Whisper + Silero VAD + Marian/NLLB + Piper
```

### Backend production features

- **Env-driven CORS:** configure allowed frontend domains with `ALLOWED_ORIGINS`.
- **Stable WebSockets:** production Uvicorn uses ping interval and ping timeout.
- **Single worker for GPU models:** keep `workers=1` so models load once and GPU memory is predictable.
- **Health check:** `GET /health`.
- **Readiness check:** `GET /ready`.
- **Restart-safe Docker:** `docker-compose.gpu.yml` uses `restart: unless-stopped`.
- **GPU container:** `Dockerfile.backend` uses NVIDIA CUDA runtime.

### GPU backend deployment

```bash
docker compose -f docker-compose.gpu.yml up --build -d
```

Required server setup:

- NVIDIA GPU driver
- NVIDIA Container Toolkit
- Docker Compose
- Mounted `models/` folder containing local TTS/model files

Example production environment:

```bash
ALLOWED_ORIGINS=https://your-frontend.example.com
USE_GPU=1
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
WHISPER_MODEL_SIZE=base
ENVIRONMENT=production
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
```

### Frontend deployment

The frontend can be hosted globally on Netlify/Vercel/static hosting.

Create `frontend/.env`:

```bash
VITE_API_URL=https://your-gpu-backend.example.com
```

Build:

```bash
npm run build
```

The frontend automatically converts:

```text
https://your-gpu-backend.example.com
```

to:

```text
wss://your-gpu-backend.example.com
```

for WebSocket streaming.

### Reverse proxy requirements

If using Nginx/Caddy/Traefik, ensure:

- WebSocket upgrade headers are enabled.
- HTTPS is enabled.
- Idle timeout is long enough for live conversation.
- `/health` and `/ready` are accessible for monitoring.

## Product Hardening

The production layer includes authentication, quotas, metrics, logging, and connection recovery.

### Authentication

The app supports JWT user sessions.

Set users and a JWT signing secret:

```bash
USERS=alice:strong-password,bob:another-password
JWT_SECRET=replace-with-a-long-random-secret
SESSION_MINUTES=480
```

Login:

```http
POST /auth/login
Content-Type: application/json

{"username":"alice","password":"strong-password"}
```

Response:

```json
{"access_token":"...","token_type":"bearer"}
```

HTTP requests use:

```text
Authorization: Bearer <access_token>
```

WebSockets use:

```text
wss://your-backend/ws/audio?access_token=<access_token>
```

The frontend includes a `User Session` login panel and stores the JWT in local storage.

API keys are still supported for service-to-service access with `API_KEYS`, but user sessions should use JWT login.

### Quotas

Set request and audio quotas:

```bash
QUOTA_REQUESTS_PER_HOUR=120
REQUESTS_PER_MINUTE=20
FREE_DAILY_AUDIO_MINUTES=10
MAX_AUDIO_MB=25
MAX_AUDIO_SECONDS=300
USER_TIERS=alice:free,bob:pro
```

Tier behavior:

- **Free users:** limited by `FREE_DAILY_AUDIO_MINUTES`.
- **Pro users:** unlimited daily audio minutes.

Audio protection:

- **Max request size:** `MAX_AUDIO_MB`.
- **Max segment/request duration:** `MAX_AUDIO_SECONDS`.
- **Streaming segments:** checked before STT/translation/TTS to protect GPU usage.

When quota is exceeded:

- HTTP returns `429`.
- WebSocket closes with policy violation.

### Monitoring

Protected metrics endpoint:

```text
GET /metrics
```

Returns:

- HTTP request count
- WebSocket connection count
- WebSocket error count
- Per-key usage in the last hour
- Daily audio usage in minutes

### WebSocket recovery

Backend behavior:

- Authenticates before accepting work.
- Logs connect/disconnect/error events.
- Closes failed sockets with `1011` for internal errors.
- Stores speaker/session bindings in `backend/sessions.py`.
- Sends `session_restored` after a reconnect binds the same speaker again.

Frontend behavior:

- Sends the login JWT with HTTP and WebSocket requests.
- Displays stream connection errors.
- Stops local mic tracks when sockets close or fail.
- Persists a `translator_session_id` in local storage.
- Sends `session_id` with every audio WebSocket `start` message.
- Automatically reconnects duplex Speaker A/B streams after unexpected drops.
- Rebinds the same speaker direction after reconnect.

Session restore message:

```json
{
  "type": "session_restored",
  "session": {
    "session_id": "...",
    "speaker": "A",
    "connected": true,
    "reconnects": 1
  }
}
```

Monitoring includes active/recent sessions:

```text
GET /metrics
```

### Logging and monitoring

The backend writes structured JSONL events to:

```text
logs/events.jsonl
```

Tracked events include:

- Text translation latency
- Audio translation latency
- Streaming segment latency
- Failed translations
- WebSocket disconnects
- WebSocket errors

The JSON metrics endpoint includes an `observability` section:

```text
GET /metrics
```

Prometheus-compatible metrics are available at:

```text
GET /metrics/prometheus
```

Example metrics:

```text
anai_translator_translation_failures_total
anai_translator_websocket_disconnects_total
anai_translator_websocket_errors_total
anai_translator_text_translation_latency_seconds_avg
anai_translator_audio_translation_latency_seconds_avg
anai_translator_streaming_segment_latency_seconds_avg
anai_translator_gpu_memory_used_mb
anai_translator_gpu_utilization_percent
```

GPU metrics can be supplied by the runtime environment:

```bash
GPU_MEMORY_USED_MB=0
GPU_UTILIZATION_PERCENT=0
EVENT_LOG_PATH=logs/events.jsonl
```

For a production setup, point Prometheus at `/metrics/prometheus` and build Grafana panels for latency, disconnect rate, failures, and GPU utilization.

### GPU cost controls

The backend keeps models loaded once per process and limits STT concurrency to avoid GPU stampedes.

Cost-related settings:

```bash
GPU_COST_MODE=balanced
STT_MAX_CONCURRENCY=1
WHISPER_BEAM_SIZE=1
WHISPER_MODEL_SIZE=base
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
```

Low-cost mode:

```bash
GPU_COST_MODE=low
WHISPER_MODEL_SIZE=tiny
STT_MAX_CONCURRENCY=1
WHISPER_BEAM_SIZE=1
```

Recommended modes:

- **Lowest GPU cost:** `tiny`, `beam_size=1`, `STT_MAX_CONCURRENCY=1`.
- **Balanced quality/cost:** `base`, `beam_size=1`, `STT_MAX_CONCURRENCY=1`.
- **Higher throughput:** increase `STT_MAX_CONCURRENCY` only if GPU memory and latency remain stable.

STT calls are serialized by default through a bounded semaphore so multiple users cannot overload Whisper at the same time.

### Latency optimization

The streaming pipeline is tuned for lower perceived response latency.

Frontend packet timing:

```bash
VITE_STREAM_PACKET_MS=250
```

Backend low-latency knobs:

```bash
TTS_CHUNK_CHARS=70
VAD_RECENT_CHUNKS=3
VAD_SILENT_CHECKS=1
WHISPER_BEAM_SIZE=1
```

What these do:

- **VAD buffering:** fewer recent chunks and one silent check finalize speech sooner.
- **TTS chunk size:** shorter text chunks start audio playback earlier.
- **WebSocket packet size:** 250ms audio packets reduce time before backend VAD sees speech.
- **Translation/STT decoding:** `WHISPER_BEAM_SIZE=1` reduces decode latency.

For more stability on poor networks, increase packet size:

```bash
VITE_STREAM_PACKET_MS=500
```

### Memory stability for long sessions

The backend bounds long-running memory growth.

Memory-related settings:

```bash
STREAM_BUFFER_MAX_MB=12
SEMANTIC_HISTORY_LIMIT=12
TOPIC_LIMIT=25
SESSION_TTL_SECONDS=1800
```

Protection behavior:

- **Audio buffers:** streaming audio buffers reset if they exceed `STREAM_BUFFER_MAX_MB`.
- **Temp audio files:** uploaded streaming segment files are deleted after processing.
- **Conversation history:** semantic history is capped by `SEMANTIC_HISTORY_LIMIT`.
- **Topic memory:** topic counters are pruned to `TOPIC_LIMIT`.
- **Inactive sessions:** disconnected sessions older than `SESSION_TTL_SECONDS` are removed during session bind/snapshot.

Frontend env:

```bash
VITE_API_URL=https://your-gpu-backend.example.com
```

## Productization and Real-World Adoption

The frontend includes product-focused improvements for real users.

## Native Mobile App

The project now includes a separate React Native mobile frontend in:

```text
translator-mobile/
```

This does not replace the backend or AI pipeline. The mobile app reuses the existing FastAPI backend for:

- **JWT login**
- **Language list**
- **Audio translation**
- **Analytics**
- **Shared session IDs**

## Phase 1: PWA Launch

The web frontend is installable as a PWA for fast real-world testing without app store approval.

PWA files:

```text
frontend/public/manifest.json
frontend/public/sw.js
frontend/src/pwa.js
```

Frontend build:

```bash
cd frontend
npm install
npm run build
```

Deploy `frontend/` to Netlify or Vercel and set:

```bash
VITE_API_URL=https://your-backend.example.com
```

Production WebSocket URLs are derived automatically:

```text
https://your-backend.example.com -> wss://your-backend.example.com
http://localhost:8000 -> ws://localhost:8000
```

The frontend includes an `Install App` button. On supported Chrome/Android devices, users can install it to the home screen for a fullscreen app-like experience.

Backend remains the same:

```text
FastAPI -> WebSocket -> GPU AI pipeline
```

Production backend requirements:

- **HTTPS/WSS:** required for browser mic and secure WebSocket.
- **Reverse proxy:** Caddy, Nginx, RunPod proxy, or cloud load balancer.
- **Allowed origins:** include your deployed frontend URL.

## Phase 2: App Store Wrap

After PWA testing stabilizes, use the Expo app in `translator-mobile/` as the native shell.

Reuse:

- **WebSocket system**
- **AI pipeline**
- **Translation engine**
- **Conversation brain**
- **Backend auth/analytics/limits**

Build:

```bash
cd translator-mobile
npm install
npm start
```

Later, use EAS Build for Android APK/AAB and iOS App Store packages.

App store build files:

```text
translator-mobile/app.json
translator-mobile/eas.json
translator-mobile/.env.example
```

Before production builds, replace these placeholders:

```text
com.yourcompany.anaitranslator
replace-with-eas-project-id
https://your-backend.example.com
```

Production mobile connection:

```text
Mobile App -> WSS -> FastAPI backend -> AI pipeline -> response
```

The mobile app reads:

```bash
EXPO_PUBLIC_API_URL=https://your-backend.example.com
```

and converts it to WebSocket automatically:

```text
https://your-backend.example.com -> wss://your-backend.example.com/ws/audio
```

EAS build examples:

```bash
cd translator-mobile
npm install
npx eas login
npx eas build:configure
npx eas build --platform android --profile preview
npx eas build --platform android --profile production
npx eas build --platform ios --profile production
```

Build outputs:

- **Preview Android:** APK for internal testing.
- **Production Android:** AAB for Google Play.
- **Production iOS:** iOS archive for App Store Connect.

Important:

- The backend is not rebuilt for app stores.
- The backend must use HTTPS/WSS in production.
- Microphone permission text is configured in `translator-mobile/app.json`.
- Use the PWA testing phase to stabilize before submitting to stores.

### Run the mobile app

Install mobile dependencies:

```bash
cd translator-mobile
npm install
```

Start Expo:

```bash
npm start
```

Then open the app with:

- **Android:** Expo Go or Android emulator
- **iOS:** Expo Go or iOS simulator on macOS

### Backend URL on a real phone

If testing on a real device, `127.0.0.1` points to the phone, not your computer.

Set the app's backend URL to your computer LAN address:

```text
http://192.168.1.25:8000
```

For this machine, the detected Wi-Fi IPv4 address was:

```text
http://192.168.12.243:8000
```

Keep the backend running:

```bash
venv\Scripts\python -m uvicorn backend.api:app --host 0.0.0.0 --port 8000
```

### Mobile features

- **Native microphone access:** uses `expo-av` recording APIs.
- **Large mic button:** primary tap target for recording and translating.
- **Speaker A/B toggle:** assign turns before recording.
- **Live translation box:** shows source and translated text in a mobile-first panel.
- **Audio playback control:** replay the last local recording for confidence checks.
- **WebSocket readiness:** `Connect Stream` opens `/ws/audio` with the JWT access token.
- **JWT storage:** stores the login token with `expo-secure-store`.
- **Shared sessions:** stores and edits the same session ID used by the web app.
- **Audio upload:** records locally, then sends the file to `/translate/audio`.
- **Analytics:** reads `/analytics` using the user's JWT.

### Mobile streaming test order

Use this order to verify the full mobile data flow:

1. **Log in** with a valid user to get a JWT.
2. **Connect Stream** to open `/ws/audio`.
3. Confirm the stream status changes after ping/pong.
4. **Start Streaming Audio** to send chunked binary audio frames.
5. Speak into the phone microphone.
6. Watch for VAD/STT status updates and live translation text.
7. Stop streaming to send `finalize`.
8. Listen for streamed TTS playback on the phone.

The mobile app sends short recorded chunks as binary WebSocket frames. The backend receives those bytes in `backend/streaming.py`, runs VAD, then finalizes into STT, translation, and TTS.

### Mobile audio pipeline implementation

The mobile audio pipeline is implemented in strict A to D order:

#### Step A: Microphone streaming

```text
translator-mobile/services/audio-stream.js
```

Expo does not provide true low-level PCM streaming by default, so the app uses the prototype-safe approach:

- Record short clips.
- Convert each clip to an `ArrayBuffer`.
- Pass each chunk to the stream callback.

#### Step B: Binary WebSocket frames

```text
translator-mobile/App.js
translator-mobile/services/ws.js
```

The app sends each audio chunk directly:

```text
streamSocketRef.current.send(audioChunk)
```

#### Step C: VAD + STT backend

```text
backend/streaming.py
```

The backend receives binary frames and routes them through:

```text
WebSocket bytes -> Silero VAD -> Whisper STT -> Translation
```

#### Step D: TTS playback on phone

```text
translator-mobile/services/audio-stream.js
```

The app receives `tts_audio_chunk`, writes the base64 audio to a temporary file, and plays it with `expo-av`.

### Mobile latency and debug checklist

Backend console logs include:

```text
AUDIO RECEIVED: <bytes>
VAD: True|False
STT: <recognized text>
TRANSLATION: <translated text>
```

Mobile UI shows:

```text
Latency: mic_to_backend: <ms>
Latency: backend_response: <ms>
Chunks sent: <count> (<KB> KB)
```

Latency targets:

- **Excellent:** under 500ms
- **Acceptable:** 500-1200ms
- **Needs optimization:** 1500ms or higher

Expected fix knobs:

- **Reduce chunk size:** mobile streaming now uses `500ms` chunks by default.
- **Improve VAD sensitivity:** tune VAD thresholds and silent checks.
- **Fix TTS queue:** mobile TTS playback uses a single queue to avoid overlap.
- **Stabilize WebSocket:** mobile sends heartbeat `ping` every 15 seconds.

### Latency, noise, and scaling optimization pass

Current optimization defaults:

```bash
NEAR_ZERO_LATENCY_MODE=1
STREAM_HOT_PATH_LOGGING=0
PARTIAL_STT_MIN_BYTES=12000
PARTIAL_STT_INTERVAL_MS=900
TTS_CHUNK_CHARS=55
VAD_RECENT_CHUNKS=3
VAD_SILENT_CHECKS=1
MIN_SPEECH_BYTES=18000
SPEECH_MERGE_MS=300
MAX_ACTIVE_STREAMS_PER_USER=2
STT_MAX_CONCURRENCY=1
STT_QUEUE_MAX_DEPTH=8
```

Implemented upgrades:

- **Pipeline latency:** smaller mobile chunks and smaller TTS chunks reduce perceived wait.
- **Near-zero perceived latency:** partial STT/translation updates are emitted before final sentence commit.
- **Translation cache:** repeated phrase translations are cached in memory.
- **TTS preload hook:** the TTS model path is checked during warmup-ready flows.
- **Speech smoothing:** short bursts are ignored and short silence gaps are merged.
- **Real-world VAD controls:** `MIN_SPEECH_BYTES` and `SPEECH_MERGE_MS` provide tuning knobs.
- **Scaling guardrail:** `MAX_ACTIVE_STREAMS_PER_USER` limits concurrent active streams per user.

Next tuning loop:

1. Measure `mic_to_backend` and `backend_response`.
2. If `mic_to_backend` is high, reduce mobile chunk size toward `300-400ms`.
3. If VAD false-positives occur, increase `MIN_SPEECH_BYTES`.
4. If speech is cut off, increase `SPEECH_MERGE_MS`.
5. If TTS overlaps, keep the mobile TTS queue enabled and reduce `TTS_CHUNK_CHARS` carefully.

### Near-zero perceived latency mode

This mode does not make full STT + translation + TTS complete in 300ms. Instead, it makes the app feel live by overlapping work and showing early partial output.

Flow:

```text
Audio chunks arrive
VAD detects speech
Partial STT runs while audio continues
Partial translation appears before final sentence
Final STT/translation/TTS corrects the result
```

Backend controls:

```bash
NEAR_ZERO_LATENCY_MODE=1
PARTIAL_STT_MIN_BYTES=12000
PARTIAL_STT_INTERVAL_MS=900
STREAM_HOT_PATH_LOGGING=0
```

Mobile shows:

- **Source:** partial transcription while speaking.
- **Partial:** early translation guess.
- **Translated:** final or latest partial translation.

For production-grade true streaming STT, replace the Expo short-clip prototype with a native PCM module and an incremental STT decoder.

### Emotion-based TTS pacing

The backend now builds TTS pacing metadata before voice generation:

```json
{
  "text": "I am sorry, I cannot do that",
  "emotion": "apologetic",
  "intent": "refusal",
  "urgency": "low",
  "style": {
    "speed": 0.85,
    "pitch": 0.95,
    "pause_seconds": 0.5,
    "tone": "soft"
  }
}
```

Implemented in:

```text
backend/tts_pacing.py
backend/streaming.py
translator-mobile/App.js
```

Emotion detection is lightweight and rule-based for speed:

- **Apologetic:** sorry/apology language or refusal intent.
- **Excited:** exclamation-heavy speech.
- **Curious:** questions or question intent.
- **Serious:** urgent/emergency wording.
- **Neutral:** fallback.

The backend sends:

```text
tts_style
tts_audio_chunk.emotion
tts_audio_chunk.intent
tts_audio_chunk.urgency
tts_audio_chunk.tts_style
```

The mobile app displays the detected emotion, intent, urgency, and tone/speed style. Piper does not directly expose all prosody controls here, so the current implementation applies pacing through segmentation and pause-aware metadata, while keeping the style fields ready for a TTS engine that supports speed/pitch controls.

### UI/UX refinement

- Quick-start onboarding panel.
- Clean three-step onboarding screen.
- Microphone permission setup flow.
- Backend and microphone status indicators.
- Dedicated language direction picker.
- Clear single-speaker and duplex conversation controls.
- Visible connection, pipeline, semantic, and conversation-brain status.
- Larger touch targets for mobile and tablet use.

### Onboarding flow

The app now guides users to:

1. Pick source and target languages.
2. Use `Stream Audio` for one-speaker live translation.
3. Use `Start A Mic` and `Start B Mic` for two-person conversation.
4. Place each device close to its speaker for accuracy.

### Mobile compatibility

The UI uses responsive one-column layouts on small screens and full-width action buttons for touch use.

Mobile support includes:

- **Touch-friendly controls:** larger tap targets on small screens.
- **Low-bandwidth mode:** increases stream packet size to reduce packet churn and skips streamed TTS playback on the client.
- **Mobile audio unlock:** provides an `Unlock Audio` button to satisfy mobile browser autoplay rules.
- **Stable mobile layout:** disables overscroll bounce and improves long text wrapping.
- **Safer form controls:** 16px mobile input/select text to avoid browser zoom jumps.

### Multi-device sessions

Multiple devices can join the same conversation by using the same signed-in user and shared session ID.

Backend session sync settings:

```bash
SESSION_HISTORY_LIMIT=20
SESSION_TTL_SECONDS=1800
```

How it works:

- **Shared session ID:** enter the same session ID on each device.
- **Device binding:** each WebSocket binds its speaker/device into the shared session.
- **Conversation sync:** completed turns are stored in shared session history.
- **Reconnect restore:** joining or reconnecting devices receive the latest shared session state.
- **History view:** the frontend shows recent shared turns so devices can catch up.

### Usage tracking, analytics, and GPU queue

The backend tracks per-user usage for limits and billing.

Tracked usage:

- **HTTP requests**
- **Text translations**
- **Audio translations**
- **Streaming segments**
- **Audio seconds/minutes**
- **Errors**

Analytics endpoint:

```text
GET /analytics
Authorization: Bearer <access_token>
```

The frontend includes an `Analytics Dashboard` panel that shows:

- **GPU queue:** active jobs, queued jobs, rejected jobs, average wait.
- **Latency:** text/audio average latency.
- **Errors:** translation failures and WebSocket disconnects.
- **Billing usage:** per-user request and audio usage totals.

GPU queue settings:

```bash
STT_MAX_CONCURRENCY=1
STT_QUEUE_MAX_DEPTH=8
```

If the queue is full, STT rejects new work with a retryable overload error instead of overloading the GPU.

### Accessibility and real-world speech

Conversation settings include:

- **Balanced**
- **Noisy room**
- **Strong accent**
- **Slower conversation**

The UI provides live tips for noise, accents, and turn pacing.

### Multi-device support

For better real-world duplex use:

- Open the frontend on two devices.
- Assign one device to Speaker A.
- Assign the other device to Speaker B.
- Keep each microphone close to the assigned speaker.

## Silero VAD Speech Finalization

The app uses Silero VAD on the backend before finalizing audio.

VAD behavior:

- **Real VAD engine:** `speech/silero_vad.py` loads `snakers4/silero-vad`.
- **Unified streaming pipeline:** `/ws/audio` runs VAD and STT together.
- **Detects speech onset:** finalization starts only after Silero detects speech.
- **Ignores pre-speech silence:** does not finalize just because the room is quiet before you talk.
- **Detects speech end:** finalizes after sustained post-speech silence.
- **Applies to recording and streaming:** both `Record Mic` and `Stream Audio` use VAD.

VAD endpoint:

```text
POST /vad
```

This endpoint is still available for diagnostics, but streaming audio uses `/ws/audio` directly.

This avoids splitting sentences too early, for example:

```text
Bad:  "I go to..." + "store"
Good: "I go to store"
```

Current audio flow:

```text
Listen
↓
Buffer chunks locally
↓
Detect speech with VAD
↓
Detect post-speech silence
↓
Merge into one WebM clip
↓
Upload to /translate/audio
↓
Transcribe, translate, synthesize
```

## GPU Speed Optimization

Whisper can use GPU acceleration through environment variables:

```bash
set USE_GPU=1
set WHISPER_DEVICE=cuda
set WHISPER_COMPUTE_TYPE=float16
set WHISPER_MODEL_SIZE=base
uvicorn backend.api:app --reload
```

Use `small`, `medium`, or `large-v3` for better accuracy if your GPU has enough memory.

Latency tuning defaults:

- **Whisper model:** `base`
- **CPU compute:** `int8`
- **GPU compute:** `float16`
- **Backend audio processing:** threadpool worker to avoid blocking the API event loop

## Supported Languages

The backend exposes supported language codes at:

```text
GET /languages
```

Current defaults include English, Spanish, French, German, Italian, Portuguese, Dutch, Russian, Chinese, Japanese, Korean, Arabic, and Hindi.

## Real Usage Test Checklist

Test with full sentences, not only single words:

- **Long sentence:** “I am going to the store after work because I need groceries.”
- **Pause mid-sentence:** “I am going to...” then pause, then say “the store.”
- **Fast speech:** speak naturally at a faster pace.
- **Noisy background:** run a fan, music, or room noise while speaking.
- **Language pairs:** test EN → ES, EN → FR, EN → DE, and another pair supported by the dropdown.
- **UX states:** confirm the UI shows “Listening...”, “Processing...”, and “Playing...” at the right times.

Additional references:

- docs/ARCHITECTURE.md
- docs/DEPLOYMENT_CHECKLIST.md

## Governance and Support

- `CONTRIBUTING.md`
- `SECURITY.md`
- `CODE_OF_CONDUCT.md`
- `SUPPORT.md`
- `LICENSE`
- `CHANGELOG.md`
