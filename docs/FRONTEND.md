# Frontend Guide

The web client is a Vite + React 19 PWA living in `frontend/`.

## Quick start

```bash
cd frontend
npm install
npm run dev        # http://localhost:5173, hot-reload
npm run build      # builds dist/
npm run preview    # serves dist/ for a final smoke test
```

The dev server is configured to allow LAN access (`server.allowedHosts: true`
in `vite.config.js`), which is required for testing audio capture on a phone
on the same Wi-Fi.

## Folder layout

```
frontend/
├── src/
│   ├── main.jsx          # entrypoint + top-level Translator app
│   ├── Assistant.jsx     # NAIA chat panel (opens via floating button)
│   ├── ErrorBoundary.jsx # top-level error UI
│   ├── pwa.js            # service-worker registration helper
│   └── styles.css        # full visual design (CSS only — no Tailwind)
├── public/
│   ├── manifest.json     # PWA manifest
│   ├── sw.js             # service worker
│   ├── install.html      # PWA install landing page
│   ├── offline.html      # offline fallback
│   └── icons/            # PWA icons
├── dist/                 # build output (also embedded in the backend Docker image)
├── index.html
├── package.json
├── vite.config.js
├── netlify.toml          # Netlify deploy config
├── vercel.json           # Vercel deploy config
└── vercel.local.json     # local override for `vercel dev`
```

## Runtime config

The frontend reads runtime config from Vite env vars. Copy
`frontend/.env.example` to `frontend/.env.local` and edit:

| Variable | Purpose | Example |
| --- | --- | --- |
| `VITE_API_URL` | HTTP base URL for backend | `https://api.example.com` |
| `VITE_WS_URL` | WebSocket base URL | `wss://api.example.com` |
| `VITE_WS_AUDIO_URL` | Direct override for `/ws/audio` | `wss://api.example.com/ws/audio` |
| `VITE_STREAM_PACKET_MS` | Audio chunk size sent over WS | `80` |
| `VITE_STREAM_AUDIO_BITRATE` | Opus bitrate for capture | `32000` |
| `VITE_CLIENT_VAD_THRESHOLD` | Browser-side VAD energy threshold | `0.055` |
| `VITE_FAST_SPEECH_TIMEOUT_MS` | Timeout for fast-speech path | `10000` |
| `VITE_FAST_TTS_TIMEOUT_MS` | Timeout for fast TTS path | `10000` |
| `VITE_MIN_STREAM_CAPTURE_MS` | Minimum capture before flush | `1800` |
| `VITE_LIVE_SPEECH_TEXT_THROTTLE_MS` | Throttle for live caption updates | `90` |

If the page is served from the same origin as the API (Railway, Cloudflare
tunnel, Fly.dev, Render, or localhost), the frontend autodetects the backend
URL and you can leave `VITE_API_URL` unset. See `defaultApiUrl()` in
`main.jsx`.

## Auth flow

1. The user's JWT is stored in `localStorage` as `translator_token` after a
   successful `POST /auth/login`.
2. WebSocket connections include the token as a query param
   (`?token=…`) or via `Sec-WebSocket-Protocol`, depending on the host.
3. The `Assistant` component (NAIA) shares the same token and a per-session
   id for context continuity.

## Components

- **`main.jsx`** — top-level Translator UI: language pickers, microphone,
  transcript, translation, voice settings, partial-stream rendering, share
  link, install prompt.
- **`Assistant.jsx`** — chat panel that reuses the translation context (most
  recent source/target text) so the user can say "make that more formal" or
  "what does that idiom mean?".
- **`ErrorBoundary.jsx`** — catches render errors and offers a reload.

## Design rules

Per the project README, the main screen stays focused on **title, language
direction, microphone, transcript, translation**. New top-level UI elements
should not be added; instead, refine spacing, animation, smoothness, and
speed. Secondary actions (settings, install prompt, share link, assistant)
belong in floating buttons or modal panels.

## PWA notes

- `public/manifest.json` and `public/sw.js` are served as-is and not built
  by Vite.
- `pwa.js` registers `sw.js` after first paint to avoid blocking the main
  thread.
- The service worker caches the app shell and the model warmup audio for
  offline use; data calls are always live.

## Deploy

The frontend can be deployed independently (Vercel, Netlify, Cloudflare
Pages) or bundled into the FastAPI image (root `Dockerfile`'s multi-stage
build copies `frontend/dist` into `/app/frontend/dist` and the backend serves
it when `SERVE_FRONTEND_DIST=1`).

See `DEPLOYMENT.md` for the full guide.
