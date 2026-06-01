# Mobile Guide

The mobile client is an Expo (React Native) app living in `translator-mobile/`.
It targets iOS, Android, and a web export for testing.

## Quick start

```bash
cd translator-mobile
npm install
npm start            # open the Expo dev server (QR for Expo Go)
npm run android      # launch on a connected Android device/emulator
npm run ios          # launch on a connected iOS device/simulator
npm run web          # browser export for quick UI iteration
npm run lint         # expo lint (ESLint + Expo rules)
npm run build        # `expo export --platform web` → dist/
```

The Expo dev server prints a `exp://…` URL plus a LAN URL. On a phone,
install **Expo Go** and either scan the QR or paste the URL.

## Folder layout

```
translator-mobile/
├── App.js                  # root component
├── app/                    # screens / routes
├── components/             # UI sections (Duplex, Settings, Semantic, etc.)
├── hooks/                  # custom hooks
├── services/
│   ├── ws.js               # WebSocket lifecycle for /ws/audio
│   └── audio-stream.js     # recording, encoding, playback
├── constants/              # design tokens, colors, sizes
├── assets/                 # icons + splash
├── app.json                # Expo metadata + branding
├── eas.json                # EAS build profiles (dev / preview / production)
├── eslint.config.js
├── tsconfig.json
└── package.json
```

## Runtime config

The app reads its backend URL from `EXPO_PUBLIC_API_URL`. Copy
`translator-mobile/.env.example` to `translator-mobile/.env`:

```env
EXPO_PUBLIC_API_URL=https://your-backend.example.com
EXPO_PUBLIC_DEBUG_LOGS=0
```

The fallback default in `app.json` (`extra.apiUrl`) is used only if the env
var is missing.

## Permissions

The app requests microphone access on first launch (see `app.json` →
`plugins` and the `expo-av` permissions block). Without microphone access
the mic button stays disabled and the duplex mode is unavailable.

## Key components

- **`Assistant.js`** — chat panel mirroring the web NAIA assistant.
- **`DuplexMode.tsx`** — two-speaker conversation mode (each speaker has a
  separate transcript lane).
- **`SemanticContext.tsx`** — surface for showing detected topic/intent.
- **`AdvancedFeatures.tsx`** — settings for streaming, VAD threshold, voice.
- **`SettingsScreen.tsx`** — user-facing preferences (saved to AsyncStorage).
- **`AnimatedCard.tsx`, `GradientHeader.tsx`** — shared visual primitives.

## Building production binaries (EAS)

EAS builds are configured in `eas.json` with three profiles: `development`,
`preview`, and `production`. Typical flow:

```bash
npx eas login
npx eas build --profile preview --platform ios
npx eas build --profile production --platform android
```

Submission to the App Store / Play Store uses `npx eas submit`.

## Web export

`npm run build` produces a static web export in `translator-mobile/dist/`,
which is useful for quick UI demos but is **not** the recommended end-user
web client. For the polished PWA, see `frontend/`.

## CI

The mobile package is part of CI (`.github/workflows/ci.yml` → `mobile`
job): it runs `npm ci`, `npm run lint`, then `npm run build`. Keep both
lint and build clean before pushing.
