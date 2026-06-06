# Testing Guide

## Offline stack check (no server)

```bash
make verify-local
# or
python scripts/smoke_local.py
```

## Live checks (backend running and LIVE)

```bash
make start-local
make preflight-deploy-live   # recommended: deploy checks + full EN↔HT smoke
make verify-local-live
make verify-bundled-live
make verify-all              # offline imports + full bundled smoke
bash scripts/test_translator.sh http://127.0.0.1:8000
```

Windows: `.\Test-Translator.ps1`

## Deploy preflight (no server required for file checks)

```bash
make preflight-deploy
bash scripts/preflight_deploy.sh --smoke http://127.0.0.1:8000
```

Windows: `powershell -File .\Test-DeploymentReady.ps1 -RunSmoke`

## Backend unit tests

```bash
pip install -r requirements.txt
python -m pytest --ignore=tests/test_stt_integration.py -q
```

If `pytest` is unavailable, targeted smoke checks can still use:

```bash
python -m compileall backend translation speech tts llm tests -q
python -c "import backend.api, backend.streaming; print('imports ok')"
```

## Frontend

```bash
cd frontend
npm ci
npm test -- --run
npm run build
```

## Mobile

```bash
cd translator-mobile
npm ci
npm run lint
npm run build
```

## Prerequisites for full EN↔HT coverage

- **espeak-ng** installed (HT TTS uses eSpeak when no Piper voice exists)
- Models warmed via `make setup-models`
- Backend header shows **LIVE** before mic, conversation, or self-test

Run the checks most closely related to your change first, then broader checks before release.
