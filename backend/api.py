import base64
import asyncio
import hashlib
from pathlib import Path
from uuid import uuid4

from contextlib import asynccontextmanager, suppress
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
from pydantic import BaseModel, field_validator
from starlette.websockets import WebSocketDisconnect
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from backend.conversation import ConversationBrain
from backend.memory import ConversationMemory
from backend.refine import refine_translation
from backend.speakers import SpeakerMemory, detect_language_heuristic
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
    get_stt_provider,
    get_stt_provider_url,
    get_stt_provider_ws_url,
    get_translation_backend,
    get_translation_device,
    get_hybrid_enable_remote,
    get_vad_force_final_seconds,
    get_vad_silent_checks,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_model_size,
    get_google_tts_api_key,
    validate_production_config,
)
from backend.service_health import get_service_health_manager
from translation import HybridTranslator, LightweightTranslator, MarianTranslator
from backend.pipeline import AnaiTranslatorPipeline
from backend.observability import observability
from backend.security import WEBSOCKET_AUTH_RELEASE, authenticate_http, authenticate_user, authenticate_websocket, usage_limiter
from backend.sessions import session_registry
from backend.streaming import websocket_audio_translation, websocket_text_translation
from speech import SileroVoiceActivityDetector
from backend.confidence import ConfidenceEngine, assess_translation_confidence, estimate_stt_confidence, estimate_translation_confidence, detect_ambiguities, clarification_for
from backend.communication_brain import detect_domains
from backend.glossary import get_session_glossary, glossary_coverage_score
from backend.cip_client import call_cip_brain, cip_health_snapshot, cip_settings
from backend.cip_bridge import apply_cip_decision, choose_translation, get_cip_confidence, is_cip_clarification
from backend import assistant as naia_assistant
try:
    import pytesseract  # type: ignore
    from PIL import Image
    _HAS_PYTESSERACT = True
except (ImportError, ModuleNotFoundError):
    _HAS_PYTESSERACT = False


# --- Helpers, models, and shared state are in sibling modules. ---
# `backend.api` keeps the route table and lifespan; everything else
# is split out so this file stays readable.
from backend.api_models import (
    ImageTranslationResponse,
    LoginRequest,
    TextToSpeechRequest,
    TextTranslationRequest,
)
from backend.api_helpers import (
    HOP_BY_HOP_HEADERS,
    normalize_language as _normalize_language,
    read_limited_upload as _read_limited_upload,
    safe_upload_suffix as _safe_upload_suffix,
)
from backend.api_frontend import (
    embedded_frontend_response as _embedded_frontend_response,
    frontend_asset_path as _frontend_asset_path,
    frontend_dist_dir as _frontend_dist_dir,
    frontend_index_path as _frontend_index_path,
    frontend_launcher as _frontend_launcher,
    frontend_proxy_response as _frontend_proxy_response,
    local_frontend_url as _local_frontend_url,
    proxy_frontend as _proxy_frontend,
)
from backend.api_health import (
    RELEASE_ID,
    metrics,
    runtime_payload as _runtime_payload,
    runtime_state,
    stt_provider_health_snapshot as _stt_provider_health_snapshot,
)


def _translator_for_request(mode: str | None, provider: str | None):
    """Return a fresh translator instance based on per-request mode/provider hints.
    Falls back to the global pipeline translator when no override is requested."""
    if not mode and not provider:
        return None
    p = (provider or "").lower()
    m = (mode or "").lower()
    if p in ("marian", "local") or m == "accurate":
        return MarianTranslator()
    if p in ("lightweight",) or m == "fast":
        return LightweightTranslator()
    if p in ("hybrid",) or m == "balanced":
        return HybridTranslator()
    return None


VOICE_WARMUP_TEXTS = {
    "es": ["Hola, ¿cómo estás?"],
    "ht": ["Bonjou, kijan ou ye?"],
}
logger = logging.getLogger("anai_translator")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")


@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    # Abort immediately if production config is insecure
    config_errors = validate_production_config()
    if config_errors:
        for err in config_errors:
            logger.critical("[PRODUCTION CONFIG ERROR] %s", err)
        raise RuntimeError(
            "Server refused to start due to insecure production configuration.\n"
            + "\n".join(f"  - {e}" for e in config_errors)
        )

    # Warn if CIP brain is not fully configured
    from backend.cip_client import cip_settings as _cip_settings
    _cip = _cip_settings()
    if _cip["mode"] == "cip_first" and not _cip["external_configured"]:
        logger.warning(
            "CIP_MODE=cip_first but CIP_PROCESS_URL is not set — "
            "ambiguity resolution will use local engine only. "
            "Set CIP_PROCESS_URL to enable the full AI Comm System brain."
        )
    elif _cip["mode"] == "off":
        logger.info("CIP brain disabled (CIP_DEFAULT_MODE=off). Translations will not go through ambiguity resolution.")

    voice_warmup_task = None
    runtime_state["models"] = {
        "whisper_device": get_whisper_device(),
        "whisper_compute_type": get_whisper_compute_type(),
        "whisper_model_size": get_whisper_model_size(),
        "translation_backend": get_translation_backend(),
        "translation_runtime": pipeline.translator.__class__.__name__,
        "translation_device": get_translation_device(),
        "tts": "piper",
        "vad": "silero",
    }
    runtime_state["warming"] = get_preload_models()
    if get_preload_models():
        runtime_state["models"]["preloaded"] = await run_in_threadpool(pipeline.preload)
    runtime_state["warming"] = False
    runtime_state["ready"] = True
    runtime_state["voice_warmup"] = {"status": "queued", "started_at": time()}
    voice_warmup_task = asyncio.create_task(_warm_voice_cache("startup"))
    try:
        yield
    finally:
        if voice_warmup_task:
            voice_warmup_task.cancel()
        runtime_state["ready"] = False


app = FastAPI(title="Anai Translator", lifespan=lifespan)

# Initialize rate limiter
limiter = Limiter(key_func=get_remote_address)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_origin_regex=get_allowed_origin_regex(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# AILang integration (gracefully degrades if not installed)
try:
    from ailang_integration.runtime.api_routes import register_ailang_routes, check_ailang_available
    if check_ailang_available():
        register_ailang_routes(app)
        logger.info("AILang integration routes registered")
    else:
        logger.info("AILang not installed — integration disabled (graceful degradation)")
except ImportError:
    logger.info("AILang integration not available (optional dependency)")

pipeline = AnaiTranslatorPipeline()
vad = SileroVoiceActivityDetector()
conversation_brain = ConversationBrain()
memory = ConversationMemory()
speaker_memory = SpeakerMemory()
from backend.profile_memory import ProfileMemory
profiles = ProfileMemory()
confidence_engine = ConfidenceEngine()


@app.get("/")
def root(request: Request):
    embedded_frontend = _embedded_frontend_response()
    if embedded_frontend:
        return embedded_frontend
    return _proxy_frontend(request)


@app.get("/health")
async def health():
    return _runtime_payload()


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
    return _runtime_payload(include_details=True)


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
            upstream_request = UrlRequest(f"{frontend_url}/", headers={"User-Agent": "AnaiTranslatorDiagnostics/1.0"})
            with urlopen(upstream_request, timeout=1.5) as upstream:
                frontend["reachable"] = 200 <= upstream.status < 500
                frontend["status_code"] = upstream.status
        except (URLError, TimeoutError, ConnectionError) as exc:
            frontend["error"] = exc.__class__.__name__

    stt_provider = _stt_provider_health_snapshot(timeout_seconds=3)

    service_health_manager = get_service_health_manager()
    
    # Get AILang pipeline statistics
    ailang_stats = pipeline.get_ailang_statistics() if hasattr(pipeline, 'get_ailang_statistics') else {"enabled": False, "active_sessions": 0, "bridge_stats": None}
    
    # Get AILang configuration from config
    from backend.config import ailang_diagnostics
    ailang_config = ailang_diagnostics()
    
    # Get AILang health status
    ailang_health = None
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        ailang_health = pipeline.ailang_pipeline.get_health_status()
    
    # Translation health: show fallback chain and optional remote probe
    import os as _os
    _backend = get_translation_backend()
    _hybrid_marian_fallback = _os.getenv("HYBRID_ENABLE_MARIAN_FALLBACK", "1") != "0"
    _remote_enabled = get_hybrid_enable_remote()
    if _backend == "marian":
        _fallback_chain = ["marian"]
    elif _backend == "lightweight":
        _fallback_chain = ["lightweight"]
    elif _backend == "hybrid":
        _fallback_chain = ["lightweight"]
        if _hybrid_marian_fallback:
            _fallback_chain.append("marian")
        if _remote_enabled:
            _fallback_chain.append("remote_google")
    else:
        _fallback_chain = [_backend]
    _remote_ok: bool | None = None
    _remote_error: str | None = None
    if _remote_enabled:
        try:
            from translation.remote_translator import RemoteTranslator as _RT
            _r = _RT(timeout_seconds=2.0)
            _probe = _r.translate("hello", "en", "es")
            _remote_ok = bool(_probe and not _probe.startswith("[en->es]"))
        except Exception as _exc:
            _remote_ok = False
            _remote_error = type(_exc).__name__

    from backend.store import get_quota_store as _gqs, get_user_store as _gus
    _qs = _gqs()
    _us = _gus()
    _persistence = {
        "data_dir": _os.getenv("DATA_DIR", "") or None,
        "quota_store_available": _qs._available,
        "user_store_available": _us.is_available(),
        "db_has_users": _us.has_any_users() if _us.is_available() else False,
    }

    return {
        "status": "ok",
        "ready": runtime_state["ready"],
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
        "served_from": str(request.base_url).rstrip("/"),
        "frontend": frontend,
        "models": runtime_state["models"],
        "voice_warmup": runtime_state.get("voice_warmup"),
        "translation": {
            "runtime": runtime_state["models"].get("translation_runtime"),
            "backend": runtime_state["models"].get("translation_backend"),
            "device": runtime_state["models"].get("translation_device"),
            "fallback_chain": _fallback_chain,
            "marian_fallback_enabled": _hybrid_marian_fallback,
            "remote_fallback_enabled": _remote_enabled,
            "remote_translator_reachable": _remote_ok,
            "remote_translator_error": _remote_error,
            "tts_google_configured": bool(get_google_tts_api_key()),
        },
        "persistence": _persistence,
        "cip": cip_health_snapshot(),
        "stt_provider": stt_provider,
        "ailang": {**ailang_stats, "config": ailang_config, "health": ailang_health},
        "service_health": service_health_manager.get_all_health_summaries(),
        "streaming": {
            "websocket_path": "/ws/audio",
            "streaming_stt_path": "/ws/audio/streaming",
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
        "cip": cip_settings(),
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
    except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
        logger.exception("tts_sample_failed")
        raise HTTPException(status_code=503, detail=f"TTS sample unavailable: {exc}") from exc
    return FileResponse(str(output_path), media_type="audio/wav", filename="tts-sample.wav", headers={"Cache-Control": "no-store"})


def _tts_cache_path(cache_key: str) -> Path:
    return Path("models/tts/cache") / f"{cache_key}.wav"


def _is_tts_cache_key(cache_key: str) -> bool:
    return len(cache_key) == 64 and all(character in "0123456789abcdef" for character in cache_key)


def _normalize_audio_response_format(response_format: str | None) -> str:
    normalized = (response_format or "base64").strip().lower()
    if normalized not in {"base64", "url", "both"}:
        raise HTTPException(status_code=400, detail="audio response format must be base64, url, or both.")
    return normalized


def _cached_tts_payload(text: str, language: str, response_format: str, google_api_key: str | None = None) -> dict:
    cache_dir = Path("models/tts/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = hashlib.sha256(f"{language}\0{text}".encode("utf-8")).hexdigest()
    output_path = _tts_cache_path(cache_key)
    cache_hit = output_path.is_file() and output_path.stat().st_size >= 100
    audio_bytes = None
    audio_size = output_path.stat().st_size if cache_hit else 0

    if not cache_hit:
        temp_path = Path("models/tts") / f"{uuid4()}.wav"
        temp_path.parent.mkdir(parents=True, exist_ok=True)
        rendered_path = Path(pipeline.tts.synthesize(text, str(temp_path), language=language, google_api_key=google_api_key) or temp_path)
        audio_bytes = rendered_path.read_bytes()
        if len(audio_bytes) < 100:
            raise RuntimeError("TTS returned empty audio.")
        output_path.write_bytes(audio_bytes)
        audio_size = len(audio_bytes)
        if rendered_path != output_path:
            try:
                rendered_path.unlink(missing_ok=True)
            except (OSError, PermissionError):
                pass

    response_dict = {
        "text": text,
        "language": language,
        "mime_type": "audio/wav",
        "audio_output_path": str(output_path),
        "audio_url": f"/tts/audio/{cache_key}.wav",
        "audio_bytes": audio_size,
        "cache_hit": cache_hit,
    }
    if response_format in {"base64", "both"}:
        if audio_bytes is None:
            audio_bytes = output_path.read_bytes()
        response_dict["audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
    return response_dict


async def _warm_voice_cache(reason: str) -> None:
    started_at = time()
    warmed = []
    runtime_state["voice_warmup"] = {"status": "running", "started_at": started_at, "reason": reason}
    for language, texts in VOICE_WARMUP_TEXTS.items():
        for text in texts:
            try:
                payload = await run_in_threadpool(lambda text=text, language=language: _cached_tts_payload(text, language, "url"))
                warmed.append({
                    "language": language,
                    "text": text,
                    "cache_hit": payload["cache_hit"],
                    "audio_bytes": payload["audio_bytes"],
                })
                observability.record_event("voice_warmup", language=language, cache_hit=payload["cache_hit"], reason=reason)
            except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
                logger.warning("voice_warmup_failed language=%s reason=%s error=%s", language, reason, exc)
                observability.record_event("voice_warmup_failed", language=language, reason=reason, error=exc.__class__.__name__)
    runtime_state["voice_warmup"] = {
        "status": "complete",
        "reason": reason,
        "latency_seconds": round(time() - started_at, 3),
        "items": warmed,
    }


@app.get("/tts/audio/{cache_key}.wav")
async def cached_tts_audio(cache_key: str):
    if not _is_tts_cache_key(cache_key):
        raise HTTPException(status_code=404, detail="Voice audio not found.")
    output_path = _tts_cache_path(cache_key)
    if not output_path.is_file() or output_path.stat().st_size < 100:
        raise HTTPException(status_code=404, detail="Voice audio not found.")
    return FileResponse(
        str(output_path),
        media_type="audio/wav",
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


@app.post("/tts")
async def text_to_speech(request: TextToSpeechRequest, identity: str = Depends(authenticate_http)):
    started_at = time()
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    usage_limiter.track(identity, "tts_requests")
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text is required for voice output.")
    response_format = _normalize_audio_response_format(request.response_format)
    try:
        response_dict = await run_in_threadpool(lambda: _cached_tts_payload(text, request.language, response_format))
        observability.observe_latency("tts_request", time() - started_at)
        observability.record_event("tts_request", identity=identity, latency_seconds=time() - started_at, cache_hit=response_dict["cache_hit"], response_format=response_format)
        return response_dict
    except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
        usage_limiter.track(identity, "errors")
        observability.increment("tts_failures_total")
        observability.record_event("tts_failure", identity=identity)
        logger.exception("tts_request_failed identity=%s", identity)
        raise HTTPException(status_code=503, detail=f"Voice unavailable: {exc}") from exc


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
    request.source_language = _normalize_language(request.source_language, "en")
    request.target_language = _normalize_language(request.target_language, "es")
    logger.info(
        "text_translation identity=%s source=%s target=%s mode=%s provider=%s",
        identity, request.source_language, request.target_language,
        request.translation_mode or "default", request.translation_provider or "default",
    )
    audio_response_format = _normalize_audio_response_format(request.audio_response_format) if request.synthesize_audio else "base64"
    _google_key = (request.google_tts_api_key or "").strip() or None
    try:
        # Run pipeline up to translation (no synth), then refine, then optionally TTS
        # Register default speaker 'A' and lock/request language
        speaker_id = "A"
        if not speaker_memory.get_language(speaker_id):
            speaker_memory.register(speaker_id, language=request.source_language or detect_language_heuristic(request.text))
        # Use a per-request translator if mode/provider was specified by the client
        req_translator = _translator_for_request(request.translation_mode, request.translation_provider)
        
        # Get session ID from request or generate one
        session_id = request.session_id if hasattr(request, 'session_id') and request.session_id else identity
        
        # Get speaker from request or use default
        speaker = request.speaker if hasattr(request, 'speaker') and request.speaker else speaker_id
        
        # Get confidence from request
        confidence = request.confidence if hasattr(request, 'confidence') else 0.0
        
        # Configure AILang pipeline with request settings
        if request.dialect_preference:
            pipeline.set_dialect_preference(request.dialect_preference)
        if request.glossary:
            pipeline.set_glossary(request.glossary)
        
        if req_translator:
            interim = pipeline.translate_text_with(
                req_translator,
                text=request.text,
                source_language=request.source_language,
                target_language=request.target_language,
                tone=request.tone,
                synthesize_audio=False,
                speaker=speaker,
                confidence=confidence,
            )
        else:
            interim = pipeline.translate_text(
                text=request.text,
                source_language=request.source_language,
                target_language=request.target_language,
                tone=request.tone,
                synthesize_audio=False,
                speaker=speaker,
                confidence=confidence,
            )
        user_profile = profiles.get(identity)
        # Let the UT pipeline produce the translation first, then let CIP make
        # confidence, clarification, and conversation-routing decisions.
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(speaker_id)
        refined_text = refine_translation(request.text, interim.translated_text, memory_context, speaker_context)
        stt_conf = 0.9
        tr_conf = estimate_translation_confidence(request.text, refined_text)
        semantic_context = {
            "conversation_mood": "neutral",
            "topics": memory.recent_topics(),
        }
        cip = None
        cip = call_cip_brain(
            request.text,
            request.target_language,
            identity,
            fallback_translation=refined_text,
            source_language=request.source_language,
            stt_confidence=stt_conf,
            translation_confidence=tr_conf,
            context=memory_context,
            speaker_context=speaker_context,
            semantic_context=semantic_context,
        )
        cip_clarify = is_cip_clarification(cip)
        final_text = "" if cip_clarify else choose_translation(cip, refined_text)
        if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
            semantic_context["last_intent"] = cip["analysis"].get("intent") or "statement"
            semantic_context["conversation_mood"] = cip["analysis"].get("tone") or "neutral"
        # Confidence/clarify for text path
        tr_conf = estimate_translation_confidence(request.text, final_text)
        cip_conf = get_cip_confidence(cip)
        domains = detect_domains(request.text)
        session_key = request.session_id or identity
        glossary_cov = glossary_coverage_score(
            request.text,
            final_text,
            get_session_glossary(session_key),
            request.source_language,
            request.target_language,
        )
        assessment = assess_translation_confidence(
            request.text,
            final_text,
            stt_confidence=stt_conf,
            domains=domains,
            glossary_coverage=glossary_cov,
        )
        conf_score = cip_conf if cip_conf is not None else assessment["confidence"]
        audio_path = None
        audio_payload = None
        if request.synthesize_audio and final_text and not cip_clarify:
            audio_payload = _cached_tts_payload(final_text, request.target_language, audio_response_format, google_api_key=_google_key)
            audio_path = audio_payload["audio_output_path"]
        result = type(interim)(
            source_text=request.text,
            improved_text=interim.improved_text,
            translated_text=final_text,
            audio_output_path=audio_path,
        )
        observability.observe_latency("text_translation", time() - started_at)
        observability.record_event("text_translation", identity=identity, latency_seconds=time() - started_at)
        memory.add(speaker_id, request.text, result.translated_text, {"cip": cip})
        # Update profile preferences heuristically
        langs = set(user_profile.get("preferred_languages") or [])
        langs.update([request.source_language, request.target_language])
        user_profile["preferred_languages"] = [l for l in langs if l]
        user_profile["history"] = (user_profile.get("history") or [])[-48:] + [{"type": "text", "source": request.text, "translated": result.translated_text}]
        profiles.save(identity, user_profile)
        speaker_memory.add_message(speaker_id, request.text)
        response_dict = dict(result.__dict__)
        apply_cip_decision(response_dict, cip)
        
        # Include AILang metadata in response
        if interim.ailang_metadata:
            response_dict["ailang_metadata"] = interim.ailang_metadata
        
        if assessment["low_confidence"] and not response_dict.get("clarify"):
            response_dict["low_confidence"] = True
            response_dict["confidence"] = assessment["confidence"]
            response_dict["confidence_threshold"] = assessment["confidence_threshold"]
            response_dict["needs_confirmation"] = assessment["needs_confirmation"]
            response_dict["confidence_message"] = assessment["confidence_message"]
            response_dict["high_stakes_domains"] = assessment["high_stakes"]
        if conf_score < 0.4 and not response_dict.get("clarify"):
            response_dict["clarify"] = True
            response_dict["clarify_message"] = clarification_for(request.text, detect_ambiguities(request.text))
        if audio_payload and not response_dict.get("clarify"):
            response_dict.update(audio_payload)
            response_dict["translated_text"] = final_text
            observability.record_event("text_translation_tts", identity=identity, cache_hit=audio_payload["cache_hit"], response_format=audio_response_format)
        elif result.audio_output_path and not response_dict.get("clarify"):
            try:
                audio_bytes = Path(result.audio_output_path).read_bytes()
                if len(audio_bytes) >= 100:
                    response_dict["audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
                    response_dict["mime_type"] = "audio/wav"
            except (OSError, IOError) as exc:
                logger.warning("failed_to_embed_text_audio identity=%s error=%s", identity, exc)
        if request.session_id and not response_dict.get("clarify"):
            if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
                _a = cip["analysis"]
                semantic_context["cip"] = {
                    "intent": _a.get("intent"),
                    "tone": _a.get("tone"),
                    "confidence": _a.get("confidence"),
                }
            else:
                semantic_context["cip"] = None
            speaker_profile = session_registry.resolve_auto_speaker(
                request.session_id,
                identity,
                request.device_id,
                request.source_language,
                request.target_language,
                request.speaker_name,
            )
            shared_session = session_registry.record_turn(
                request.session_id,
                identity,
                speaker_profile["speaker"],
                result.source_text,
                result.translated_text,
                semantic_context,
                device_id=speaker_profile["device_id"],
                speaker_label=speaker_profile["speaker_label"],
            )
            session_payload = {
                k: v for k, v in shared_session.items() if k != "history"
            }
            session_payload["history"] = shared_session.get("history", [])[-10:]
            response_dict.update({
                "speaker": speaker_profile["speaker"],
                "speaker_label": speaker_profile["speaker_label"],
                "speaker_index": speaker_profile["speaker_index"],
                "device_id": speaker_profile["device_id"],
                "detection": speaker_profile["detection"],
                "semantic_context": dict(semantic_context),
                "session": session_payload,
            })
        return response_dict
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
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
    source_language = _normalize_language(source_language, "en")
    target_language = _normalize_language(target_language, "es")
    logger.info("audio_translation identity=%s source=%s target=%s", identity, source_language, target_language)
    max_bytes = get_max_audio_mb() * 1024 * 1024
    audio_bytes = await _read_limited_upload(audio, max_bytes)

    estimated_seconds = max(1, len(audio_bytes) / 16000)
    if estimated_seconds > get_max_audio_seconds():
        raise HTTPException(status_code=413, detail=f"Audio request exceeds {get_max_audio_seconds()} second limit.")

    allowed, remaining_seconds = usage_limiter.check_audio_seconds(identity, estimated_seconds)
    if not allowed:
        raise HTTPException(status_code=429, detail=f"Daily audio quota exceeded. Remaining seconds: {int(remaining_seconds)}")

    upload_dir = Path("models/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = _safe_upload_suffix(audio.filename, "audio.webm", {".webm", ".wav", ".m4a", ".mp3", ".ogg", ".aac"})
    audio_path = upload_dir / f"{uuid4()}{suffix}"
    audio_path.write_bytes(audio_bytes)

    try:
        source_text = await run_in_threadpool(pipeline.stt.transcribe, str(audio_path), source_language)
        # Default single-speaker flow: lock language for 'A'
        speaker_id = "A"
        if not speaker_memory.get_language(speaker_id):
            auto_lang = detect_language_heuristic(source_text)
            speaker_memory.register(speaker_id, language=source_language or auto_lang)
        # Translate (no synth), then refine, then synthesize if requested
        interim = await run_in_threadpool(
            pipeline.translate_text,
            source_text,
            source_language,
            target_language,
            None,
            False,
            f"models/tts/{uuid4()}.wav",
        )
        user_profile = profiles.get(identity)
        cip = None
        memory_context = memory.get_context()
        speaker_context = speaker_memory.get_context(speaker_id)
        refined_text = refine_translation(source_text, interim.translated_text, memory_context, speaker_context)
        stt_conf = estimate_stt_confidence(source_text)
        tr_conf = estimate_translation_confidence(source_text, refined_text)
        semantic_context = {
            "conversation_mood": "neutral",
            "topics": memory.recent_topics(),
        }
        cip = call_cip_brain(
            source_text,
            target_language,
            identity,
            fallback_translation=refined_text,
            source_language=source_language,
            stt_confidence=stt_conf,
            translation_confidence=tr_conf,
            context=memory_context,
            speaker_context=speaker_context,
            semantic_context=semantic_context,
        )
        cip_clarify = is_cip_clarification(cip)
        final_text = "" if cip_clarify else choose_translation(cip, refined_text)
        if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
            semantic_context["last_intent"] = cip["analysis"].get("intent") or "statement"
            semantic_context["conversation_mood"] = cip["analysis"].get("tone") or "neutral"
        # Confidence/clarify for audio path
        tr_conf = estimate_translation_confidence(source_text, final_text)
        cip_conf = get_cip_confidence(cip)
        conf_score = cip_conf if cip_conf is not None else confidence_engine.evaluate(stt_conf, tr_conf)
        audio_path = None
        if synthesize_audio and final_text and conf_score >= 0.4 and not cip_clarify:
            audio_path = await run_in_threadpool(pipeline.tts.synthesize, final_text, f"models/tts/{uuid4()}.wav", target_language)
        result = type(interim)(
            source_text=source_text,
            improved_text=interim.improved_text,
            translated_text=final_text,
            audio_output_path=audio_path,
        )
        observability.observe_latency("audio_translation", time() - started_at)
        observability.record_event("audio_translation", identity=identity, latency_seconds=time() - started_at)
        usage_limiter.track_audio(identity, estimated_seconds, "audio_translations")
        response_dict = dict(result.__dict__)
        apply_cip_decision(response_dict, cip)
        if conf_score < 0.4 and not response_dict.get("clarify"):
            response_dict["clarify"] = True
            response_dict["clarify_message"] = clarification_for(source_text, detect_ambiguities(source_text))
        try:
            memory.add(speaker_id, source_text, result.translated_text, {"cip": cip})
            speaker_memory.add_message(speaker_id, source_text)
            # Update profile: languages, history
            langs = set(user_profile.get("preferred_languages") or [])
            langs.update([source_language, target_language])
            user_profile["preferred_languages"] = [l for l in langs if l]
            user_profile["history"] = (user_profile.get("history") or [])[-48:] + [{"type": "audio", "source": source_text, "translated": result.translated_text}]
            profiles.save(identity, user_profile)
        except (OSError, PermissionError, KeyError) as exc:
            logger.warning("profile_save_failed identity=%s error=%s", identity, exc)
        # Include audio as base64 so mobile clients can play without fetching a separate file
        if result.audio_output_path and not response_dict.get("clarify"):
            try:
                audio_bytes = Path(result.audio_output_path).read_bytes()
                if len(audio_bytes) >= 100:
                    response_dict["audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
                    response_dict["mime_type"] = "audio/wav"
            except (OSError, IOError) as exc:
                logger.warning("failed_to_embed_audio identity=%s error=%s", identity, exc)
        return response_dict
    except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError):
        usage_limiter.track(identity, "errors")
        observability.increment("translation_failures_total")
        observability.record_event("translation_failure", identity=identity, mode="audio")
        raise
    finally:
        with suppress(Exception):
            audio_path.unlink(missing_ok=True)


@app.post("/translate/image")
async def translate_image(
    image: UploadFile = File(...),
    source_language: str = Form("auto"),
    target_language: str = Form("es"),
    synthesize_audio: bool = Form(False),
    identity: str = Depends(authenticate_http),
):
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    source_language = _normalize_language(source_language, "auto", allow_auto=True)
    target_language = _normalize_language(target_language, "es")
    logger.info("image_translation identity=%s target=%s", identity, target_language)
    if not _HAS_PYTESSERACT:
        raise HTTPException(status_code=503, detail="OCR unavailable on server. Install Tesseract to enable.")
    # Save upload to a temp path
    upload_dir = Path("models/uploads")
    upload_dir.mkdir(parents=True, exist_ok=True)
    suffix = _safe_upload_suffix(image.filename, "image.png", {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"})
    image_path = upload_dir / f"{uuid4()}{suffix}"
    image_bytes = await _read_limited_upload(image, get_max_audio_mb() * 1024 * 1024)
    image_path.write_bytes(image_bytes)
    try:
        # OCR
        ocr_text = pytesseract.image_to_string(Image.open(image_path)) or ""
        if source_language == "auto":
            source_language = detect_language_heuristic(ocr_text)
        # Translate (no synth), then optional TTS synth
        interim = pipeline.translate_text(
            text=ocr_text,
            source_language=source_language,
            target_language=target_language,
            tone=None,
            synthesize_audio=False,
        )
        user_profile = profiles.get(identity)
        final_text = refine_translation(ocr_text, interim.translated_text, memory.get_context(), speaker_memory.get_context("CAM"))
        audio_path = None
        audio_b64 = None
        if synthesize_audio and final_text:
            audio_path = pipeline.tts.synthesize(final_text, f"models/tts/{uuid4()}.wav", language=target_language)
            try:
                audio_bytes = Path(audio_path).read_bytes()
                if len(audio_bytes) >= 100:
                    audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
            except (OSError, IOError) as exc:
                logger.warning("tts_audio_read_failed identity=%s error=%s", identity, exc)
        # Store in memory under virtual speaker CAM
        memory.add("CAM", ocr_text, final_text)
        speaker_memory.register("CAM", language=source_language)
        speaker_memory.add_message("CAM", ocr_text)
        # Update profile history
        user_profile["history"] = (user_profile.get("history") or [])[-48:] + [{"type": "image", "source": ocr_text, "translated": final_text}]
        profiles.save(identity, user_profile)
        return {
            "ocr_text": ocr_text.strip(),
            "translated_text": final_text,
            "mime_type": "audio/wav" if audio_b64 else None,
            "audio_base64": audio_b64,
        }
    finally:
        with suppress(Exception):
            image_path.unlink(missing_ok=True)


@app.post("/vad")
async def detect_voice_activity(audio: UploadFile = File(...), identity: str = Depends(authenticate_http)):
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    audio_bytes = await _read_limited_upload(audio, get_max_audio_mb() * 1024 * 1024)
    suffix = _safe_upload_suffix(audio.filename, "audio.webm", {".webm", ".wav", ".m4a", ".mp3", ".ogg", ".aac"})
    return await run_in_threadpool(vad.detect_bytes, audio_bytes, suffix)


# AILang Configuration Endpoints

@app.post("/ailang/glossary")
@limiter.limit("10/minute")
def set_ailang_glossary(
    request: Request,
    glossary: list,
    session_id: str = "default",
    identity: str = Depends(authenticate_http),
):
    """Set custom glossary for AILang terminology injection."""
    metrics["http_requests"] += 1
    pipeline.set_glossary(glossary)
    logger.info("ailang_glossary_set identity=%s session_id=%s terms=%d", identity, session_id, len(glossary))
    return {"status": "ok", "session_id": session_id, "glossary_terms": len(glossary)}


@app.post("/ailang/dialect")
@limiter.limit("10/minute")
def set_ailang_dialect(
    request: Request,
    dialect: str,
    session_id: str = "default",
    identity: str = Depends(authenticate_http),
):
    """Set dialect preference for AILang regional adaptation."""
    metrics["http_requests"] += 1
    pipeline.set_dialect_preference(dialect)
    logger.info("ailang_dialect_set identity=%s session_id=%s dialect=%s", identity, session_id, dialect)
    return {"status": "ok", "session_id": session_id, "dialect": dialect}


@app.post("/ailang/speaker")
@limiter.limit("10/minute")
def set_ailang_speaker(
    request: Request,
    speaker: str,
    session_id: str = "default",
    identity: str = Depends(authenticate_http),
):
    """Set current speaker for AILang context tracking."""
    metrics["http_requests"] += 1
    pipeline.set_speaker(speaker)
    logger.info("ailang_speaker_set identity=%s session_id=%s speaker=%s", identity, session_id, speaker)
    return {"status": "ok", "session_id": session_id, "speaker": speaker}


@app.delete("/ailang/context")
def clear_ailang_context(
    session_id: str = "default",
    identity: str = Depends(authenticate_http),
):
    """Clear AILang context for a session."""
    metrics["http_requests"] += 1
    pipeline.clear_session_context()
    logger.info("ailang_context_cleared identity=%s session_id=%s", identity, session_id)
    return {"status": "ok", "session_id": session_id}


@app.get("/ailang/stats")
def get_ailang_stats(identity: str = Depends(authenticate_http)):
    """Get AILang pipeline statistics."""
    metrics["http_requests"] += 1
    stats = pipeline.get_ailang_statistics()
    return stats


@app.get("/ailang/health")
def get_ailang_health(identity: str = Depends(authenticate_http)):
    """Get AILang bridge health status."""
    metrics["http_requests"] += 1
    try:
        from ailang_integration.runtime.bridge import get_bridge
        bridge = get_bridge()
        bridge_stats = bridge.get_stats() if bridge else None
        return {
            "status": "healthy" if bridge else "unavailable",
            "bridge_loaded": bridge is not None,
            "bridge_stats": bridge_stats,
            "pipeline_enabled": pipeline.ailang_pipeline._enabled if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline else False,
        }
    except Exception as e:
        return {
            "status": "error",
            "bridge_loaded": False,
            "error": str(e),
        }


@app.get("/ailang/health-status")
def get_ailang_health_status(identity: str = Depends(authenticate_http)):
    """Get AILang pipeline health status with alerts."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        return pipeline.ailang_pipeline.get_health_status()
    return {
        "overall_status": "unavailable",
        "agent_health": {},
        "alerts": [],
        "total_alerts": 0,
        "critical_alerts": 0,
        "warning_alerts": 0,
    }


@app.post("/ailang/agent/{agent_name}/enable")
@limiter.limit("20/minute")
def enable_ailang_agent(request: Request, agent_name: str, identity: str = Depends(authenticate_http)):
    """Enable a specific AILang agent."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        pipeline.ailang_pipeline.set_agent_enabled(agent_name, True)
        return {"status": "ok", "agent": agent_name, "enabled": True}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/agent/{agent_name}/disable")
@limiter.limit("20/minute")
def disable_ailang_agent(request: Request, agent_name: str, identity: str = Depends(authenticate_http)):
    """Disable a specific AILang agent."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        pipeline.ailang_pipeline.set_agent_enabled(agent_name, False)
        return {"status": "ok", "agent": agent_name, "enabled": False}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/agent/{agent_name}/config")
@limiter.limit("10/minute")
def set_ailang_agent_config(request: Request, agent_name: str, config: dict, identity: str = Depends(authenticate_http)):
    """Set custom configuration for a specific AILang agent."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        success = pipeline.ailang_pipeline.set_agent_config(agent_name, config)
        if success:
            return {"status": "ok", "agent": agent_name, "config": config}
        return {"status": "error", "message": f"Agent {agent_name} not found"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.get("/ailang/agent/{agent_name}/config")
def get_ailang_agent_config(agent_name: str, identity: str = Depends(authenticate_http)):
    """Get custom configuration for a specific AILang agent."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        config = pipeline.ailang_pipeline.get_agent_config(agent_name)
        return {"status": "ok", "agent": agent_name, "config": config}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.delete("/ailang/agent/{agent_name}/config")
@limiter.limit("10/minute")
def delete_ailang_agent_config(request: Request, agent_name: str, identity: str = Depends(authenticate_http)):
    """Delete custom configuration for a specific AILang agent."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        success = pipeline.ailang_pipeline.delete_agent_config(agent_name)
        if success:
            return {"status": "ok", "agent": agent_name, "message": "Config deleted"}
        return {"status": "error", "message": f"Agent {agent_name} not found or no config"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.get("/ailang/agents")
def get_ailang_agents(identity: str = Depends(authenticate_http)):
    """Get all AILang agents and their enable/disable status."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        return pipeline.ailang_pipeline.get_enabled_agents()
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/cache/clear")
@limiter.limit("10/minute")
def clear_ailang_cache(request: Request, identity: str = Depends(authenticate_http)):
    """Clear the AILang response cache."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        pipeline.ailang_pipeline.clear_cache()
        return {"status": "ok", "message": "Cache cleared"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/circuit-breaker/{agent_name}/reset")
@limiter.limit("20/minute")
def reset_ailang_circuit_breaker(request: Request, agent_name: str, identity: str = Depends(authenticate_http)):
    """Manually reset a specific agent's circuit breaker."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        success = pipeline.ailang_pipeline.reset_circuit_breaker(agent_name)
        if success:
            return {"status": "ok", "agent": agent_name, "message": "Circuit breaker reset"}
        return {"status": "error", "message": f"Agent {agent_name} not found"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/circuit-breaker/reset-all")
@limiter.limit("5/minute")
def reset_all_ailang_circuit_breakers(request: Request, identity: str = Depends(authenticate_http)):
    """Reset all circuit breakers."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        count = pipeline.ailang_pipeline.reset_all_circuit_breakers()
        return {"status": "ok", "count": count, "message": f"Reset {count} circuit breakers"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.post("/ailang/sessions/cleanup")
@limiter.limit("5/minute")
def cleanup_ailang_sessions(request: Request, max_age_seconds: float = 3600.0, identity: str = Depends(authenticate_http)):
    """Clean up inactive AILang sessions older than max_age_seconds."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        count = pipeline.ailang_pipeline.cleanup_inactive_sessions(max_age_seconds)
        return {"status": "ok", "cleaned": count, "message": f"Cleaned {count} inactive sessions"}
    return {"status": "error", "message": "AILang pipeline not available"}


@app.get("/ailang/metrics")
def get_ailang_metrics(identity: str = Depends(authenticate_http)):
    """Get AILang metrics in Prometheus-compatible format."""
    metrics["http_requests"] += 1
    if hasattr(pipeline, 'ailang_pipeline') and pipeline.ailang_pipeline:
        stats = pipeline.ailang_pipeline.get_statistics()
        lines = []
        
        # Circuit breaker metrics
        for agent_name, cb_stats in stats.get("circuit_breakers", {}).items():
            lines.append(f'ailang_circuit_state{{agent="{agent_name}"}} {1 if cb_stats["state"] == "closed" else 0}')
            lines.append(f'ailang_circuit_total_calls{{agent="{agent_name}"}} {cb_stats["total_calls"]}')
            lines.append(f'ailang_circuit_successful_calls{{agent="{agent_name}"}} {cb_stats["successful_calls"]}')
            lines.append(f'ailang_circuit_failed_calls{{agent="{agent_name}"}} {cb_stats["failed_calls"]}')
            lines.append(f'ailang_circuit_success_rate{{agent="{agent_name}"}} {cb_stats["success_rate"]:.4f}')
            lines.append(f'ailang_circuit_avg_latency_ms{{agent="{agent_name}"}} {cb_stats["avg_latency_ms"]:.2f}')
            lines.append(f'ailang_circuit_p50_latency_ms{{agent="{agent_name}"}} {cb_stats.get("p50_latency_ms", 0):.2f}')
            lines.append(f'ailang_circuit_p95_latency_ms{{agent="{agent_name}"}} {cb_stats.get("p95_latency_ms", 0):.2f}')
            lines.append(f'ailang_circuit_p99_latency_ms{{agent="{agent_name}"}} {cb_stats.get("p99_latency_ms", 0):.2f}')
        
        # Cache metrics
        cache_info = stats.get("cache", {})
        lines.append(f'ailang_cache_size {cache_info.get("size", 0)}')
        lines.append(f'ailang_cache_max_size {cache_info.get("max_size", 1000)}')
        lines.append(f'ailang_cache_hit_rate {cache_info.get("hit_rate", 0):.4f}')
        lines.append(f'ailang_cache_hits {cache_info.get("hits", 0)}')
        lines.append(f'ailang_cache_misses {cache_info.get("misses", 0)}')
        
        # Session metrics
        lines.append(f'ailang_active_sessions {stats.get("active_sessions", 0)}')
        lines.append(f'ailang_enabled {1 if stats.get("enabled") else 0}')
        
        return Response(content="\n".join(lines), media_type="text/plain")
    return Response(content="", media_type="text/plain")


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
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
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
        if get_stt_provider() == "streaming":
            from backend.streaming import websocket_streaming_stt_translation

            await websocket_streaming_stt_translation(
                websocket, pipeline, conversation_brain, memory, speaker_memory, identity
            )
        else:
            await websocket_audio_translation(websocket, pipeline, vad, conversation_brain, memory, speaker_memory, identity)
    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        observability.record_event("websocket_disconnect", identity=identity, mode="audio")
        logger.info("audio_websocket_disconnected identity=%s", identity)
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        metrics["websocket_errors"] += 1
        observability.increment("websocket_errors_total")
        observability.record_event("websocket_error", identity=identity, mode="audio")
        logger.exception("audio_websocket_error identity=%s", identity)
        await websocket.close(code=1011, reason="Internal WebSocket error")


@app.websocket("/ws/audio/streaming")
async def websocket_audio_streaming(websocket: WebSocket):
    """Streaming STT audio WebSocket — proxies audio to the STT provider service."""
    from backend.streaming import websocket_streaming_stt_translation
    from backend.config import get_stt_provider

    logger.info("streaming_stt_websocket_auth_start release=%s", WEBSOCKET_AUTH_RELEASE)
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        logger.warning("streaming_stt_websocket_auth_rejected identity=%s", identity)
        return

    if get_stt_provider() != "streaming":
        await websocket.close(code=1008, reason="STT provider is not in streaming mode")
        return

    metrics["websocket_connections"] += 1
    logger.info("streaming_stt_websocket_connected identity=%s", identity)
    try:
        await websocket_streaming_stt_translation(
            websocket, pipeline, conversation_brain, memory, speaker_memory, identity
        )
    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        observability.record_event("websocket_disconnect", identity=identity, mode="streaming_stt")
        logger.info("streaming_stt_websocket_disconnected identity=%s", identity)
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        metrics["websocket_errors"] += 1
        observability.increment("websocket_errors_total")
        observability.record_event("websocket_error", identity=identity, mode="streaming_stt")
        logger.exception("streaming_stt_websocket_error identity=%s", identity)
        await websocket.close(code=1011, reason="Internal WebSocket error")


@app.websocket("/ws/ping")
async def websocket_ping(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"type": "ready", "release": RELEASE_ID, "websocket_auth_release": WEBSOCKET_AUTH_RELEASE})
    await websocket.close()


# ---------------------------------------------------------------------------
# NAIA assistant — conversational helper alongside translations
# ---------------------------------------------------------------------------


class AssistantChatRequest(BaseModel):
    message: str
    session_id: str | None = None
    translation_context: dict | None = None
    metadata: dict | None = None

    @field_validator("message")
    @classmethod
    def message_must_be_bounded(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("message is required")
        if len(v) > 4000:
            raise ValueError("message too long (max 4000 characters)")
        return v


@app.get("/api/assistant/health")
async def assistant_health():
    """Report whether the bundled naia kernel is available."""
    return {
        "available": naia_assistant.is_available(),
        "error": naia_assistant.import_error(),
        "kernel_timeout_seconds": naia_assistant.KERNEL_TIMEOUT_SECONDS,
    }


@app.post("/api/assistant/chat")
async def assistant_chat(payload: AssistantChatRequest, identity: str = Depends(authenticate_http)):
    """Send a chat message to the naia assistant.

    Accepts an optional ``translation_context`` so the assistant can answer
    follow-up questions about the user's most recent translation
    (e.g. "rephrase that more formally" or "what does this idiom mean?").
    """
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    if not payload.message or not payload.message.strip():
        raise HTTPException(status_code=400, detail="message is required")
    if not naia_assistant.is_available():
        raise HTTPException(
            status_code=503,
            detail=f"Assistant unavailable: {naia_assistant.import_error()}",
        )
    meta = dict(payload.metadata or {})
    if payload.session_id:
        meta["client_session_id"] = payload.session_id
    meta["identity"] = identity
    try:
        result = await naia_assistant.chat(
            payload.message,
            source="http",
            translation_context=payload.translation_context,
            metadata=meta,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        logger.exception("assistant_chat_failed identity=%s", identity)
        raise HTTPException(status_code=500, detail="Assistant error")
    return result


@app.websocket("/ws/assistant")
async def websocket_assistant(websocket: WebSocket):
    """Streaming chat with the naia assistant over a WebSocket."""
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    await websocket.accept()
    metrics["websocket_connections"] += 1
    logger.info("assistant_websocket_connected identity=%s", identity)
    if not naia_assistant.is_available():
        await websocket.send_json({
            "event": "error",
            "detail": f"Assistant unavailable: {naia_assistant.import_error()}",
        })
        await websocket.close(code=1011, reason="Assistant unavailable")
        return
    try:
        while True:
            raw = await websocket.receive_json()
            try:
                req = AssistantChatRequest.model_validate(raw)
            except (ValueError, TypeError, KeyError) as exc:
                await websocket.send_json({"event": "error", "detail": f"Bad payload: {exc}"})
                continue
            if not req.message or not req.message.strip():
                await websocket.send_json({"event": "error", "detail": "message is required"})
                continue
            await websocket.send_json({"event": "started"})
            meta = dict(req.metadata or {})
            if req.session_id:
                meta["client_session_id"] = req.session_id
            meta["identity"] = identity
            try:
                result = await naia_assistant.chat(
                    req.message,
                    source="websocket",
                    translation_context=req.translation_context,
                    metadata=meta,
                )
                await websocket.send_json({"event": "completed", "response": result})
            except (RuntimeError, ValueError, ConnectionError, TimeoutError) as exc:
                logger.exception("assistant_ws_error identity=%s", identity)
                await websocket.send_json({"event": "error", "detail": "Assistant error"})
    except WebSocketDisconnect:
        observability.increment("websocket_disconnects_total")
        observability.record_event("websocket_disconnect", identity=identity, mode="assistant")
        logger.info("assistant_websocket_disconnected identity=%s", identity)
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        metrics["websocket_errors"] += 1
        logger.exception("assistant_websocket_error identity=%s", identity)
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal WebSocket error")


# ---------------------------------------------------------------------------
# Admin: User management (requires DATA_DIR to be set)
# All admin routes require a valid JWT + the identity must be listed in
# ADMIN_IDENTITIES env var (comma-separated list of admin usernames).
# ---------------------------------------------------------------------------

def _require_admin(identity: str = Depends(authenticate_http)) -> str:
    admin_ids = {
        s.strip()
        for s in os.getenv("ADMIN_IDENTITIES", "").split(",")
        if s.strip()
    }
    if not admin_ids:
        raise HTTPException(status_code=403, detail="No ADMIN_IDENTITIES configured.")
    if identity not in admin_ids:
        raise HTTPException(status_code=403, detail="Admin access required.")
    return identity


@app.get("/admin/users")
def admin_list_users(admin: str = Depends(_require_admin)):
    from backend.store import get_user_store
    us = get_user_store()
    if not us.is_available():
        raise HTTPException(status_code=503, detail="DATA_DIR not set — persistent user store unavailable.")
    return {"users": us.list_users()}


@app.post("/admin/users")
def admin_add_user(
    body: dict,
    admin: str = Depends(_require_admin),
):
    from backend.store import get_user_store
    us = get_user_store()
    if not us.is_available():
        raise HTTPException(status_code=503, detail="DATA_DIR not set — persistent user store unavailable.")
    username = str(body.get("username", "")).strip()
    password = str(body.get("password", "")).strip()
    tier = str(body.get("tier", "free")).strip()
    if not username or not password:
        raise HTTPException(status_code=422, detail="username and password are required.")
    if tier not in {"free", "pro"}:
        raise HTTPException(status_code=422, detail="tier must be 'free' or 'pro'.")
    ok = us.add_user(username, password, tier)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to add user.")
    return {"ok": True, "username": username, "tier": tier}


@app.delete("/admin/users/{username}")
def admin_delete_user(username: str, admin: str = Depends(_require_admin)):
    from backend.store import get_user_store
    us = get_user_store()
    if not us.is_available():
        raise HTTPException(status_code=503, detail="DATA_DIR not set — persistent user store unavailable.")
    ok = us.delete_user(username)
    return {"ok": ok, "username": username}


@app.patch("/admin/users/{username}/tier")
def admin_update_tier(username: str, body: dict, admin: str = Depends(_require_admin)):
    from backend.store import get_user_store
    us = get_user_store()
    if not us.is_available():
        raise HTTPException(status_code=503, detail="DATA_DIR not set — persistent user store unavailable.")
    tier = str(body.get("tier", "")).strip()
    if tier not in {"free", "pro"}:
        raise HTTPException(status_code=422, detail="tier must be 'free' or 'pro'.")
    ok = us.update_tier(username, tier)
    return {"ok": ok, "username": username, "tier": tier}


@app.get("/{full_path:path}")
def frontend_dev_asset(full_path: str, request: Request):
    embedded_frontend = _embedded_frontend_response(full_path)
    if embedded_frontend:
        return embedded_frontend
    return _proxy_frontend(request, full_path)
