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
    TRANSLATION_BACKEND=hybrid \
    TRANSLATION_DEVICE=cpu \
    REMOTE_TRANSLATION_TIMEOUT_SECONDS=0.65 \
    GPU_COST_MODE=low \
    STT_MAX_CONCURRENCY=2 \
    WHISPER_BEAM_SIZE=1 \
    VAD_RECENT_CHUNKS=2 \
    VAD_FORCE_FINAL_SECONDS=0.25 \
    SPEECH_MERGE_MS=40 \
    MIN_SPEECH_BYTES=4000 \
    PARTIAL_STT_MIN_BYTES=1200 \
    PARTIAL_STT_INTERVAL_MS=100 \
    PARTIAL_TRANSLATION_MIN_WORDS=1 \
    CLIENT_VAD_MODE=1 \
    CLIENT_VAD_THRESHOLD=0.055 \
    PARTIAL_TTS_MODE=1 \
    CIP_DEFAULT_MODE=ut_first \
    PIPELINE_STEP_TIMEOUT_SECONDS=10 \
    TTS_CHUNK_CHARS=14 \
    TTS_FIRST_CHUNK_CHARS=10

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    git \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-railway.txt ./requirements.txt
RUN python -m pip install --no-cache-dir --upgrade pip && \
    python -m pip install --no-cache-dir -r requirements.txt

COPY backend backend/
COPY llm llm/
COPY speech speech/
COPY translation translation/
COPY tts tts/
RUN mkdir -p models/tts && \
    curl -L --fail -o models/tts/en_US-lessac-medium.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx && \
    curl -L --fail -o models/tts/en_US-lessac-medium.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json && \
    curl -L --fail -o models/tts/es_MX-claude-high.onnx https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx && \
    curl -L --fail -o models/tts/es_MX-claude-high.onnx.json https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json
COPY --from=frontend-build /frontend/dist frontend/dist

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

CMD ["python", "-m", "backend.app"]
