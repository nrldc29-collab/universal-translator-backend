"""
Main FastAPI application for the True Streaming STT service.

This module contains the primary FastAPI application setup, including:
- Health check endpoints (live, ready, detailed)
- WebSocket streaming endpoint for real-time transcription
- File-based transcription endpoint
- Rate limiting and CORS configuration
- Admin and management API routers
- Metrics and monitoring endpoints

The application supports multi-tenant architecture with RBAC, rate limiting,
and comprehensive logging for audit trails.
"""
import asyncio
import csv
import io
import json
import logging
import os
import tempfile
import time
import uuid
import warnings
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from fastapi import (
    APIRouter,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    Response,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
    WebSocketException,
    status,
    Body,
)
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address
import gzip

from stt_server.auth import api_key_fingerprint, api_key_label, is_valid_api_key
from stt_server.admin_backend import router as admin_backend_router
from stt_server.admin_models import router as admin_models_router
from stt_server.models_api import router as models_router
from stt_server.speaker_profiles_api import router as speaker_profiles_router
from stt_server.usage_api import router as usage_router
from stt_server.config import settings
from stt_server.logging_utils import (
    ADMIN_AUDIT_LOG_PATH,
    configure_logging,
    get_trace_id,
    log_admin_event,
    log_event,
    new_trace_id,
    set_trace_id,
)
from stt_server.metrics import metrics, render_prometheus_metrics
from stt_server.model import transcribe_pcm16_file, warmup_model
from stt_server.model_override_audit import audit_model_override
from stt_server.model_registry import validate_model_id
from stt_server.rbac import Scope, require_scope
from stt_server.tenant_rollout import get_tenant_rollout_config
from stt_server.streaming import StreamingTranscriptionSession
from stt_server.tenant_throttling import get_throttler
from stt_server.usage import usage_store
from stt_server.rate_limit_headers import add_rate_limit_headers, add_tenant_rate_limit_headers

logger = logging.getLogger(__name__)

# Global state for connection tracking
active_connections = 0
active_connections_by_key_label: dict[str, int] = {}
is_draining = False


def rate_limit_key(request: Request) -> str:
    """
    Extract rate limit key from request.
    
    Uses API key from Authorization header if available, otherwise uses remote address.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Rate limit key string
    """
    api_key = request.headers.get("authorization", "")

    if api_key.lower().startswith("bearer "):
        return api_key[7:].strip()

    return api_key or get_remote_address(request)


limiter = Limiter(key_func=rate_limit_key)

health_router = APIRouter()


@health_router.get("/health/live")
async def health_live() -> dict[str, str]:
    """
    Liveness health check endpoint.
    
    Returns basic liveness status indicating the service is running.
    This endpoint should always return 200 if the service process is alive.
    
    Returns:
        Dictionary with status and check type
    """
    return {
        "status": "ok",
        "check": "live",
    }


@health_router.get("/health/ready")
async def health_ready(response: Response) -> dict[str, str]:
    """
    Readiness health check endpoint.
    
    Returns readiness status indicating the service is ready to accept traffic.
    Returns 503 if the service is in draining mode.
    
    Args:
        response: FastAPI response object for setting status code
        
    Returns:
        Dictionary with status and check type
    """
    if is_draining:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {
            "status": "draining",
            "check": "ready",
        }

    return {
        "status": "ok",
        "check": "ready",
    }


@health_router.get("/health")
async def health_detailed() -> dict[str, Any]:
    """
    Detailed health check with dependency status.
    
    Performs health checks on all dependencies (database, Redis, Triton)
    and returns detailed status information.
    
    Returns:
        Dictionary with overall status and detailed check results
    """
    checks = {
        "status": "healthy",
        "checks": {},
    }
    
    overall_healthy = True
    
    # Database health check
    try:
        if settings.database_url:
            checks["checks"]["database"] = {"status": "healthy"}
        else:
            checks["checks"]["database"] = {"status": "skipped", "reason": "not configured"}
    except Exception as e:
        logger.error(f"Database health check failed: {e}")
        checks["checks"]["database"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Redis health check
    try:
        from stt_server.connection_counters import redis_client
        if redis_client:
            await redis_client.ping()
            checks["checks"]["redis"] = {"status": "healthy"}
        else:
            checks["checks"]["redis"] = {"status": "skipped", "reason": "not configured"}
    except Exception as e:
        logger.error(f"Redis health check failed: {e}")
        checks["checks"]["redis"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Triton health check
    try:
        from stt_server.backends.triton import TritonStreamingClient
        if settings.stt_backend == "triton":
            triton = TritonStreamingClient(
                grpc_url=os.environ.get("TRITON_GRPC_URL", ""),
                asr_model=os.environ.get("TRITON_ASR_MODEL", ""),
                diarization_model=os.environ.get("TRITON_DIARIZATION_MODEL", ""),
                timeout_ms=5000,
            )
            if triton.is_ready():
                checks["checks"]["triton"] = {"status": "healthy"}
            else:
                checks["checks"]["triton"] = {"status": "unhealthy", "reason": "not ready"}
                overall_healthy = False
        else:
            checks["checks"]["triton"] = {"status": "skipped", "reason": "not configured"}
    except Exception as e:
        logger.error(f"Triton health check failed: {e}")
        checks["checks"]["triton"] = {"status": "unhealthy", "error": str(e)}
        overall_healthy = False
    
    # Draining status
    if is_draining:
        checks["status"] = "draining"
        checks["draining"] = True
    elif not overall_healthy:
        checks["status"] = "unhealthy"
    
    return checks


warnings.filterwarnings(
    "ignore",
    message="'asyncio.iscoroutinefunction' is deprecated.*",
    category=DeprecationWarning,
)


def estimated_cost(audio_seconds: float) -> float:
    """
    Calculate estimated cost for audio transcription.
    
    Args:
        audio_seconds: Duration of audio in seconds
        
    Returns:
        Estimated cost in currency units
    """
    audio_hours = audio_seconds / 3600
    return round(audio_hours * settings.billing_rate_per_audio_hour, 6)


def total_estimated_audio_seconds() -> float:
    """
    Calculate total estimated audio seconds across all usage counters.
    
    Returns:
        Total estimated audio seconds
    """
    return sum(
        counter.estimated_audio_seconds
        for counter in usage_store.by_key_label.values()
    )


def get_allowed_origins() -> set[str]:
    """
    Parse and return allowed CORS origins from settings.
    
    Returns:
        Set of allowed origin strings
    """
    return {
        origin.strip()
        for origin in settings.allowed_origins.split(",")
        if origin.strip()
    }


def is_allowed_websocket_origin(origin: str | None) -> bool:
    """
    Check if WebSocket origin is allowed based on CORS configuration.
    
    Args:
        origin: Origin header from WebSocket request, None if not present
        
    Returns:
        True if origin is allowed or not provided, False otherwise
    """
    if origin is None:
        return True

    return origin in get_allowed_origins()


def validate_startup_config() -> None:
    """
    Validate required configuration settings on startup.
    
    Ensures that STT_API_KEY is configured when running outside of
    development environment to prevent accidental insecure deployments.
    
    Raises:
        RuntimeError: If STT_API_KEY is not configured in non-dev environment
    """
    logger.debug(f"Validating startup config for environment: {settings.env}")
    if settings.env != "dev" and not settings.stt_api_key:
        logger.error("STT_API_KEY not configured in non-dev environment")
        raise RuntimeError(
            "STT_API_KEY must be explicitly configured outside dev environments."
        )
    logger.debug("Startup config validation passed")


def build_decoder_options(
    hotwords: str | None = None,
    initial_prompt: str | None = None,
    beam_size: int | None = None,
    word_timestamps: bool | None = None,
    temperature: float | None = None,
) -> dict[str, Any]:
    """
    Build decoder options dictionary for transcription model.
    
    Parses hotwords string into a list and filters out None values
    to create a clean decoder options dictionary.
    
    Args:
        hotwords: Comma-separated list of hotwords for biasing transcription
        initial_prompt: Initial prompt text to guide transcription
        beam_size: Beam search size for decoding
        word_timestamps: Whether to include word-level timestamps
        temperature: Sampling temperature for decoder
        
    Returns:
        Dictionary of decoder options with None values filtered out
    """
    decoder_options: dict[str, Any] = {
        "hotwords": [
            word.strip()
            for word in hotwords.split(",")
            if word.strip()
        ]
        if hotwords
        else None,
        "initial_prompt": initial_prompt,
        "beam_size": beam_size,
        "word_timestamps": word_timestamps,
        "temperature": temperature,
    }

    options = {
        key: value
        for key, value in decoder_options.items()
        if value is not None
    }
    logger.debug(f"Built decoder options: {list(options.keys())}")
    return options


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager for startup and shutdown events.
    
    Handles application startup including configuration validation, logging setup,
    usage data loading, model warmup, and graceful shutdown with connection draining.
    
    Args:
        app: FastAPI application instance
        
    Yields:
        None - control is yielded back to FastAPI during application runtime
    """
    global is_draining
    
    logger.info(f"Starting {settings.app_name}")
    configure_logging()
    
    # Validate configuration
    validate_startup_config()
    
    usage_store.load()
    metrics.restore_from_usage_store()
    log_event("server.starting", app=settings.app_name)
    warmup_model()
    log_event("server.ready", app=settings.app_name)
    logger.info(f"{settings.app_name} ready to accept connections")
    
    yield
    
    # Graceful shutdown sequence
    logger.info(f"Shutting down {settings.app_name}")
    log_event("server.shutdown_initiated", app=settings.app_name)
    
    # Set draining flag to stop accepting new connections
    is_draining = True
    log_event("server.draining_connections", active_connections=active_connections)
    
    # Wait for active connections to drain (with timeout)
    shutdown_timeout = 30  # seconds
    shutdown_start = time.time()
    
    while active_connections > 0 and (time.time() - shutdown_start) < shutdown_timeout:
        log_event(
            "server.waiting_for_connections",
            active_connections=active_connections,
            remaining_time=shutdown_timeout - (time.time() - shutdown_start),
        )
        await asyncio.sleep(1)
    
    # Log final state
    if active_connections > 0:
        log_event(
            "server.shutdown_timeout",
            active_connections=active_connections,
            message="Some connections did not drain gracefully",
        )
        logger.warning(f"Shutdown timeout: {active_connections} connections still active")
    else:
        log_event("server.all_connections_drained")
        logger.info("All connections drained gracefully")
    
    # Save usage data
    usage_store.save()
    log_event("server.usage_saved")
    
    # Final shutdown logging
    log_event("server.stopping", app=settings.app_name)
    logger.info(f"{settings.app_name} stopped")


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
    version="1.0.0",
    description="Self-hosted streaming speech-to-text provider with WebSocket and REST APIs",
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    """Middleware to add request ID tracking to all requests."""
    # Check for existing trace ID in header
    trace_id = request.headers.get("x-trace-id")
    
    if not trace_id:
        # Generate new trace ID
        trace_id = new_trace_id()
    else:
        # Use existing trace ID from header
        set_trace_id(trace_id)
    
    # Process request
    response = await call_next(request)
    
    # Add trace ID to response headers
    response.headers["x-trace-id"] = trace_id or get_trace_id() or str(uuid.uuid4())
    
    # Add rate limit headers if applicable
    try:
        key = rate_limit_key(request)
        add_rate_limit_headers(response, limiter, request, key)
    except Exception:
        pass
    
    # Add compression if applicable
    try:
        # Check if client accepts gzip encoding
        accept_encoding = request.headers.get("accept-encoding", "")
        if "gzip" in accept_encoding.lower():
            # Compress response if it's large enough (> 1KB)
            if len(response.body) > 1024:
                compressed_body = gzip.compress(response.body)
                # Only use compression if it actually reduces size
                if len(compressed_body) < len(response.body):
                    response.body = compressed_body
                    response.headers["content-encoding"] = "gzip"
    except Exception:
        pass
    
    return response
app.include_router(health_router, prefix="/v1", tags=["Health"])
app.include_router(admin_backend_router, prefix="/v1/admin", tags=["Admin - Backend"])
app.include_router(admin_models_router, prefix="/v1/admin", tags=["Admin - Models"])
app.include_router(speaker_profiles_router, prefix="/v1/admin", tags=["Admin - Speaker Profiles"])
app.include_router(usage_router, prefix="/v1", tags=["Usage"])
app.include_router(models_router, prefix="/v1", tags=["Models"])

app.add_middleware(
    CORSMiddleware,
    allow_origins=list(get_allowed_origins()),
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def add_trace_id(request: Request, call_next):
    """
    Middleware to ensure trace ID is present in response headers.
    
    Reuses existing trace ID from request headers or generates a new one,
    then adds it to the response headers for distributed tracing.
    
    Args:
        request: FastAPI request object
        call_next: Next middleware or route handler in the chain
        
    Returns:
        FastAPI response object with X-Trace-Id header
    """
    trace_id = request.headers.get("x-trace-id")

    if trace_id:
        set_trace_id(trace_id)
    else:
        trace_id = new_trace_id()

    response = await call_next(request)
    response.headers["X-Trace-Id"] = get_trace_id() or trace_id

    return response


def now_iso() -> str:
    """
    Get current UTC timestamp in ISO 8601 format.
    
    Returns:
        Current UTC datetime as ISO 8601 formatted string
    """
    return datetime.now(timezone.utc).isoformat()


async def send_event(
    websocket: WebSocket,
    session_id: str,
    sequence: int,
    event: dict,
) -> None:
    """
    Send an event message through the WebSocket connection.
    
    Wraps the event with session metadata (session_id, sequence, created_at)
    and sends it as JSON text through the WebSocket.
    
    Args:
        websocket: WebSocket connection to send event through
        session_id: Unique session identifier
        sequence: Event sequence number for ordering
        event: Event data dictionary to send
    """
    payload = {
        "session_id": session_id,
        "sequence": sequence,
        "created_at": now_iso(),
        **event,
    }

    await websocket.send_text(json.dumps(payload))
    logger.debug(f"Sent event to session {session_id}: {event.get('type', 'unknown')}, sequence={sequence}")


async def send_error(
    websocket: WebSocket,
    session_id: str,
    sequence: int,
    code: str,
    message: str,
) -> None:
    """
    Send an error event through the WebSocket connection.
    
    Increments the error metrics counter and sends an error event
    with the specified code and message.
    
    Args:
        websocket: WebSocket connection to send error through
        session_id: Unique session identifier
        sequence: Event sequence number for ordering
        code: Error code string for categorization
        message: Human-readable error message
    """
    metrics.errors += 1
    logger.warning(f"Sending error to session {session_id}: code={code}, message={message}")
    await send_event(
        websocket,
        session_id,
        sequence,
        {
            "type": "error",
            "code": code,
            "message": message,
        },
    )


@app.get("/health")
async def health():
    """
    Basic health check endpoint returning service status and configuration.
    
    Returns current service status, audio configuration, connection counts,
    and authentication configuration without requiring authentication.
    
    Returns:
        JSONResponse with service status and configuration details
    """
    return JSONResponse(
        {
            "status": "ok",
            "app": settings.app_name,
            "sample_rate": settings.sample_rate,
            "channels": settings.channels,
            "frame_ms": settings.frame_ms,
            "active_connections": active_connections,
            "active_connections_by_key_label": active_connections_by_key_label,
            "max_active_connections": settings.max_active_connections,
            "max_connections_per_key": settings.max_connections_per_key,
            "auth": "api_key",
            "allowed_origins": sorted(get_allowed_origins()),
        }
    )


@app.get("/metrics")
async def get_metrics(authorization: str | None = Header(default=None)):
    """
    Prometheus metrics endpoint for monitoring.
    
    Returns Prometheus-formatted metrics text for monitoring systems.
    Requires valid API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        PlainTextResponse with Prometheus metrics in text format
        
    Raises:
        HTTPException: If API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key for metrics endpoint")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return PlainTextResponse(
        render_prometheus_metrics(
            active_connections=active_connections,
            max_active_connections=settings.max_active_connections,
            active_connections_by_key_label=active_connections_by_key_label,
        ),
        media_type="text/plain; version=0.0.4",
    )


@app.get("/v1/usage")
async def get_usage(authorization: str | None = Header(default=None)):
    """
    Get current usage statistics for the authenticated API key.
    
    Returns detailed usage metrics including connection counts, transcript
    counts, audio processing metrics, and estimated costs.
    Requires valid API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        JSONResponse with detailed usage statistics
        
    Raises:
        HTTPException: If API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key for usage endpoint")
        raise HTTPException(status_code=401, detail="Invalid API key")

    return JSONResponse(
        {
            "active_connections": active_connections,
            "active_connections_by_key_label": active_connections_by_key_label,
            "max_active_connections": settings.max_active_connections,
            "max_connections_per_key": settings.max_connections_per_key,
            "sessions_started": metrics.sessions_started,
            "sessions_closed": metrics.sessions_closed,
            "partial_transcripts": metrics.partial_transcripts,
            "final_transcripts": metrics.final_transcripts,
            "errors": metrics.errors,
            "audio_frames_received": metrics.audio_frames_received,
            "audio_bytes_received": metrics.audio_bytes_received,
            "estimated_audio_seconds": round(total_estimated_audio_seconds(), 3),
            "billing_rate_per_audio_hour": settings.billing_rate_per_audio_hour,
            "estimated_cost": estimated_cost(total_estimated_audio_seconds()),
            "by_key_label": usage_store.as_dict(),
        }
    )


@app.get("/v1/admin/health")
async def admin_health(authorization: str | None = Header(default=None)):
    """
    Admin health check endpoint with detailed system information.
    
    Returns comprehensive system status including model configuration,
    audio settings, connection limits, security settings, and usage statistics.
    Requires admin API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        JSONResponse with detailed system health and configuration
        
    Raises:
        HTTPException: If admin API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not settings.admin_api_key or api_key != settings.admin_api_key:
        logger.warning("Invalid admin API key for admin health endpoint")
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    return JSONResponse(
        {
            "status": "ok",
            "app": settings.app_name,
            "auth": "admin_api_key",
            "model": {
                "size": settings.whisper_model_size,
                "device": settings.whisper_device,
                "compute_type": settings.whisper_compute_type,
                "language": settings.transcription_language,
            },
            "audio": {
                "sample_rate": settings.sample_rate,
                "channels": settings.channels,
                "frame_ms": settings.frame_ms,
                "max_audio_frame_bytes": settings.max_audio_frame_bytes,
            },
            "limits": {
                "active_connections": active_connections,
                "active_connections_by_key_label": active_connections_by_key_label,
                "max_active_connections": settings.max_active_connections,
                "max_connections_per_key": settings.max_connections_per_key,
                "max_session_seconds": settings.max_session_seconds,
                "idle_timeout_seconds": settings.idle_timeout_seconds,
            },
            "security": {
                "allowed_origins": sorted(get_allowed_origins()),
                "admin_reset_enabled": settings.enable_admin_reset,
            },
            "usage": {
                "sessions_started": metrics.sessions_started,
                "sessions_closed": metrics.sessions_closed,
                "errors": metrics.errors,
                "estimated_audio_seconds": round(
                    sum(
                        counter.estimated_audio_seconds
                        for counter in usage_store.by_key_label.values()
                    ),
                    3,
                ),
                "estimated_cost": estimated_cost(
                    sum(
                        counter.estimated_audio_seconds
                        for counter in usage_store.by_key_label.values()
                    )
                ),
            },
        }
    )


@app.get("/v1/admin/audit")
async def export_admin_audit(authorization: str | None = Header(default=None)):
    """
    Export admin audit log as newline-delimited JSON (NDJSON).
    
    Returns the complete admin audit log for compliance and auditing purposes.
    Requires admin API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        Response with NDJSON content and Content-Disposition header
        
    Raises:
        HTTPException: If admin API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not settings.admin_api_key or api_key != settings.admin_api_key:
        logger.warning("Invalid admin API key for audit export")
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    if not ADMIN_AUDIT_LOG_PATH.exists():
        logger.debug("Admin audit log file does not exist, returning empty response")
        return Response(
            content="",
            media_type="application/x-ndjson",
            headers={
                "Content-Disposition": "attachment; filename=admin-audit.jsonl"
            },
        )

    logger.info("Exporting admin audit log")
    return Response(
        content=ADMIN_AUDIT_LOG_PATH.read_text(encoding="utf-8"),
        media_type="application/x-ndjson",
        headers={
            "Content-Disposition": "attachment; filename=admin-audit.jsonl"
        },
    )


@app.get("/v1/admin/audit.csv")
async def export_admin_audit_csv(authorization: str | None = Header(default=None)):
    """
    Export admin audit log as CSV format.
    
    Returns the complete admin audit log in CSV format for spreadsheet
    analysis and reporting. Requires admin API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        Response with CSV content and Content-Disposition header
        
    Raises:
        HTTPException: If admin API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not settings.admin_api_key or api_key != settings.admin_api_key:
        logger.warning("Invalid admin API key for audit CSV export")
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "created_at",
            "event_type",
            "admin_api_key_fingerprint",
            "source",
            "actor_uid",
        ]
    )

    if ADMIN_AUDIT_LOG_PATH.exists():
        line_count = 0
        for line in ADMIN_AUDIT_LOG_PATH.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue

            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                logger.debug(f"Skipping malformed audit log line")
                continue

            writer.writerow(
                [
                    item.get("created_at", ""),
                    item.get("event_type", ""),
                    item.get("admin_api_key_fingerprint", ""),
                    item.get("source", ""),
                    item.get("actor_uid", ""),
                ]
            )
            line_count += 1

        logger.info(f"Exported {line_count} audit log entries as CSV")

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=admin-audit.csv"
        },
    )


@app.post("/v1/usage/reset")
@limiter.limit("5/minute")
async def reset_usage(
    request: Request,
    authorization: str | None = Header(default=None),
):
    """
    Reset usage statistics for all API keys (admin only).
    
    Resets all usage counters and metrics to zero. This is a destructive
    operation that requires admin API key authentication and is rate-limited.
    Requires admin reset to be enabled in settings.
    
    Args:
        request: FastAPI request object
        authorization: Bearer token authorization header
        
    Returns:
        JSONResponse with reset status and updated usage data
        
    Raises:
        HTTPException: If usage reset is disabled (403) or admin API key is invalid (401)
    """
    if not settings.enable_admin_reset:
        logger.warning("Usage reset attempt when disabled")
        raise HTTPException(status_code=403, detail="Usage reset is disabled")

    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not settings.admin_api_key or api_key != settings.admin_api_key:
        logger.warning("Invalid admin API key for usage reset")
        raise HTTPException(status_code=401, detail="Invalid admin API key")

    logger.info("Resetting usage statistics")
    usage_store.reset()
    metrics.restore_from_usage_store()

    log_admin_event(
        "usage.reset",
        admin_api_key_fingerprint=api_key_fingerprint(api_key),
    )

    log_event(
        "usage.reset",
        admin_api_key_fingerprint=api_key_fingerprint(api_key),
    )

    return JSONResponse(
        {
            "status": "reset",
            "by_key_label": usage_store.as_dict(),
        }
    )


@app.get("/v1/usage/export")
async def export_usage(authorization: str | None = Header(default=None)):
    """
    Export usage statistics as JSON for download.
    
    Returns detailed usage statistics including connection counts,
    transcript counts, audio metrics, and estimated costs in JSON format.
    Requires valid API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        JSONResponse with usage data and Content-Disposition header for download
        
    Raises:
        HTTPException: If API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key for usage export")
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info("Exporting usage statistics as JSON")
    return JSONResponse(
        {
            "active_connections": active_connections,
            "active_connections_by_key_label": active_connections_by_key_label,
            "max_active_connections": settings.max_active_connections,
            "max_connections_per_key": settings.max_connections_per_key,
            "totals": {
                "sessions_started": metrics.sessions_started,
                "sessions_closed": metrics.sessions_closed,
                "partial_transcripts": metrics.partial_transcripts,
                "final_transcripts": metrics.final_transcripts,
                "errors": metrics.errors,
                "audio_frames_received": metrics.audio_frames_received,
                "audio_bytes_received": metrics.audio_bytes_received,
                "estimated_audio_seconds": round(total_estimated_audio_seconds(), 3),
                "billing_rate_per_audio_hour": settings.billing_rate_per_audio_hour,
                "estimated_cost": estimated_cost(total_estimated_audio_seconds()),
            },
            "by_key_label": usage_store.as_dict(),
        },
        headers={
            "Content-Disposition": "attachment; filename=stt-usage-export.json"
        },
    )


@app.get("/v1/usage/export.csv")
async def export_usage_csv(authorization: str | None = Header(default=None)):
    """
    Export usage statistics as CSV for spreadsheet analysis.
    
    Returns detailed usage statistics in CSV format with one row per API key,
    including session counts, transcript counts, audio metrics, and cost estimates.
    Requires valid API key authentication.
    
    Args:
        authorization: Bearer token authorization header
        
    Returns:
        Response with CSV content and Content-Disposition header for download
        
    Raises:
        HTTPException: If API key is invalid (401)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key for usage CSV export")
        raise HTTPException(status_code=401, detail="Invalid API key")

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(
        [
            "key_label",
            "sessions_started",
            "sessions_closed",
            "partial_transcripts",
            "final_transcripts",
            "errors",
            "audio_frames_received",
            "audio_bytes_received",
            "estimated_audio_seconds",
            "billing_rate_per_audio_hour",
            "estimated_cost",
        ]
    )

    key_count = 0
    for key_label, counter in sorted(usage_store.by_key_label.items()):
        writer.writerow(
            [
                key_label,
                counter.sessions_started,
                counter.sessions_closed,
                counter.partial_transcripts,
                counter.final_transcripts,
                counter.errors,
                counter.audio_frames_received,
                counter.audio_bytes_received,
                round(counter.estimated_audio_seconds, 3),
                settings.billing_rate_per_audio_hour,
                estimated_cost(counter.estimated_audio_seconds),
            ]
        )
        key_count += 1

    logger.info(f"Exported usage statistics for {key_count} API keys as CSV")

    return Response(
        content=output.getvalue(),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=stt-usage-export.csv"
        },
    )


@app.post("/v1/audio/transcriptions")
@limiter.limit("30/minute")
async def create_transcription(
    request: Request,
    file: UploadFile = File(...),
    model: str | None = Form(default=None),
    language: str | None = Form(default=None),
    hotwords: str | None = Form(default=None),
    initial_prompt: str | None = Form(default=None),
    beam_size: int | None = Form(default=None),
    word_timestamps: bool | None = Form(default=None),
    temperature: float | None = Form(default=None),
    authorization: str | None = Header(default=None),
):
    """
    Transcribe an audio file using the STT service.
    
    Accepts an audio file upload and returns the transcribed text. Supports
    model selection (admin only), language specification, and various decoder
    options like hotwords, beam size, and word timestamps.
    
    Args:
        request: FastAPI request object
        file: Audio file to transcribe (multipart/form-data)
        model: Model ID to use for transcription (admin only, overrides tenant default)
        language: Language code for transcription (e.g., "en", "es")
        hotwords: Comma-separated list of hotwords to bias transcription
        initial_prompt: Initial prompt text to guide transcription
        beam_size: Beam search size for decoding
        word_timestamps: Whether to include word-level timestamps in output
        temperature: Sampling temperature for decoder
        authorization: Bearer token authorization header
        
    Returns:
        JSONResponse with transcribed text, model used, and language
        
    Raises:
        HTTPException: If API key is invalid (401) or model override is unauthorized (403)
    """
    api_key = authorization.replace("Bearer ", "", 1) if authorization else None

    if not is_valid_api_key(api_key):
        logger.warning("Invalid API key for transcription endpoint")
        raise HTTPException(status_code=401, detail="Invalid API key")

    logger.info(f"Transcription request for file: {file.filename}, model: {model}")

    selected_model_id = validate_model_id(model or settings.whisper_model_size)

    decoder_options = build_decoder_options(
        hotwords=hotwords,
        initial_prompt=initial_prompt,
        beam_size=beam_size,
        word_timestamps=word_timestamps,
        temperature=temperature,
    )
    suffix = Path(file.filename or "audio.wav").suffix or ".wav"
    tmp_path: Path | None = None

    try:
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
            tmp.write(await file.read())
            tmp.flush()
            tmp_path = Path(tmp.name)

        logger.debug(f"Transcribing file: {tmp_path} with model: {selected_model_id}")
        text = transcribe_pcm16_file(
            str(tmp_path),
            language_override=language,
            **decoder_options,
        )
        logger.info(f"Transcription completed: {len(text)} characters")
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    return JSONResponse(
        {
            "text": text,
            "model": selected_model_id,
            "language": language or settings.transcription_language,
        }
    )


@app.websocket("/stt/stream")
async def stt_stream(
    websocket: WebSocket,
    hotwords: str | None = None,
    initial_prompt: str | None = None,
    beam_size: int | None = None,
    word_timestamps: bool | None = None,
    temperature: float | None = None,
    model: str | None = None,
):
    """
    WebSocket endpoint for real-time streaming speech-to-text.
    
    Accepts PCM16 audio frames and returns partial and final transcripts in real-time.
    Supports VAD-based speech detection, session timeout handling, and model selection.
    
    Connection requirements:
    - Valid API key via query parameter
    - Allowed origin per CORS configuration
    - Connection limits (global and per-key)
    
    Message format:
    - Binary frames: PCM16 audio bytes (sample_rate, channels, encoding sent in session.started)
    - Text frames: JSON control messages (e.g., {"type": "flush"})
    
    Args:
        websocket: WebSocket connection object
        hotwords: Comma-separated list of hotwords to bias transcription
        initial_prompt: Initial prompt text to guide transcription
        beam_size: Beam search size for decoding
        word_timestamps: Whether to include word-level timestamps in output
        temperature: Sampling temperature for decoder
        model: Model ID to use for transcription (admin only, overrides tenant default)
        
    Events sent:
    - session.started: Session initialization with audio format details
    - transcript.partial: Interim transcription result
    - transcript.final: Final transcription result for speech segment
    - session.flushed: Response to flush control message
    - error: Error event with code and message
        
    Raises:
        WebSocketDisconnect: If client disconnects
        WebSocketException: For policy violations (invalid model, etc.)
    """
    global active_connections

    trace_id = new_trace_id()
    origin = websocket.headers.get("origin")
    api_key = websocket.query_params.get("api_key")
    language = websocket.query_params.get("language")
    decoder_options = build_decoder_options(
        hotwords=hotwords,
        initial_prompt=initial_prompt,
        beam_size=beam_size,
        word_timestamps=word_timestamps,
        temperature=temperature,
    )

    if not is_allowed_websocket_origin(origin):
        logger.warning(f"WebSocket connection rejected: origin not allowed: {origin}")
        await websocket.close(code=1008, reason="Origin not allowed")
        return

    if not is_valid_api_key(api_key):
        logger.warning("WebSocket connection rejected: invalid API key")
        await websocket.close(code=1008, reason="Invalid API key")
        return

    key_label = api_key_label(api_key)
    current_key_connections = active_connections_by_key_label.get(key_label, 0)

    if active_connections >= settings.max_active_connections:
        logger.warning(f"WebSocket connection rejected: too many active connections ({active_connections})")
        await websocket.close(code=1013, reason="Too many active connections")
        return

    if current_key_connections >= settings.max_connections_per_key:
        logger.warning(f"WebSocket connection rejected: too many connections for key {key_label} ({current_key_connections})")
        await websocket.close(code=1013, reason="Too many active connections for this API key")
        return

    await websocket.accept()
    active_connections += 1
    active_connections_by_key_label[key_label] = current_key_connections + 1
    logger.info(f"WebSocket connection accepted: key_label={key_label}, active_connections={active_connections}")
    log_event(
        "session.accepted",
        active_connections=active_connections,
        api_key_label=key_label,
        key_active_connections=active_connections_by_key_label[key_label],
    )

    session_id = str(uuid.uuid4())
    key_usage = usage_store.get(key_label)
    sequence = 0
    session_started_at = time.monotonic()
    
    try:
        selected_model_id = validate_model_id(model or settings.whisper_model_size)
    except ValueError as exc:
        raise WebSocketException(
            code=status.WS_1008_POLICY_VIOLATION,
            reason=str(exc),
        )
    
    session = StreamingTranscriptionSession(
        language=language,
        decoder_options=decoder_options,
        model_id=selected_model_id,
    )
    metrics.sessions_started += 1
    key_usage.sessions_started += 1
    log_event(
        "session.started",
        session_id=session_id,
        language=language or settings.transcription_language,
        api_key_fingerprint=api_key_fingerprint(api_key),
        api_key_label=key_label,
    )

    await send_event(
        websocket,
        session_id,
        sequence,
        {
            "type": "session.started",
            "sample_rate": settings.sample_rate,
            "channels": settings.channels,
            "encoding": "pcm_s16le",
            "language": language or settings.transcription_language,
            "trace_id": trace_id,
        },
    )
    sequence += 1

    try:
        while True:
            if time.monotonic() - session_started_at > settings.max_session_seconds:
                await send_error(
                    websocket,
                    session_id,
                    sequence,
                    "max_session_duration_exceeded",
                    "Maximum session duration exceeded.",
                )
                sequence += 1
                await websocket.close(code=1000, reason="Maximum session duration exceeded")
                break

            try:
                message = await asyncio.wait_for(
                    websocket.receive(),
                    timeout=settings.idle_timeout_seconds,
                )
            except asyncio.TimeoutError:
                await send_error(
                    websocket,
                    session_id,
                    sequence,
                    "idle_timeout",
                    "No audio or control messages received before idle timeout.",
                )
                sequence += 1
                await websocket.close(code=1000, reason="Idle timeout")
                break

            if "bytes" in message and message["bytes"] is not None:
                pcm16_audio = message["bytes"]

                if not pcm16_audio:
                    await send_error(
                        websocket,
                        session_id,
                        sequence,
                        "empty_audio_frame",
                        "Received an empty audio frame.",
                    )
                    sequence += 1
                    continue

                if len(pcm16_audio) > settings.max_audio_frame_bytes:
                    await send_error(
                        websocket,
                        session_id,
                        sequence,
                        "audio_frame_too_large",
                        "Audio frame exceeds the configured maximum size.",
                    )
                    sequence += 1
                    continue

                # Frame is accepted — credit it to metrics and per-key usage.
                metrics.audio_frames_received += 1
                metrics.audio_bytes_received += len(pcm16_audio)
                key_usage.audio_frames_received += 1
                key_usage.audio_bytes_received += len(pcm16_audio)
                key_usage.add_audio_bytes(len(pcm16_audio))

                async for event in session.receive_audio(pcm16_audio):
                    await send_event(
                        websocket,
                        session_id,
                        sequence,
                        {
                            "type": event.type,
                            "text": event.text,
                        },
                    )
                    if event.type == "transcript.partial":
                        metrics.partial_transcripts += 1
                        key_usage.partial_transcripts += 1
                    elif event.type == "transcript.final":
                        metrics.final_transcripts += 1
                        key_usage.final_transcripts += 1

                    log_event(
                        event.type,
                        session_id=session_id,
                        sequence=sequence,
                        text_length=len(event.text),
                    )
                    sequence += 1

            elif "text" in message and message["text"] is not None:
                try:
                    data = json.loads(message["text"])
                except json.JSONDecodeError:
                    await send_error(
                        websocket,
                        session_id,
                        sequence,
                        "invalid_json",
                        "Text frames must be valid JSON.",
                    )
                    sequence += 1
                    continue

                event_type = data.get("type")

                if event_type == "flush":
                    async for event in session.flush():
                        await send_event(
                            websocket,
                            session_id,
                            sequence,
                            {
                                "type": event.type,
                                "text": event.text,
                            },
                        )
                        sequence += 1

                    await send_event(
                        websocket,
                        session_id,
                        sequence,
                        {"type": "session.flushed"},
                    )
                    sequence += 1

                else:
                    await send_error(
                        websocket,
                        session_id,
                        sequence,
                        "unknown_event_type",
                        "Supported text event types: flush.",
                    )
                    sequence += 1

            else:
                await send_error(
                    websocket,
                    session_id,
                    sequence,
                    "unsupported_frame",
                    "Send binary PCM audio frames or JSON text control frames.",
                )
                sequence += 1

    except WebSocketDisconnect:
        log_event("session.disconnected", session_id=session_id)

    except Exception as exc:
        metrics.errors += 1
        key_usage.errors += 1
        log_event(
            "session.exception",
            session_id=session_id,
            error_type=type(exc).__name__,
            error_message=str(exc),
        )

        try:
            await send_error(
                websocket,
                session_id,
                sequence,
                "internal_error",
                "An internal server error occurred.",
            )
        except Exception:
            pass

    finally:
        try:
            async for event in session.flush():
                log_event(
                    "session.final_flush",
                    session_id=session_id,
                    text_length=len(event.text),
                )
        except Exception as exc:
            log_event(
                "session.final_flush_failed",
                session_id=session_id,
                error_type=type(exc).__name__,
                error_message=str(exc),
            )

        active_connections = max(0, active_connections - 1)
        active_connections_by_key_label[key_label] = max(
            0,
            active_connections_by_key_label.get(key_label, 0) - 1,
        )
        metrics.sessions_closed += 1
        key_usage.sessions_closed += 1
        usage_store.save()
        log_event(
            "session.closed",
            session_id=session_id,
            active_connections=active_connections,
            api_key_label=key_label,
            key_active_connections=active_connections_by_key_label[key_label],
        )
