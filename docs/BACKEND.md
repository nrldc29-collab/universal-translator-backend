# Backend Guide

The backend is a FastAPI service in `backend/` that orchestrates a real-time
speech → translation → speech pipeline. It supports HTTP, Server-Sent updates,
and WebSocket clients (web + mobile).

## Run locally

```bash
python -m venv .venv && source .venv/bin/activate    # or .venv\Scripts\activate on Windows
pip install -r requirements.txt
cp .env.example .env
uvicorn backend.api:app --reload --host 0.0.0.0 --port 8000
```

Interactive API docs are available at <http://localhost:8000/docs>.

## Run 