"""Health and diagnostics helpers used by `backend.api`.

These were extracted from `backend.api` to keep the route module focused
on routing. `backend.api` re-exports `_stt_provider_health_snapshot`
under its original underscore name because tests reference it.

`runtime_state` is module-global state for runtime warmup/readiness.
It lives here so other modules (route handlers, websocket lifespan)
can share a single source of truth.
"""

from __future__ import annotations

from time import time
from urllib.error import URLError
from urllib.request import Request as UrlRequest, urlopen

from backend.config import (
    get_stt_provider,
    get_stt_provider_url,
    get_stt_provider_ws_url,
)
from backend.security import WEBSOCKET_AUTH_RELEASE


RELEASE_ID = "2026-05-13-active-speaker-v19"


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
    """Probe the configured STT provider and return a structured snapshot."""

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
    except (URLError, TimeoutError, ConnectionError) as exc:
        snapshot["reachable"] = False
        snapshot["error"] = exc.__class__.__name__
        snapshot["latency_ms"] = round((time() - started_at) * 1000)
    return snapshot


def runtime_payload(include_details: bool = False) -> dict:
    """Compose the JSON payload returned by `/health`, `/ready`, etc."""

    payload = {
        "status": "ok" if runtime_state["ready"] else "warming",
        "ready": runtime_state["ready"],
        "release": RELEASE_ID,
        "uptime_seconds": round(time() - runtime_state["started_at"], 2),
    }
    if include_details:
        stt_provider = stt_provider_health_snapshot()
        payload.update(
            {
                "models": runtime_state["models"],
                "voice_warmup": runtime_state.get("voice_warmup"),
                "websocket_auth_release": WEBSOCKET_AUTH_RELEASE,
                "stt_provider": stt_provider,
            }
        )
        if stt_provider["mode"] == "streaming" and not stt_provider.get("reachable"):
            payload["ready"] = False
            payload["status"] = "degraded" if runtime_state["ready"] else "warming"
    return payload


__all__ = [
    "RELEASE_ID",
    "runtime_state",
    "metrics",
    "stt_provider_health_snapshot",
    "runtime_payload",
]
