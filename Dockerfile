FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ENVIRONMENT=production \
    BACKEND_HOST=0.0.0.0 \
    USE_GPU=0 \
    WHISPER_DEVICE=cpu \
    WHISPER_COMPUTE_TYPE=int8 \
    WHISPER_MODEL_SIZE=tiny \
    GPU_COST_MODE=low \
    STT_MAX_CONCURRENCY=1 \
    WHISPER_BEAM_SIZE=1

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

EXPOSE 8000

CMD ["python", "-m", "backend.app"]
