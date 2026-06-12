"""Health and diagnostics helpers used by `backend.api`.

These were extracted from `backend.api` to keep the route module focused
on routing. `backend.api` re-exports `_stt_provider_health_snapshot`
under its original underscore name because tests reference it.

`runtime_state` is module-global state for runtime warmup/readiness.
It lives here so other modules (route handlers, websocket lifespan)
can share a single source of truth.
"""

from __future__ import annotations

import json
from time import time
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from backend.config import (
    get_stt_provider,
    get_stt_provider_url,
    get_stt_provider_ws_url,
)
from backend.model_readiness import evaluate_preload_result
from backend.security import WEBSOCKET_AUTH_RELEASE


RELEASE_ID = "2026-06-06-railway-backend-v20"


runtime_state: dict = {
    "ready": False,
    "started_at": time(),
    "models": {},
}


metrics: dict = {
    "http_requests": 0,
    "websocket_connections": 0,
    "websocket_errors": 0,
}


def stt_provider_health_snapshot(timeout_seconds: float = 1.5) -> dict:
    """Probe the configured STT provider and return a structured snapshot.

    Uses the provider's ``/health`` endpoint (which returns connection stats
    in the updated v0.2 server) and falls back gracefully to ``/health/live``
    if the richer endpoint is unavailable.
    """

    mode = get_stt_provider()
    snapshot = {
        "mode": mode,
        "url": get_stt_provider_url(),
        "ws_url": get_stt_provider_ws_url(),
        "reachable": None,
        "status_code": None,
        "latency_ms": None,
    }
    if mode != "streaming":
        return snapshot

    health_url = f"{snapshot['url']}/health"
    snapshot["health_url"] = health_url
    started_at = time()
    try:
        req = UrlRequest(health_url, headers={"User-Agent": "AnaiTranslator/1.0"})
        with urlopen(req, timeout=timeout_seconds) as resp:
            snapshot["reachable"] = 200 <= resp.status < 500
            snapshot["status_code"] = resp.status
            snapshot["latency_ms"] = round((time() - started_at) * 1000)
            try:
                body = json.loads(resp.read().decode("utf-8"))
                snapshot["active_connections"] = body.get("active_connections")
                snapshot["max_active_connections"] = body.get("max_active_connections")
                snapshot["provider_app"] = body.get("app")
            except Exception:
                pass
    except (URLError, TimeoutError, ConnectionError, OSError) as exc:
        snapshot["reachable"] = False
        snapshot["error"] = exc.__class__.__name__
        snapshot["latency_ms"] = round((time() - started_at) * 1000)
    return snapshot


def voice_warmup_blocks_ready() -> bool:
    """True while startup voice cache warmup is still in progress."""

    voice = runtime_state.get("voice_warmup") or {}
    status = str(voice.get("status") or "").strip().lower()
    return bool(status and status not in ("complete", "skipped", "failed"))


def runtime_payload(include_details: bool = False) -> dict:
    """Compose the JSON payload returned by `/health`, `/ready`, etc."""

    ready = bool(runtime_state["ready"]) and not voice_warmup_blocks_ready()
    payload = {
        "status": "ok" if ready else "warming",
        "ready": ready,
        "release": RELEASE_ID,
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
    }
    readiness = runtime_state.get("readiness")
    if readiness and not ready:
        payload["blockers"] = readiness.get("blockers") or []
        payload["warnings"] = readiness.get("warnings") or []
        if payload["blockers"]:
            payload["status"] = "degraded"
    if include_details:
        stt_provider = stt_provider_health_snapshot()
        preload = runtime_state.get("models", {}).get("preloaded")
        readiness = runtime_state.get("readiness") or evaluate_preload_result(preload if isinstance(preload, dict) else None)
        ready = ready and bool(readiness.get("ready", True))
        payload.update(
            {
                "models": runtime_state["models"],
                "readiness": readiness,
                "voice_warmup": runtime_state.get("voice_warmup"),
                "websocket_auth_release": WEBSOCKET_AUTH_RELEASE,
                "stt_provider": stt_provider,
            }
        )
        if stt_provider["mode"] == "streaming" and not stt_provider.get("reachable"):
            ready = False
        payload["ready"] = ready
        if not ready:
            payload["status"] = "degraded" if runtime_state.get("ready") else "warming"
    return payload


__all__ = [
    "RELEASE_ID",
    "runtime_state",
    "metrics",
    "voice_warmup_blocks_ready",
    "stt_provider_health_snapshot",
    "runtime_payload",
]
