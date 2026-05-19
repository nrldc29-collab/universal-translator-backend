# Dockerfile for True Streaming STT Provider
# Self-hosted streaming and batch speech-to-text service built on FastAPI and faster-whisper.

FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for audio processing
RUN apt-get update && apt-get install -y \
    build-essential \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY stt_server ./stt_server
COPY .env.example .env

# Expose the FastAPI server port
EXPOSE 8002

# Run the FastAPI application with uvicorn
CMD ["uvicorn", "stt_server.main:app", "--host", "0.0.0.0", "--port", "8002"]
