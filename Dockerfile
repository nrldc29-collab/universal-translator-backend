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
    PRELOAD_MODELS=0 \
    TRANSLATION_BACKEND=marian \
    TRANSLATION_DEVICE=cpu \
    HYBRID_ENABLE_MARIAN_FALLBACK=1 \
    HYBRID_ENABLE_REMOTE=0 \
    REMOTE_TRANSLATION_TIMEOUT_SECONDS=0.65 \
    GPU_COST_MODE=low \
    STT_MAX_CONCURRENCY=1 \
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
    TTS_FIRST_CHUNK_CHARS=10 \
    MAX_ACTIVE_STREAMS_PER_USER=5 \
    REQUESTS_PER_MINUTE=120 \
    QUOTA_REQUESTS_PER_HOUR=500 \
    STT_PROVIDER=local \
    NEAR_ZERO_LATENCY_MODE=1 \
    STREAM_BUFFER_MAX_MB=12 \
    HF_HOME=/app/.cache/huggingface \
    TRANSFORMERS_CACHE=/app/.cache/huggingface \
    HUGGINGFACE_HUB_CACHE=/app/.cache/huggingface

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    git \
    espeak-ng \
    && rm -rf /var/lib/apt/lists/*

COPY requirements-railway.txt ./requirements.txt
RUN python -m pip install --no-cache-dir uv && \
    UV_HTTP_TIMEOUT=600 uv pip install --system --no-cache \
    --index-strategy unsafe-best-match \
    -r requirements.txt

COPY backend backend/
COPY llm llm/
COPY speech speech/
COPY translation translation/
COPY tts tts/
COPY ailang ailang/
COPY ailang_integration ailang_integration/
COPY models/tts/ models/tts/
COPY scripts/docker_fetch_piper.sh scripts/docker_fetch_piper.sh
ARG HF_TOKEN=
ENV HF_TOKEN=${HF_TOKEN}
RUN chmod +x scripts/docker_fetch_piper.sh && ./scripts/docker_fetch_piper.sh models/tts
COPY --from=frontend-build /frontend/dist frontend/dist

EXPOSE 8000

CMD ["python", "-m", "backend.app"]
