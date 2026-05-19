# Contributing to Anai Translator

## Setup

```bash
copy .env.example .env
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

For frontend work:

```bash
cd frontend
npm install
npm run build
```

For mobile work:

```bash
cd translator-mobile
npm install
npm run lint
```

## Quality bar

- Keep changes focused and small.
- Do not commit secrets, downloaded models, generated audio, or local logs.
- Run relevant validation before opening a PR.
- Preserve the main-screen design rule in `README.md`.
