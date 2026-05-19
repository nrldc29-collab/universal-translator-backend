# Anai Translator Frontend

Vite/React PWA client for Anai Translator.

## Setup

```bash
npm install
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

## Run

```bash
npm run dev
```

## Build

```bash
npm run build
```

## Environment

- `VITE_API_URL` — FastAPI backend base URL.
- `VITE_WS_URL` — optional WebSocket base URL.
- `VITE_WS_AUDIO_URL` — optional direct `/ws/audio` URL.
- `VITE_STREAM_PACKET_MS` — browser audio packet cadence.
- `VITE_STREAM_AUDIO_BITRATE` — browser recorder bitrate.
- `VITE_CLIENT_VAD_THRESHOLD` — local voice activity threshold.
- `VITE_FAST_SPEECH_TIMEOUT_MS` — speech timeout threshold.
- `VITE_FAST_TTS_TIMEOUT_MS` — TTS timeout threshold.

More details: `docs/FRONTEND.md`.
