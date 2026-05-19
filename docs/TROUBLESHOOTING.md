# Troubleshooting

## Backend will not start

- Confirm `.env` exists or required platform env vars are configured.
- Run `python -m compileall backend translation speech tts llm tests -q`.
- Check `JWT_SECRET`, `USERS`, and numeric env values.

## Browser microphone does not work

- Use HTTPS or localhost.
- Confirm browser microphone permission is granted.
- Check `/health`, `/ready`, and `/diagnostics`.

## WebSocket fails

- Confirm `/ws/audio` is reachable through the reverse proxy.
- Enable WebSocket upgrade headers.
- Check `ALLOWED_ORIGINS` and frontend `VITE_API_URL`.

## Mobile cannot connect

- On a real phone, do not use `127.0.0.1` for the backend.
- Set `EXPO_PUBLIC_API_URL` to the computer/server LAN or public HTTPS URL.
- Confirm the backend listens on `0.0.0.0` for LAN testing.

## TTS has no audio

- Confirm Piper voice files exist in `models/tts/`.
- Check `/debug/tts-sample.wav`.
- Inspect logs for TTS synthesis errors.
