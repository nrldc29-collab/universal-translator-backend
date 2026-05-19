# Anai Translator Mobile

Expo mobile client for the Anai real-time translator.

## Setup

```bash
npm install
copy .env.example .env
```

On macOS/Linux:

```bash
cp .env.example .env
```

Set `EXPO_PUBLIC_API_URL` to the backend URL.

## Run

```bash
npm start
```

Useful targets:

```bash
npm run android
npm run ios
npm run web
```

## Validate

```bash
npm run lint
npm run build
```

## Environment

- `EXPO_PUBLIC_API_URL` — FastAPI backend base URL.
- `EXPO_PUBLIC_DEBUG_LOGS` — set to `1` for verbose client diagnostics.

More details: `docs/MOBILE.md`.
