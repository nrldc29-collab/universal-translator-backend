from pathlib import Path
from uuid import uuid4

from contextlib import asynccontextmanager
from time import time

import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Response, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from backend.conversation import ConversationBrain
from backend.config import (
    LANGUAGES,
    get_allowed_origins,
    get_max_audio_mb,
    get_max_audio_seconds,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_model_size,
)
from backend.pipeline import UniversalTranslatorPipeline
from backend.observability import observability
from backend.security import authenticate_http, authenticate_user, authenticate_websocket, usage_limiter
from backend.sessions import session_registry
from backend.streaming import websocket_audio_translation, websocket_text_translation
from speech import SileroVoiceActivityDetector


runtime_state = {
    "ready": False,
    "started_at": time(),
    "models": {},
}
metrics = {
    "http_requests": 0,
    "websocket_connections": 0,
    "websocket_errors": 0,
}
logger = logging.getLogger("universal_translator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


class TextTranslationRequest(BaseModel):
    text: str
    source_language: str = "en"
    target_language: str = "es"
    tone: str | None = None
    synthesize_audio: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    runtime_state["models"] = {
        "whisper_device": get_whisper_device(),
        "whisper_compute_type": get_whisper_compute_type(),
        "whisper_model_size": get_whisper_model_size(),
        "tts": "piper",
        "vad": "silero",
    }
    runtime_state["ready"] = True
    yield
    runtime_state["ready"] = False


app = FastAPI(title="Universal Translator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
pipeline = UniversalTranslatorPipeline()
vad = SileroVoiceActivityDetector()
conversation_brain = ConversationBrain()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    return {
        "ready": runtime_state["ready"],
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
        "models": runtime_state["models"],
    }


@app.get("/metrics")
def metrics_snapshot(identity: str = Depends(authenticate_http)):
    return {
        "metrics": metrics,
        "usage_last_hour": usage_limiter.snapshot(),
        "audio_usage_minutes_today": usage_limiter.audio_snapshot(),
        "billing_usage": usage_limiter.billing_snapshot(),
        "gpu_queue": pipeline.stt.queue_snapshot(),
        "sessions": session_registry.snapshot(),
        "observability": observability.snapshot(),
    }


@app.get("/analytics")
def analytics(identity: str = Depends(authenticate_http)):
    return {
        "billing_usage": usage_limiter.billing_snapshot(),
        "usage_last_hour": usage_limiter.snapshot(),
        "audio_usage_minutes_today": usage_limiter.audio_snapshot(),
        "gpu_queue": pipeline.stt.queue_snapshot(),
        "observability": observability.snapshot(),
        "metrics": metrics,
    }


@app.get("/metrics/prometheus")
def prometheus_metrics(identity: str = Depends(authenticate_http)):
    return Response(content=observability.prometheus(pipeline.stt.queue_snapshot()), media_type="text/plain")


@app.get("/languages")
def languages():
    return {"languages": LANGUAGES}


@app.post("/auth/login")
def login(request: LoginRequest):
    token = authenticate_user(request.username, request.password)
    return {"access_token": token, "token_type": "bearer"}


@app.post("/translate/text")
def translate_text(request: TextTranslationRequest, identity: str = Depends(authenticate_http)):
    started_at = time()
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    usage_limiter.track(identity, "text_translations")
    logger.info("text_translation identity=%s source=%s target=%s", identity, request.source_language, request.target_language)
    try:
        result = pipeline.translate_text(
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language,
            tone=request.tone,
            synthesize_audio=request.synthesize_audio,
        )
        observability.observe_latency("text_translation", time() - started_at)
        observability.record_event("text_translation", identity=identity, latency_seconds=time() - started_at)
        return result.__dict__
    except Exception:
        usage_limiter.track(identity, "errors")
        observability.increment("translation_failures_total")
        observability.record_event("translation_failure", identity=identity, mode="text")
        raise


@app.post("/translate/audio")
async def translate_audio(
    audio: UploadFile = File(...),
    source_language: str = Form("en"),
    target_language: str = Form("es"),
    synthesize_audio: bool = Form(True),
    identity: str = Depends(authenticate_http),
):
    started_at = time()
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    logger.info("audio_translation identity=%s source=%s target=%s", identity, source_language, target_language)
    audio_bytes = await audio.read()
    max_bytes = get_max_audio_mb() * 1024 * 1024
    if len(audio_bytes) > max_bytes:
        raise HTTPException(status_code=413, detail=f"Audio upload exceeds {get_max_audio_mb()} MB limit.")

    estimated_seconds = max(1, len(audio_bytes) / 16000)
    if estimated_seconds > get_max_audio_seconds():
        raise HTTPException(status_code=413, detail=f"Audio request exceeds {get_max_audio_seconds()} second limit.")

    allowed, remaining_seconds = usage_limiter.check_audio_seconds(identity, estimated_seconds)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Daily audio quota exceeded. Remaining seconds: {int(remaining_seconds)}")

    upload_dir = Path("models/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    audio_path = upload_dir / f"{uuid4()}{suffix}"
    audio_path.write_bytes(audio_bytes)

    try:
        result = await run_in_threadpool(
            pipeline.translate_audio,
            str(audio_path),
            source_language,
            target_language,
            None,
            synthesize_audio,
            f"models/tts/{uuid4()}.wav",
        )
        observability.observe_latency("audio_translation", time() - started_at)
        observability.record_event("audio_translation", identity=identity, latency_seconds=time() - started_at)
        usage_limiter.track_audio(identity, estimated_seconds, "audio_translations")
        return result.__dict__
    except Exception:
        usage_limiter.track(identity, "errors")
        observability.increment("translation_failures_total")
        observability.record_event("translation_failure", identity=identity, mode="audio")
        raise


@app.post("/vad")
async def detect_voice_activity(audio: UploadFile = File(...), identity: str = Depends(authenticate_http)):
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    audio_bytes = await audio.read()
    suffix = Path(audio.filename or "audio.webm").suffix or ".webm"
    return await run_in_threadpool(vad.detect_bytes, audio_bytes, suffix)


@app.websocket("/ws/translate")
async def websocket_translate(websocket: WebSocket):
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    metrics["websocket_connections"] += 1
    logger.info("text_websocket_connected identity=%s", identity)
    try:
        await websocket_text_translation(websocket, pipeline)
    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        observability.record_event("websocket_disconnect", identity=identity, mode="text")
        logger.info("text_websocket_disconnected identity=%s", identity)
    except Exception:
        metrics["websocket_errors"] += 1
        observability.increment("websocket_errors_total")
        observability.record_event("websocket_error", identity=identity, mode="text")
        logger.exception("text_websocket_error identity=%s", identity)
        await websocket.close(code=1011, reason="Internal WebSocket error")


@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    metrics["websocket_connections"] += 1
    logger.info("audio_websocket_connected identity=%s", identity)
    try:
        await websocket_audio_translation(websocket, pipeline, vad, conversation_brain, identity)
    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        observability.record_event("websocket_disconnect", identity=identity, mode="audio")
        logger.info("audio_websocket_disconnected identity=%s", identity)
    except Exception:
        metrics["websocket_errors"] += 1
        observability.increment("websocket_errors_total")
        observability.record_event("websocket_error", identity=identity, mode="audio")
        logger.exception("audio_websocket_error identity=%s", identity)
        await websocket.close(code=1011, reason="Internal WebSocket error")
