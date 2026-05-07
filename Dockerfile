FROM node:20-alpine AS frontend-build

WORKDIR /frontend

COPY frontend/package*.json ./
RUN npm ci

COPY frontend/ ./
RUN npm run build


FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    BACKEND_HOST=0.0.0.0 \
    SERVE_FRONTEND_DIST=1 \
    FRONTEND_DIST_DIR=frontend/dist \
    USE_GPU=0 \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    WHISPER_MODEL_SIZE=tiny \
    WHISPER_CPU_THREADS=4 \
    WHISPER_NUM_WORKERS=1 \
    PRELOAD_MODELS=1 \
    TRANSLATION_DEVICE=cpu \
    GPU_COST_MODE=low \
    STT_MAX_CONCURRENCY=2 \
    WHISPER_BEAM_SIZE=1 \
    VAD_RECENT_CHUNKS=2 \
    VAD_FORCE_FINAL_SECONDS=0.35 \
    SPEECH_MERGE_MS=80 \
    MIN_SPEECH_BYTES=4000 \
    PARTIAL_STT_MIN_BYTES=4000 \
    PARTIAL_STT_INTERVAL_MS=250 \
    PIPELINE_STEP_TIMEOUT_SECONDS=10 \
    TTS_CHUNK_CHARS=26

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    git \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-railway.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY backend backend/
COPY llm llm/
COPY speech speech/
COPY translation translation/
COPY tts tts/
COPY models/tts/en_US-lessac-medium.onnx models/tts/en_US-lessac-medium.onnx
COPY models/tts/en_US-lessac-medium.onnx.json models/tts/en_US-lessac-medium.onnx.json
COPY --from=frontend-build /frontend/dist frontend/dist

EXPOSE 8000

CMD ["python", "-m", "backend.app"]
