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
â”œâ