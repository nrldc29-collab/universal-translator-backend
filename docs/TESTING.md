# Testing Guide

## Backend

```bash
pip install -r requirements.txt
pytest
```

If `pytest` is unavailable, targeted smoke checks can still use:

```bash
python -m compileall backend translation speech tts llm tests -q
python -c "import backend.api, backend.streaming; print('imports ok')"
```

## Frontend

```bash
cd frontend
npm install
npm run build
```

## Mobile

```bash
cd translator-mobile
npm install
npm run lint
npm run build
```

Run the checks most closely related to your change first, then broader checks before release.
