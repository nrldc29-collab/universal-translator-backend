from pathlib import Path
from uuid import uuid4

from contextlib import asynccontextmanager
from html import escape
import json
import os
from time import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request as UrlRequest, urlopen

import logging

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from starlette.websockets import WebSocketDisconnect

from backend.conversation import ConversationBrain
from backend.config import (
    LANGUAGES,
    get_allowed_origin_regex,
    get_allowed_origins,
    get_frontend_dist_dir,
    get_frontend_url,
    get_max_audio_mb,
    get_max_audio_seconds,
    get_min_speech_bytes,
    get_preload_models,
    get_speech_merge_ms,
    get_serve_frontend_dist,
    get_vad_force_final_seconds,
    get_vad_silent_checks,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_model_size,
)
from backend.pipeline import UniversalTranslatorPipeline
from backend.observability import observability
from backend.security import WEBSOCKET_AUTH_RELEASE, authenticate_http, authenticate_user, authenticate_websocket, usage_limiter
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
RELEASE_ID = "2026-05-10-haitian-creole-v10"
logger = logging.getLogger("universal_translator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


class TextTranslationRequest(BaseModel):
    text: str
    source_language: str = "en"
    target_language: str = "es"
    tone: str | None = None
    synthesize_audio: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


def _local_frontend_url(request: Request) -> str:
    frontend_url = get_frontend_url()
    if frontend_url == "http://127.0.0.1:5173":
        host = request.headers.get("host", "").split(":", 1)[0]
        if host in {"localhost", "127.0.0.1"} or host.startswith(("192.168.", "10.", "172.")):
            return f"{request.url.scheme}://{host}:5173"
    return frontend_url


def _frontend_dist_dir() -> Path:
    dist_dir = Path(get_frontend_dist_dir())
    if not dist_dir.is_absolute():
        dist_dir = Path.cwd() / dist_dir
    return dist_dir


def _frontend_index_path() -> Path | None:
    index_path = _frontend_dist_dir() / "index.html"
    if get_serve_frontend_dist() and index_path.is_file():
        return index_path
    return None


def _frontend_asset_path(full_path: str) -> Path | None:
    try:
        dist_dir = _frontend_dist_dir().resolve()
        asset_path = (dist_dir / full_path).resolve()
    except OSError:
        return None

    if asset_path.is_file() and (asset_path == dist_dir or dist_dir in asset_path.parents):
        return asset_path
    return None


def _embedded_frontend_response(full_path: str = "") -> FileResponse | None:
    index_path = _frontend_index_path()
    if not index_path:
        return None

    if full_path:
        asset_path = _frontend_asset_path(full_path)
        if asset_path:
            return FileResponse(asset_path)

    return FileResponse(index_path)


def _frontend_launcher(frontend_url: str) -> HTMLResponse:
    frontend_href = escape(frontend_url, quote=True)
    frontend_js = json.dumps(frontend_url)
    return HTMLResponse(f"""<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <meta http-equiv="refresh" content="0; url={frontend_href}" />
    <title>Opening Universal Translator</title>
    <style>
      body {{
        margin: 0;
        min-height: 100vh;
        display: grid;
        place-items: center;
        font-family: system-ui, sans-serif;
        background: #07111f;
        color: #e5ecff;
      }}
      main {{
        width: min(520px, calc(100vw - 32px));
        border: 1px solid rgba(148, 163, 184, .3);
        border-radius: 18px;
        padding: 24px;
        background: #0f172a;
        box-shadow: 0 20px 60px rgba(0, 0, 0, .35);
      }}
      a {{
        display: inline-flex;
        margin-top: 12px;
        min-height: 48px;
        align-items: center;
        justify-content: center;
        padding: 0 18px;
        border-radius: 999px;
        background: #2563eb;
        color: white;
        font-weight: 800;
        text-decoration: none;
      }}
    </style>
  </head>
  <body>
    <main>
      <h1>Opening Universal Translator...</h1>
      <p>If it does not open automatically, use the button below.</p>
      <a href="{frontend_href}">Open app</a>
    </main>
    <script>window.location.replace({frontend_js});</script>
  </body>
</html>""")


def _frontend_proxy_response(content: bytes, status_code: int, upstream_headers) -> Response:
    headers = {}
    media_type = None
    for name, value in upstream_headers.items():
        lower_name = name.lower()
        if lower_name == "content-type":
            media_type = value
        elif lower_name not in HOP_BY_HOP_HEADERS:
            headers[name] = value
    return Response(content=content, status_code=status_code, media_type=media_type, headers=headers)


def _proxy_frontend(request: Request, full_path: str = "") -> Response:
    frontend_url = _local_frontend_url(request).rstrip("/")
    path = quote(full_path, safe="/@._-")
    upstream_url = f"{frontend_url}/{path}" if path else f"{frontend_url}/"
    if request.url.query:
        upstream_url = f"{upstream_url}?{request.url.query}"

    try:
        upstream_request = UrlRequest(upstream_url, headers={"User-Agent": "UniversalTranslatorLocalProxy/1.0"})
        with urlopen(upstream_request, timeout=8) as upstream:
            return _frontend_proxy_response(upstream.read(), upstream.status, upstream.headers)
    except HTTPError as exc:
        return _frontend_proxy_response(exc.read(), exc.code, exc.headers)
    except URLError:
        return _frontend_launcher(frontend_url)


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    runtime_state["models"] = {
        "whisper_device": get_whisper_device(),
        "whisper_compute_type": get_whisper_compute_type(),
        "whisper_model_size": get_whisper_model_size(),
        "tts": "piper",
        "vad": "silero",
    }
    runtime_state["warming"] = get_preload_models()
    if get_preload_models():
        runtime_state["models"]["preloaded"] = await run_in_threadpool(pipeline.preload)
    runtime_state["warming"] = False
    runtime_state["ready"] = True
    yield
    runtime_state["ready"] = False


app = FastAPI(title="Universal Translator", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=get_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
pipeline = UniversalTranslatorPipeline()
vad = SileroVoiceActivityDetector()
conversation_brain = ConversationBrain()


@app.get("/")
def root(request: Request):
    embedded_frontend = _embedded_frontend_response()
    if embedded_frontend:
        return embedded_frontend
    return _proxy_frontend(request)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/debug/version")
async def debug_version():
    return {
        "release": RELEASE_ID,
        "environment": os.getenv("ENVIRONMENT", ""),
        "users_configured": bool(os.getenv("USERS", "")),
        "api_keys_configured": bool(os.getenv("API_KEYS", "")),
        "anonymous_websocket": True,
        "websocket_auth_release": WEBSOCKET_AUTH_RELEASE,
    }


@app.get("/api/debug/version")
async def api_debug_version():
    return await debug_version()


@app.get("/ready")
def ready():
    return {
        "ready": runtime_state["ready"],
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
        "models": runtime_state["models"],
    }


@app.get("/diagnostics")
def diagnostics(request: Request):
    frontend_index = _frontend_index_path()
    if frontend_index:
        frontend = {
            "target": str(_frontend_dist_dir()),
            "mode": "embedded_dist",
            "reachable": True,
            "status_code": 200,
        }
    else:
        frontend_url = _local_frontend_url(request).rstrip("/")
        frontend = {
            "target": frontend_url,
            "mode": "dev_proxy",
            "reachable": False,
            "status_code": None,
        }
        try:
            upstream_request = UrlRequest(f"{frontend_url}/", headers={"User-Agent": "UniversalTranslatorDiagnostics/1.0"})
            with urlopen(upstream_request, timeout=1.5) as upstream:
                frontend["reachable"] = 200 <= upstream.status < 500
                frontend["status_code"] = upstream.status
        except Exception as exc:
            frontend["error"] = exc.__class__.__name__

    return {
        "status": "ok",
        "ready": runtime_state["ready"],
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
        "served_from": str(request.base_url).rstrip("/"),
        "frontend": frontend,
        "models": runtime_state["models"],
        "streaming": {
            "websocket_path": "/ws/audio",
            "vad_silent_checks": get_vad_silent_checks(),
            "vad_force_final_seconds": get_vad_force_final_seconds(),
            "speech_merge_ms": get_speech_merge_ms(),
            "min_speech_bytes": get_min_speech_bytes(),
        },
        "limits": {
            "max_audio_mb": get_max_audio_mb(),
            "max_audio_seconds": get_max_audio_seconds(),
        },
        "queues": {
            "stt": pipeline.stt.queue_snapshot(),
        },
        "sessions": session_registry.snapshot(),
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


@app.get("/debug/tts-sample.wav")
async def tts_sample():
    output_path = Path("models/tts/debug-sample.wav")
    try:
        if not output_path.is_file():
            await run_in_threadpool(pipeline.tts.synthesize, "This is a voice test.", str(output_path))
    except Exception as exc:
        logger.exception("tts_sample_failed")
        raise HTTPException(status_code=503, detail=f"TTS sample unavailable: {exc}") from exc
    return FileResponse(str(output_path), media_type="audio/wav", filename="tts-sample.wav", headers={"Cache-Control": "no-store"})


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
    logger.info("audio_websocket_auth_start release=%s", WEBSOCKET_AUTH_RELEASE)
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        logger.warning("audio_websocket_auth_rejected identity=%s", identity)
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


@app.websocket("/ws/ping")
async def websocket_ping(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"type": "ready", "release": RELEASE_ID, "websocket_auth_release": WEBSOCKET_AUTH_RELEASE})
    await websocket.close()


@app.get("/{full_path:path}")
def frontend_dev_asset(full_path: str, request: Request):
    embedded_frontend = _embedded_frontend_response(full_path)
    if embedded_frontend:
        return embedded_frontend
    return _proxy_frontend(request, full_path)
