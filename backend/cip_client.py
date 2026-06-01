import json
import logging
from time import time
from urllib.error import HTTPError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request as UrlRequest, urlopen

from backend.config import get_cip_mode, get_cip_process_url, get_cip_retries, get_cip_timeout_seconds

from backend.cip_engine import evaluate_local_cip
from backend.observability import observability
from backend.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError, get_circuit_breaker
from backend.service_health import get_service_health_manager, record_service_success, record_service_failure

logger = logging.getLogger("anai_translator.cip_client")


def cip_settings() -> dict:
    url = get_cip_process_url()
    mode = get_cip_mode()
    local_enabled = mode in {"ut_first", "cip_first"}
    external_configured = bool(url)
    external_enabled = external_configured and mode == "cip_first"
    return {
        "mode": mode,
        "process_url": url,
        "configured": local_enabled or external_configured,
        "external_configured": external_configured,
        "local_enabled": local_enabled,
        "external_enabled": external_enabled,
        "enabled": local_enabled or external_enabled,
        "provider": "external" if external_enabled else ("local" if local_enabled else "off"),
        "local_engine": "python_ai_brain_v8" if local_enabled else None,
        "timeout_seconds": get_cip_timeout_seconds(),
        "retries": get_cip_retries(),
    }


def cip_enabled() -> bool:
    settings = cip_settings()
    return bool(settings["enabled"])


def _cip_endpoint(path: str) -> str:
    base_url = get_cip_process_url()
    if not base_url:
        return ""
    parsed = urlsplit(base_url)
    if parsed.scheme and parsed.netloc:
        return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))
    return f"{base_url.rstrip('/')}{path}"


def _json_safe(value):
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    return str(value)


def cip_health_snapshot(timeout: float | None = None) -> dict:
    settings = cip_settings()
    snapshot = {
        **settings,
        "health_url": _cip_endpoint("/health"),
        "openai_diagnostics_url": _cip_endpoint("/diagnostics/openai"),
        "reachable": bool(settings["local_enabled"]),
        "external_reachable": False,
        "status_code": None,
        "latency_ms": None,
        "openai": None,
        "error": None,
        "external_error": None,
    }
    if not settings["enabled"]:
        snapshot["error"] = "disabled"
        return snapshot
    if not settings["external_configured"]:
        snapshot["status"] = "local"
        snapshot["external_error"] = "not_configured"
        return snapshot

    request_timeout = timeout if timeout is not None else get_cip_timeout_seconds()
    started_at = time()
    try:
        req = UrlRequest(snapshot["health_url"], headers={"User-Agent": "AnaiTranslator-CIPDiagnostics/1.0"})
        with urlopen(req, timeout=request_timeout) as resp:
            snapshot["status_code"] = resp.status
            snapshot["external_reachable"] = 200 <= resp.status < 500
            snapshot["reachable"] = snapshot["external_reachable"] or bool(settings["local_enabled"])
            snapshot["latency_ms"] = round((time() - started_at) * 1000, 1)
    except HTTPError as exc:
        snapshot["status_code"] = exc.code
        snapshot["latency_ms"] = round((time() - started_at) * 1000, 1)
        snapshot["external_error"] = exc.__class__.__name__
    except (URLError, TimeoutError, ConnectionError) as exc:
        snapshot["latency_ms"] = round((time() - started_at) * 1000, 1)
        snapshot["external_error"] = exc.__class__.__name__

    try:
        req = UrlRequest(snapshot["openai_diagnostics_url"], headers={"User-Agent": "AnaiTranslator-CIPDiagnostics/1.0"})
        with urlopen(req, timeout=request_timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            snapshot["openai"] = json.loads(body)
    except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
        snapshot["openai"] = {"error": exc.__class__.__name__}
    return snapshot


def _call_external_cip(
    text: str,
    target_language: str,
    session_id: str | None,
    timeout: float | None,
    payload_context: dict,
) -> dict | None:
    process_url = get_cip_process_url()
    if not process_url:
        return None

    # Get or create circuit breaker for CIP external calls
    cb_config = CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
        success_threshold=2,
        timeout=timeout if timeout is not None else get_cip_timeout_seconds(),
    )
    circuit_breaker = get_circuit_breaker("cip_external", cb_config)

    request_timeout = timeout if timeout is not None else get_cip_timeout_seconds()
    span_start = time()
    payload = json.dumps(_json_safe({
        "text": text,
        "targetLanguage": target_language,
        "sessionId": session_id or "default",
        **payload_context,
    })).encode("utf-8")

    async def make_request():
        for attempt in range(get_cip_retries() + 1):
            try:
                req = UrlRequest(process_url, data=payload, headers={
                    "Content-Type": "application/json",
                    "User-Agent": "AnaiTranslator-CIPBridge/1.0",
                })
                with urlopen(req, timeout=request_timeout) as resp:
                    body = resp.read().decode("utf-8", errors="ignore")
                    result = json.loads(body)
                    if isinstance(result, dict):
                        result.setdefault("provider", "external")
                        result.setdefault("translation_source", "CIP")
                    observability.record_event("cip_call", success=True, attempt=attempt, latency_seconds=time() - span_start, session_id=session_id)
                    observability.observe_latency("cip_call", time() - span_start)
                    return result
            except (URLError, TimeoutError, ConnectionError, json.JSONDecodeError) as exc:
                observability.increment("cip_failures_total")
                observability.record_event(
                    "cip_call",
                    success=False,
                    attempt=attempt,
                    latency_seconds=time() - span_start,
                    session_id=session_id,
                    error=exc.__class__.__name__,
                )
                if attempt < get_cip_retries():
                    import asyncio
                    await asyncio.sleep(0.1 * (attempt + 1))  # Exponential backoff
        return None

    # Try circuit breaker protected call
    try:
        import asyncio
        result = asyncio.run(circuit_breaker.call(make_request))
        if result:
            record_service_success("cip_external", {"provider": "external"})
        return result
    except CircuitBreakerOpenError:
        observability.increment("cip_circuit_breaker_rejections_total")
        logger.warning("CIP circuit breaker OPEN, skipping external CIP call")
        record_service_failure("cip_external", {"reason": "circuit_breaker_open"})
        return None


def call_cip_brain(
    text: str,
    target_language: str,
    session_id: str | None = None,
    timeout: float | None = None,
    *,
    fallback_translation: str | None = None,
    source_language: str | None = None,
    stt_confidence: float | None = None,
    translation_confidence: float | None = None,
    context=None,
    speaker_context=None,
    semantic_context: dict | None = None,
) -> dict | None:
    if not cip_enabled() or not text or not target_language:
        return None

    settings = cip_settings()
    payload_context = {
        "fallbackTranslation": fallback_translation,
        "sourceLanguage": source_language,
        "sttConfidence": stt_confidence,
        "translationConfidence": translation_confidence,
        "context": context or [],
        "speakerContext": speaker_context or {},
        "semanticContext": semantic_context or {},
    }

    if settings["external_enabled"]:
        external = _call_external_cip(text, target_language, session_id, timeout, payload_context)
        if external:
            return external

    return evaluate_local_cip(
        text,
        target_language,
        fallback_translation=fallback_translation,
        source_language=source_language,
        stt_confidence=stt_confidence,
        translation_confidence=translation_confidence,
        context=context,
        speaker_context=speaker_context,
        semantic_context=semantic_context,
    )
