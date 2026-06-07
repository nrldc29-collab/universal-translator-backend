import base64
import asyncio
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
from backend.speakers import SpeakerMemory, detect_language_heuristic, resolve_barrier_route
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
    get_vad_force_final_seconds,
    get_vad_silent_checks,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_model_size,
    get_google_tts_api_key,
    get_natural_tts_mode,
    get_partial_tts_mode,
    validate_production_config,
)
from backend.service_health import get_service_health_manager
from translation import HybridTranslator, LightweightTranslator, MarianTranslator
from backend.pipeline import AnaiTranslatorPipeline
from tts import PiperTextToSpeech
from backend.observability import observability
from backend.security import WEBSOCKET_AUTH_RELEASE, authenticate_http, authenticate_user, authenticate_websocket, usage_limiter
from backend.sessions import session_registry
from backend.streaming import websocket_audio_translation, websocket_text_translation
from backend.streaming_helpers import audio_suffix_for_bytes, is_internal_translation_artifact
from speech import SileroVoiceActivityDetector
from backend.confidence import ConfidenceEngine, estimate_stt_confidence, estimate_translation_confidence, detect_ambiguities, clarification_for
from backend.cip_client import call_cip_brain, cip_health_snapshot, cip_settings
from backend.cip_bridge import apply_cip_decision, choose_translation, get_cip_confidence, should_block_translation_for_cip
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
from backend.tts_cache import (
    cached_tts_payload as _cached_tts_payload_impl,
    is_tts_cache_key as _is_shared_tts_cache_key,
    tts_cache_path as _shared_tts_cache_path,
)


def _translation_wants_quality(mode: str | None, quality: str | None) -> bool:
    m = (mode or "").lower()
    q = (quality or "").lower()
    return m in {"accurate", "quality", "high"} or q in {"quality", "high", "accurate"}


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
    if p in ("remote",):
        return MarianTranslator()
    return None


VOICE_WARMUP_TEXTS = {
    "en": ["Hello", "Hello."],
    "es": ["Hola", "Hola.", "Hola, como estas?"],
    "ht": ["Bonjou."],
    "fr": ["Bonjour."],
    "de": ["Hallo."],
    "it": ["Ciao."],
    "pt": ["Ola.", "Ol\u00e1."],
    "nl": ["Hallo."],
    "ru": ["\u041f\u0440\u0438\u0432\u0435\u0442.", "\u0411\u043e\u043b\u044c\u0448\u043e\u0435 \u0441\u043f\u0430\u0441\u0438\u0431\u043e."],
    "zh": ["\u4f60\u597d\u3002"],
    "ja": ["\u3053\u3093\u306b\u3061\u306f\u3002"],
    "ko": ["\uc548\ub155\ud558\uc138\uc694."],
    "ar": ["\u0645\u0631\u062d\u0628\u0627."],
    "hi": ["\u0928\u092e\u0938\u094d\u0924\u0947."],
}
_CONFIGURED_LANGUAGE_CODES = tuple(LANGUAGES.keys())

TRANSLATION_WARMUP_TEXTS = [
    *((lang, "en", "hello") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *((lang, "en", "thank you") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "I need help") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "es", "Mwen bezwen èd"),
    ("es", "ht", "Necesito ayuda"),
    ("fr", "de", "J'ai besoin d'aide"),
    ("de", "fr", "Ich brauche Hilfe"),
    ("ja", "ko", "助けが必要です"),
    ("ar", "hi", "أحتاج إلى مساعدة"),
    *(( "en", lang, "Turn left") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "I need a taxi") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("es", "zh", "Gire a la izquierda"),
    ("fr", "ht", "Tournez à gauche"),
    ("de", "ar", "Ich brauche ein Taxi"),
    ("ht", "es", "Mwen bezwen yon taksi"),
]

REMOTE_TRANSLATION_WARMUP_TEXTS = [
    *(( "en", lang, "I need help with directions") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Where is the bathroom?") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Help") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "I need a doctor") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Call the police") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "es", "Mwen pa konprann"),
    ("ht", "fr", "Mwen bezwen èd"),
    ("es", "ht", "Necesito ayuda"),
    ("es", "fr", "No entiendo"),
    ("fr", "de", "J'ai besoin d'aide"),
    ("de", "ht", "Ich brauche Hilfe"),
    ("ru", "de", "Мне нужна помощь"),
    ("zh", "ja", "我需要帮助"),
    ("ko", "ar", "도움이 필요합니다"),
    ("ja", "en", "助けが必要です"),
    ("ar", "ht", "أحتاج إلى مساعدة"),
    *(( "en", lang, "Turn left") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Where is the bus stop?") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("es", "ht", "Necesito un taxi"),
    ("ht", "fr", "Vire a goch"),
    ("zh", "es", "向左转"),
    ("ja", "ko", "タクシーが必要です"),
    ("ko", "en", "택시가 필요해요"),
    ("ar", "de", "أحتاج إلى سيارة أجرة"),
    *(( "en", lang, "I am hungry") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "I feel sick") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "es", "Mwen grangou"),
    ("es", "ht", "Tengo hambre"),
    ("fr", "zh", "J'ai faim"),
    ("ja", "ko", "気分が悪いです"),
    *(( "en", lang, "I have a reservation") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "How much is this?") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "fr", "Mwen gen yon rezèvasyon"),
    ("es", "de", "¿Cuánto cuesta esto?"),
    ("zh", "ht", "今天"),
    *(( "en", lang, "I lost my passport") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Five") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "es", "Mwen pèdi paspò mwen"),
    ("es", "fr", "Cinco"),
    ("de", "ht", "Drei"),
    *(( "en", lang, "I cannot breathe") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Where is the embassy?") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "fr", "Mwen pa ka respire"),
    ("es", "zh", "Buenas noches"),
    *(( "en", lang, "I have no money") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    *(( "en", lang, "Where is the ATM?") for lang in _CONFIGURED_LANGUAGE_CODES if lang != "en"),
    ("ht", "es", "Mwen pa gen lajan"),
    ("fr", "de", "Ma femme"),
]
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

    from tts.tts_readiness import log_neural_tts_startup_warning, neural_tts_status

    log_neural_tts_startup_warning()
    runtime_state["tts_neural"] = neural_tts_status()

    voice_warmup_task = None
    runtime_state["models"] = {
        "whisper_device": get_whisper_device(),
        "whisper_compute_type": get_whisper_compute_type(),
        "whisper_model_size": get_whisper_model_size(),
        "translation_backend": get_translation_backend(),
        "translation_runtime": pipeline.translator.__class__.__name__,
        "translation_device": get_translation_device(),
        "tts": "edge_neural" if runtime_state.get("tts_neural", {}).get("neural_ready") else "piper_fallback",
        "vad": "silero",
    }
    runtime_state["warming"] = get_preload_models()
    if get_preload_models():
        runtime_state["models"]["preloaded"] = await run_in_threadpool(pipeline.preload)
    runtime_state["warming"] = False
    runtime_state["ready"] = True

    async def _run_ollama_warmup() -> None:
        runtime_state["ollama_warmup"] = await _warm_ollama()

    runtime_state["ollama_warmup"] = {"status": "queued", "started_at": time()}
    ollama_warmup_task = asyncio.create_task(_run_ollama_warmup())

    translation_warmup_task = None
    remote_translation_warmup_task = None
    skip_translation_warmup = os.getenv("SKIP_TRANSLATION_WARMUP", "true").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if skip_translation_warmup:
        runtime_state["translation_warmup"] = {
            "status": "skipped",
            "reason": "SKIP_TRANSLATION_WARMUP",
            "message": "Translation warmup skipped to keep neural voice stable on limited RAM",
        }
    else:
        runtime_state["translation_warmup"] = {"status": "queued", "started_at": time()}
        translation_warmup_task = asyncio.create_task(_warm_translation_cache("startup"))

    remote_warmup_enabled = os.getenv("REMOTE_TRANSLATION_WARMUP", "1").strip().lower() in {
        "1", "true", "yes", "on",
    }
    if remote_warmup_enabled:
        runtime_state["remote_translation_warmup"] = {"status": "queued", "started_at": time()}
        remote_translation_warmup_task = asyncio.create_task(_warm_remote_translation_cache("startup"))
    else:
        runtime_state["remote_translation_warmup"] = {
            "status": "skipped",
            "reason": "REMOTE_TRANSLATION_WARMUP",
            "items": [],
        }

    runtime_state["voice_warmup"] = {"status": "queued", "started_at": time()}
    voice_warmup_task = asyncio.create_task(_warm_voice_cache("startup"))
    try:
        yield
    finally:
        if voice_warmup_task:
            voice_warmup_task.cancel()
        if remote_translation_warmup_task:
            remote_translation_warmup_task.cancel()
        if translation_warmup_task:
            translation_warmup_task.cancel()
        if ollama_warmup_task:
            ollama_warmup_task.cancel()
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

# Global latency engine — shared across streaming and HTTP paths
from backend.latency import LatencyEngine as _LatencyEngineClass
latency_engine = _LatencyEngineClass()
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


@app.get("/health/ollama")
def health_ollama():
    """Lightweight Ollama health check — startup warm-up status + live ping."""
    warmup = runtime_state.get("ollama_warmup") or {}
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_enabled = os.getenv("OLLAMA_ENABLED", "").lower() in ("true", "1", "yes")

    result = {
        "enabled": ollama_enabled,
        "url": ollama_url,
        "model": os.getenv("OLLAMA_MODEL", "mistral"),
        "warmup": warmup,
    }

    # Live ping — is Ollama reachable right now?
    if ollama_enabled:
        try:
            import json as _json
            from urllib.request import Request as _Req, urlopen as _urlopen
            req = _Req(f"{ollama_url}/api/tags", headers={"User-Agent": "AnaiTranslator/1.0"})
            with _urlopen(req, timeout=3.0) as resp:
                data = _json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                result["reachable"] = True
                result["models"] = models
                model_base = os.getenv("OLLAMA_MODEL", "mistral").split(":")[0]
                result["model_loaded"] = any(model_base in m for m in models)
        except Exception as exc:
            result["reachable"] = False
            result["error"] = str(exc)
    else:
        result["reachable"] = False
        result["note"] = "Ollama not enabled"

    return result


@app.post("/health/ollama/model")
async def set_ollama_model(request: Request):
    """Switch the active Ollama model at runtime — no restart needed."""
    body = await request.json()
    new_model = (body.get("model") or "").strip()
    if not new_model:
        raise HTTPException(status_code=400, detail="model field is required")

    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    old_model = os.getenv("OLLAMA_MODEL", "mistral")

    # Validate model exists in Ollama
    import json as _json
    try:
        from urllib.request import Request as _Req, urlopen as _urlopen
        req = _Req(f"{ollama_url}/api/tags", headers={"User-Agent": "AnaiTranslator/1.0"})
        with _urlopen(req, timeout=5.0) as resp:
            data = _json.loads(resp.read().decode("utf-8"))
            available = [m.get("name", "") for m in data.get("models", [])]
            model_base = new_model.split(":")[0]
            if not any(model_base in m for m in available):
                raise HTTPException(
                    status_code=404,
                    detail={"error": f"Model '{new_model}' not found", "available_models": available},
                )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Cannot reach Ollama: {exc}")

    # Update at runtime — takes effect on the next AILang call
    os.environ["OLLAMA_MODEL"] = new_model

    # Update warmup state to reflect the switch
    warmup = runtime_state.get("ollama_warmup") or {}
    warmup["status"] = "switched"
    warmup["ollama_model"] = new_model
    warmup["previous_model"] = old_model
    warmup["message"] = f"Switched from {old_model} to {new_model}"
    runtime_state["ollama_warmup"] = warmup

    logger.info("Ollama model switched: %s -> %s", old_model, new_model)

    return {
        "previous_model": old_model,
        "active_model": new_model,
        "available_models": available,
        "message": f"Switched from {old_model} to {new_model}",
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
    
    # Get predictive cache statistics
    predictive_cache_stats = None
    if hasattr(pipeline, 'predictive_cache') and pipeline.predictive_cache:
        predictive_cache_stats = pipeline.predictive_cache.get_statistics()
        predictive_cache_stats["enabled"] = True
        # Add hit/miss tracking
        if hasattr(pipeline, 'get_cache_statistics'):
            cache_stats = pipeline.get_cache_statistics()
            predictive_cache_stats.update({
                "hits": cache_stats.get("hits", 0),
                "misses": cache_stats.get("misses", 0),
                "hit_rate": cache_stats.get("hit_rate", 0.0),
            })
    else:
        predictive_cache_stats = {"enabled": False}

    # Get optimization feedback status
    optimization_feedback = None
    try:
        from backend.optimization_feedback import OptimizationFeedbackLoop
        # Check if feedback loop is initialized (would be in app.py)
        optimization_feedback = {"enabled": False, "status": "not_initialized"}
    except ImportError:
        optimization_feedback = {"enabled": False, "status": "not_available"}

    # Translation health: show fallback chain and remote translator reachability
    import os as _os
    _hybrid_marian_fallback = _os.getenv("HYBRID_ENABLE_MARIAN_FALLBACK", "0") == "1"
    _remote_ok: bool | None = None
    _remote_error: str | None = None
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
        "translation_warmup": runtime_state.get("translation_warmup"),
        "remote_translation_warmup": runtime_state.get("remote_translation_warmup"),
        "translation": {
            "runtime": runtime_state["models"].get("translation_runtime"),
            "backend": runtime_state["models"].get("translation_backend"),
            "device": runtime_state["models"].get("translation_device"),
            "fallback_chain": ["lightweight", "remote_google", "marian" if _hybrid_marian_fallback else None],
            "marian_fallback_enabled": _hybrid_marian_fallback,
            "remote_translator_reachable": _remote_ok,
            "remote_translator_error": _remote_error,
            "tts_google_configured": bool(get_google_tts_api_key()),
        },
        "tts_neural": runtime_state.get("tts_neural"),
        "tts_voice": {
            "engine": runtime_state["models"].get("tts"),
            "natural_voice": get_natural_tts_mode(),
            "partial_tts_mode": get_partial_tts_mode(),
        },
        "persistence": _persistence,
        "cip": cip_health_snapshot(),
        "stt_provider": stt_provider,
        "ailang": {**ailang_stats, "config": ailang_config, "health": ailang_health, "ollama_warmup": runtime_state.get("ollama_warmup")},
        "predictive_cache": predictive_cache_stats,
        "optimization_feedback": optimization_feedback,
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
        "latency": latency_engine.snapshot(),
    }


@app.get("/latency")
def latency_report():
    """Real-time pipeline latency metrics: per-stage timing, percentiles, health."""
    return {
        **latency_engine.snapshot(),
        "health": latency_engine.health_assessment(),
        "translation_tier_metrics": pipeline.translator.get_metrics() if hasattr(pipeline.translator, "get_metrics") else {},
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
            await run_in_threadpool(_synthesize_tts_resilient, "This is a voice test.", output_path, "en")
    except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
        logger.exception("tts_sample_failed")
        raise HTTPException(status_code=503, detail=f"TTS sample unavailable: {exc}") from exc
    return FileResponse(str(output_path), media_type="audio/wav", filename="tts-sample.wav", headers={"Cache-Control": "no-store"})


def _tts_cache_path(cache_key: str) -> Path:
    return _shared_tts_cache_path(cache_key)


def _is_tts_cache_key(cache_key: str) -> bool:
    return _is_shared_tts_cache_key(cache_key)


def _normalize_audio_response_format(response_format: str | None) -> str:
    normalized = (response_format or "base64").strip().lower()
    if normalized not in {"base64", "url", "both"}:
        raise HTTPException(status_code=400, detail="audio response format must be base64, url, or both.")
    return normalized


def _tts_file_ready(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size >= 100
    except OSError:
        return False


def _synthesize_tts_resilient(
    text: str,
    output_path: Path | str,
    language: str,
    google_api_key: str | None = None,
    emotion_config: dict | None = None,
) -> str:
    output_path = Path(output_path)
    first_error: Exception | None = None

    try:
        rendered = pipeline.tts.synthesize(
            text,
            str(output_path),
            language=language,
            google_api_key=google_api_key,
            emotion_config=emotion_config,
        )
        rendered_path = Path(rendered or output_path)
        if _tts_file_ready(rendered_path):
            return str(rendered_path)
        first_error = RuntimeError(f"TTS returned empty audio at {rendered_path}.")
    except Exception as exc:
        first_error = exc

    logger.warning("tts_primary_failed_retrying_fresh language=%s error=%s", language, first_error)
    try:
        rendered = PiperTextToSpeech().synthesize(
            text,
            str(output_path),
            language=language,
            google_api_key=google_api_key,
            emotion_config=emotion_config,
        )
        rendered_path = Path(rendered or output_path)
        if _tts_file_ready(rendered_path):
            return str(rendered_path)
    except Exception as exc:
        raise RuntimeError(f"TTS failed after fresh retry: {exc}") from first_error

    raise RuntimeError("TTS returned empty audio after fresh retry.") from first_error


def _cached_tts_payload(text: str, language: str, response_format: str, google_api_key: str | None = None) -> dict:
    return _cached_tts_payload_impl(
        text,
        language,
        response_format,
        lambda temp_path: _synthesize_tts_resilient(text, temp_path, language=language, google_api_key=google_api_key),
    )


async def _warm_ollama() -> dict:
    """Warm up Ollama + AILang on startup.

    Sends a tiny prompt to Ollama to force model loading into memory.
    This prevents a 10-30s cold-start timeout on the first real request.
    Logs clearly whether AILang intelligence is active or degraded.
    Never raises — always returns a status dict.
    """
    started_at = time()
    ollama_enabled = os.getenv("OLLAMA_ENABLED", "").lower() in ("true", "1", "yes")
    use_llm = os.getenv("USE_LLM_AGENTS", "").lower() in ("true", "1", "yes")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "mistral")

    result = {
        "ollama_enabled": ollama_enabled,
        "use_llm_agents": use_llm,
        "ollama_url": ollama_url,
        "ollama_model": ollama_model,
    }

    # Check if any LLM provider is configured
    openai_key = os.getenv("OPENAI_API_KEY", "")
    openai_available = bool(openai_key and not openai_key.startswith("your_api"))
    has_any_llm = ollama_enabled or use_llm or openai_available

    if not has_any_llm:
        logger.info(
            "AILang: RUNNING IN OFFLINE MODE — no LLM provider configured. "
            "AILang agents use rule-based fallbacks only. "
            "Set OLLAMA_ENABLED=true or OPENAI_API_KEY to activate intelligence layer."
        )
        result["status"] = "offline_mode"
        result["message"] = "No LLM provider configured — AILang using offline rule-based agents only"
        return result

    if not ollama_enabled:
        # OpenAI-only mode — no local warm-up needed, cloud handles cold start
        logger.info(
            "AILang: CLOUD LLM MODE — OpenAI configured, Ollama not enabled. "
            "AILang agents will call OpenAI for intelligence."
        )
        result["status"] = "cloud_mode"
        result["message"] = "OpenAI configured, Ollama not enabled"
        return result

    # Ollama is enabled — try to warm it up
    try:
        import json
        from urllib.request import Request, urlopen
        from urllib.error import URLError, HTTPError

        # Step 1: Check if Ollama is reachable
        try:
            req = Request(
                f"{ollama_url}/api/tags",
                headers={"User-Agent": "AnaiTranslator/1.0"},
            )
            with urlopen(req, timeout=5.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name", "") for m in data.get("models", [])]
                model_base = ollama_model.split(":")[0]
                model_found = any(model_base in m for m in models)
                result["models_available"] = models
                result["target_model_found"] = model_found
        except (URLError, HTTPError, TimeoutError, OSError) as exc:
            logger.warning(
                "AILang: OLLAMA UNREACHABLE at %s — %s. "
                "AILang agents will degrade to offline rule-based fallbacks. "
                "Start Ollama or set OLLAMA_ENABLED=false to suppress this warning.",
                ollama_url, exc,
            )
            result["status"] = "unreachable"
            result["error"] = str(exc)
            result["message"] = f"Ollama unreachable at {ollama_url} — AILang using offline fallbacks"
            return result

        if not model_found:
            logger.warning(
                "AILang: OLLAMA MODEL '%s' NOT FOUND. Available: %s. "
                "Run: ollama pull %s  — AILang will attempt to use it anyway.",
                ollama_model, models, ollama_model,
            )
            result["status"] = "model_not_found"
            result["message"] = f"Model '{ollama_model}' not found in Ollama — pull it first"
            return result

        # Step 2: Send a tiny warm-up prompt to force model into memory
        logger.info(
            "AILang: WARMING UP Ollama model '%s' at %s — loading into memory...",
            ollama_model, ollama_url,
        )
        warmup_prompt = "Translate to Spanish: hello"

        payload = json.dumps({
            "model": ollama_model,
            "prompt": warmup_prompt,
            "stream": False,
            "options": {"temperature": 0.1, "num_predict": 8},
        }).encode("utf-8")

        ollama_timeout = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "60"))
        req = Request(
            f"{ollama_url}/api/generate",
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "AnaiTranslator/1.0"},
            method="POST",
        )
        with urlopen(req, timeout=ollama_timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))

        warmup_ms = round((time() - started_at) * 1000)
        warmup_response = data.get("response", "")[:80]

        logger.info(
            "AILang: OLLAMA READY — model '%s' loaded in %dms. "
            "AILang intelligence layer is ACTIVE (Ollama -> OpenAI -> CIP -> stubs).",
            ollama_model, warmup_ms,
        )
        result["status"] = "active"
        result["warmup_ms"] = warmup_ms
        result["warmup_response_preview"] = warmup_response
        result["message"] = f"Ollama model '{ollama_model}' loaded and ready ({warmup_ms}ms)"
        return result

    except Exception as exc:
        logger.warning(
            "AILang: OLLAMA WARM-UP FAILED — %s. "
            "AILang agents will degrade to offline rule-based fallbacks. "
            "First real request may be slow while model loads.",
            exc,
        )
        result["status"] = "warmup_failed"
        result["error"] = str(exc)
        result["message"] = f"Ollama warm-up failed: {exc} — AILang using offline fallbacks"
        return result


async def _warm_translation_cache(reason: str) -> dict:
    started_at = time()
    warmed = []
    runtime_state["translation_warmup"] = {"status": "running", "started_at": started_at, "reason": reason}
    for source_language, target_language, text in TRANSLATION_WARMUP_TEXTS:
        try:
            translated = await run_in_threadpool(
                pipeline.translator.translate,
                text,
                source_language,
                target_language,
            )
            warmed.append({
                "source_language": source_language,
                "target_language": target_language,
                "text": text,
                "translated": translated,
                "ok": bool(translated) and "None" not in translated and not translated.startswith(f"[{source_language}->"),
            })
            observability.record_event(
                "translation_warmup",
                source_language=source_language,
                target_language=target_language,
                reason=reason,
            )
        except (RuntimeError, ValueError, OSError, TimeoutError, MemoryError) as exc:
            logger.warning(
                "translation_warmup_failed source=%s target=%s reason=%s error=%s",
                source_language,
                target_language,
                reason,
                exc,
            )
            warmed.append({
                "source_language": source_language,
                "target_language": target_language,
                "text": text,
                "ok": False,
                "error": exc.__class__.__name__,
            })
    result = {
        "status": "complete",
        "reason": reason,
        "latency_seconds": round(time() - started_at, 3),
        "items": warmed,
    }
    runtime_state["translation_warmup"] = result
    return result


async def _warm_remote_translation_cache(reason: str) -> dict:
    """Prime the cloud translation cache without loading heavy local models."""
    if os.getenv("HYBRID_ENABLE_REMOTE", "1").strip().lower() in {"0", "false", "no", "off"}:
        result = {
            "status": "skipped",
            "reason": "HYBRID_ENABLE_REMOTE",
            "message": "Remote translation warmup disabled",
            "items": [],
        }
        runtime_state["remote_translation_warmup"] = result
        return result

    from translation.remote_translator import RemoteTranslator

    started_at = time()
    remote = RemoteTranslator()
    warmed = []
    runtime_state["remote_translation_warmup"] = {"status": "running", "started_at": started_at, "reason": reason}
    for source_language, target_language, text in REMOTE_TRANSLATION_WARMUP_TEXTS:
        try:
            translated = await run_in_threadpool(
                remote.translate,
                text,
                source_language,
                target_language,
            )
            warmed.append({
                "source_language": source_language,
                "target_language": target_language,
                "text": text,
                "translated": translated[:120],
                "ok": bool(translated) and not translated.startswith(f"[{source_language}->"),
            })
            observability.record_event(
                "remote_translation_warmup",
                source_language=source_language,
                target_language=target_language,
                reason=reason,
            )
        except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
            logger.warning(
                "remote_translation_warmup_failed source=%s target=%s reason=%s error=%s",
                source_language,
                target_language,
                reason,
                exc,
            )
            warmed.append({
                "source_language": source_language,
                "target_language": target_language,
                "text": text,
                "ok": False,
                "error": exc.__class__.__name__,
            })
    result = {
        "status": "complete",
        "reason": reason,
        "latency_seconds": round(time() - started_at, 3),
        "items": warmed,
        "ok_count": sum(1 for item in warmed if item.get("ok")),
        "total": len(warmed),
    }
    runtime_state["remote_translation_warmup"] = result
    return result


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
    request.target_language = _normalize_language(request.target_language, "ht")
    route = resolve_barrier_route(
        request.text,
        request.source_language,
        request.target_language,
        enabled=True,
    )
    request.source_language = route["source_language"]
    request.target_language = route["target_language"]
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
        use_quality = _translation_wants_quality(request.translation_mode, request.translation_quality)
        
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
        
        translate_kwargs = dict(
            text=request.text,
            source_language=request.source_language,
            target_language=request.target_language,
            tone=request.tone,
            synthesize_audio=False,
            speaker=speaker,
            confidence=confidence,
            quality=use_quality,
        )
        if req_translator:
            interim = pipeline.translate_text_with(req_translator, **translate_kwargs)
        else:
            interim = pipeline.translate_text(**translate_kwargs)
        if (
            not use_quality
            and interim.translated_text
            and is_internal_translation_artifact(interim.translated_text)
        ):
            translate_kwargs["quality"] = True
            if req_translator:
                interim = pipeline.translate_text_with(req_translator, **translate_kwargs)
            else:
                interim = pipeline.translate_text(**translate_kwargs)
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
        cip_clarify = should_block_translation_for_cip(cip, refined_text, tr_conf)
        final_text = "" if cip_clarify else choose_translation(cip, refined_text)
        if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
            semantic_context["last_intent"] = cip["analysis"].get("intent") or "statement"
            semantic_context["conversation_mood"] = cip["analysis"].get("tone") or "neutral"
        # Confidence/clarify for text path
        tr_conf = estimate_translation_confidence(request.text, final_text)
        cip_conf = get_cip_confidence(cip)
        conf_score = cip_conf if cip_conf is not None else confidence_engine.evaluate(stt_conf, tr_conf)
        audio_path = None
        audio_payload = None
        if request.synthesize_audio and final_text and not cip_clarify:
            try:
                audio_payload = _cached_tts_payload(final_text, request.target_language, audio_response_format, google_api_key=_google_key)
                audio_path = audio_payload["audio_output_path"]
            except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
                logger.warning("text_translation_tts_unavailable identity=%s target=%s error=%s", identity, request.target_language, exc)
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
        apply_cip_decision(response_dict, cip, blocking=cip_clarify)
        
        # Include AILang metadata in response
        if interim.ailang_metadata:
            response_dict["ailang_metadata"] = interim.ailang_metadata
        
        if conf_score < 0.4 and not response_dict.get("clarify"):
            response_dict["clarify"] = True
            response_dict["clarify_message"] = clarification_for(request.text, detect_ambiguities(request.text))
        if audio_payload and not response_dict.get("clarify"):
            response_dict.update(audio_payload)
            response_dict["translated_text"] = final_text
            observability.record_event("text_translation_tts", identity=identity, cache_hit=audio_payload["cache_hit"], response_format=audio_response_format)
        elif request.synthesize_audio and final_text and not response_dict.get("clarify"):
            response_dict["audio_unavailable"] = True
            response_dict["audio_fallback"] = "browser_tts"
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
                connected=False,
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
    target_language: str = Form("ht"),
    synthesize_audio: bool = Form(True),
    identity: str = Depends(authenticate_http),
):
    started_at = time()
    metrics["http_requests"] += 1
    usage_limiter.track(identity, "http_requests")
    source_language = _normalize_language(source_language, "en")
    target_language = _normalize_language(target_language, "ht")
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
    filename_suffix = _safe_upload_suffix(audio.filename, "audio.webm", {".webm", ".wav", ".m4a", ".mp3", ".ogg", ".aac"})
    suffix = audio_suffix_for_bytes(audio_bytes, audio.content_type) or filename_suffix
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
        cip_clarify = should_block_translation_for_cip(cip, refined_text, tr_conf)
        final_text = "" if cip_clarify else choose_translation(cip, refined_text)
        if isinstance(cip, dict) and isinstance(cip.get("analysis"), dict):
            semantic_context["last_intent"] = cip["analysis"].get("intent") or "statement"
            semantic_context["conversation_mood"] = cip["analysis"].get("tone") or "neutral"
        # Confidence/clarify for audio path
        tr_conf = estimate_translation_confidence(source_text, final_text)
        cip_conf = get_cip_confidence(cip)
        conf_score = cip_conf if cip_conf is not None else confidence_engine.evaluate(stt_conf, tr_conf)
        audio_path = None
        audio_unavailable = False
        if synthesize_audio and final_text and conf_score >= 0.4 and not cip_clarify:
            try:
                audio_path = await run_in_threadpool(
                    _synthesize_tts_resilient,
                    final_text,
                    f"models/tts/{uuid4()}.wav",
                    target_language,
                )
            except (RuntimeError, ValueError, OSError, TimeoutError) as exc:
                audio_unavailable = True
                logger.warning("audio_translation_tts_unavailable identity=%s target=%s error=%s", identity, target_language, exc)
        result = type(interim)(
            source_text=source_text, improved_text=interim.improved_text,
            translated_text=final_text, audio_output_path=audio_path,
        )
        observability.observe_latency("audio_translation", time() - started_at)
        usage_limiter.track_audio(identity, estimated_seconds, "audio_translations")
        response_dict = dict(result.__dict__)
        apply_cip_decision(response_dict, cip, blocking=cip_clarify)
        if audio_unavailable and not response_dict.get("clarify"):
            response_dict["audio_unavailable"] = True
            response_dict["audio_fallback"] = "browser_tts"
        if result.audio_output_path and not response_dict.get("clarify"):
            try:
                ab = Path(result.audio_output_path).read_bytes()
                if len(ab) >= 100:
                    response_dict["audio_base64"] = base64.b64encode(ab).decode("ascii")
                    response_dict["mime_type"] = "audio/wav"
            except (OSError, IOError):
                pass
        return response_dict
    except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError):
        usage_limiter.track(identity, "errors")
        observability.increment("translation_failures_total")
        raise
    finally:
        with suppress(Exception):
            audio_path.unlink(missing_ok=True)


@app.post("/translate/image")
async def translate_image(image: UploadFile = File(...), source_language: str = Form("auto"), target_language: str = Form("es"), synthesize_audio: bool = Form(False), identity: str = Depends(authenticate_http)):
    raise HTTPException(status_code=503, detail="Image translation requires Tesseract OCR.")


@app.post("/vad")
async def detect_voice_activity(audio: UploadFile = File(...), identity: str = Depends(authenticate_http)):
    metrics["http_requests"] += 1
    audio_bytes = await _read_limited_upload(audio, get_max_audio_mb() * 1024 * 1024)
    filename_suffix = _safe_upload_suffix(audio.filename, "audio.webm", {".webm", ".wav", ".m4a", ".mp3", ".ogg", ".aac"})
    suffix = audio_suffix_for_bytes(audio_bytes, audio.content_type) or filename_suffix
    return await run_in_threadpool(vad.detect_bytes, audio_bytes, suffix)


@app.websocket("/ws/assistant")
async def websocket_assistant(websocket: WebSocket):
    await websocket.accept()
    if not naia_assistant.is_available():
        detail = "Assistant unavailable"
        err = naia_assistant.import_error()
        if err:
            detail = f"{detail}: {err}"
        await websocket.send_json({"event": "error", "detail": detail})
        await websocket.close()
        return

    while True:
        try:
            payload = await websocket.receive_json()
        except WebSocketDisconnect:
            break
        message = str(payload.get("message") or "").strip()
        if not message:
            await websocket.send_json({"event": "error", "detail": "message is required"})
            continue
        await websocket.send_json({"event": "started"})
        try:
            response = await naia_assistant.chat(
                message,
                source="websocket",
                translation_context=payload.get("translation_context"),
                metadata=payload.get("metadata"),
            )
        except ValueError as exc:
            await websocket.send_json({"event": "error", "detail": str(exc)})
            continue
        except (RuntimeError, TimeoutError) as exc:
            await websocket.send_json({"event": "error", "detail": str(exc)})
            continue
        await websocket.send_json({"event": "completed", "response": response})


@app.websocket("/ws/translate")
async def websocket_translate(websocket: WebSocket):
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    metrics["websocket_connections"] += 1
    try:
        await websocket_text_translation(websocket, pipeline)
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        metrics["websocket_errors"] += 1
        with suppress(Exception):
            await websocket.close(code=1011, reason="Internal WebSocket error")


@app.websocket("/ws/audio")
async def websocket_audio(websocket: WebSocket):
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    metrics["websocket_connections"] += 1
    try:
        if get_stt_provider() == "streaming":
            from backend.streaming import websocket_streaming_stt_translation
            await websocket_streaming_stt_translation(websocket, pipeline, conversation_brain, memory, speaker_memory, identity)
        else:
            await websocket_audio_translation(websocket, pipeline, vad, conversation_brain, memory, speaker_memory, identity, global_latency_engine=latency_engine)
    except WebSocketDisconnect:
        pass
    except (RuntimeError, ValueError, ConnectionError, TimeoutError):
        metrics["websocket_errors"] += 1
        await websocket.close(code=1011, reason="Internal WebSocket error")


@app.websocket("/ws/audio/streaming")
async def websocket_audio_streaming(websocket: WebSocket):
    from backend.streaming import websocket_streaming_stt_translation
    ok, identity = await authenticate_websocket(websocket)
    if not ok:
        return
    if get_stt_provider() != "streaming":
        await websocket.close(code=1008, reason="STT provider is not in streaming mode")
        return
    metrics["websocket_connections"] += 1
    try:
        await websocket_streaming_stt_translation(websocket, pipeline, conversation_brain, memory, speaker_memory, identity)
    except WebSocketDisconnect:
        pass


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
