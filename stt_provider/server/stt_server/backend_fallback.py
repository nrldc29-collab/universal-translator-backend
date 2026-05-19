"""
Backend fallback module for transcription service resilience.

This module provides functionality for selecting a healthy transcription backend
with automatic fallback from Triton to Whisper when Triton is unhealthy or the
circuit breaker is open. Includes audit logging for fallback events.
"""
import logging
from typing import Union

from stt_server.audit import write_audit_event
from stt_server.backend_routing import BackendName, TenantBackendConfig
from stt_server.backends.triton import TritonStreamingClient
from stt_server.model import WhisperModel
from stt_server.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    get_circuit_breaker,
)

logger = logging.getLogger(__name__)


# Circuit breaker for Triton backend
_triton_circuit_breaker = get_circuit_breaker(
    "triton_backend",
    CircuitBreakerConfig(
        failure_threshold=3,
        recovery_timeout=30.0,
    ),
)


async def select_healthy_backend(
    *,
    db,
    tenant_backend: TenantBackendConfig,
    triton: TritonStreamingClient,
) -> Union[TritonStreamingClient, WhisperModel]:
    """
    Select a healthy backend for streaming transcription.
    
    Evaluates the tenant's configured backend preference and checks Triton health
    using circuit breaker protection. Falls back to Whisper if Triton is unhealthy
    and fallback is allowed, otherwise raises an error.
    
    Args:
        db: Database connection for audit logging
        tenant_backend: Tenant backend configuration with preferred backend and fallback settings
        triton: Triton streaming client instance
        
    Returns:
        Either TritonStreamingClient if healthy, or WhisperModel as fallback
        
    Raises:
        RuntimeError: If Triton is unhealthy and fallback is not allowed
    """
    logger.info(
        "Selecting backend for tenant",
        extra={
            "tenant_id": tenant_backend.tenant_id,
            "requested_backend": tenant_backend.backend,
            "fallback_allowed": tenant_backend.allow_fallback,
        },
    )
    
    if tenant_backend.backend == BackendName.WHISPER:
        logger.info(
            "Using Whisper backend as configured",
            extra={"tenant_id": tenant_backend.tenant_id},
        )
        return WhisperModel()

    try:
        # Use circuit breaker for Triton calls
        logger.debug(
            "Checking Triton backend health",
            extra={"tenant_id": tenant_backend.tenant_id},
        )
        is_ready = await _triton_circuit_breaker.call(triton.is_ready)
        
        if is_ready:
            logger.info(
                "Triton backend is healthy, using Triton",
                extra={"tenant_id": tenant_backend.tenant_id},
            )
            return triton
    except CircuitBreakerOpenError:
        logger.warning(
            "Triton circuit breaker is open, falling back to Whisper",
            extra={
                "tenant_id": tenant_backend.tenant_id,
                "circuit_breaker": "triton_backend",
            },
        )
    except Exception as e:
        logger.warning(
            f"Triton health check failed: {e}",
            extra={
                "tenant_id": tenant_backend.tenant_id,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

    if tenant_backend.allow_fallback:
        logger.warning(
            "Triton backend is unhealthy; falling back to Whisper",
            extra={
                "tenant_id": tenant_backend.tenant_id,
                "requested_backend": tenant_backend.backend,
                "fallback_backend": BackendName.WHISPER,
            },
        )

        await write_audit_event(
            db,
            tenant_id=tenant_backend.tenant_id,
            actor_id=None,
            event_type="tenant.backend_fallback",
            resource="stt_backend",
            payload={
                "from_backend": "triton",
                "to_backend": "whisper",
                "reason": "triton_unhealthy",
            },
        )

        logger.info(
            "Successfully fell back to Whisper backend",
            extra={"tenant_id": tenant_backend.tenant_id},
        )
        return WhisperModel()

    await write_audit_event(
        db,
        tenant_id=tenant_backend.tenant_id,
        actor_id=None,
        event_type="tenant.backend_unavailable",
        resource="stt_backend",
        payload={
            "backend": "triton",
            "fallback_allowed": False,
            "reason": "triton_unhealthy",
        },
    )

    logger.error(
        "Triton backend is unhealthy and fallback is disabled",
        extra={"tenant_id": tenant_backend.tenant_id},
    )

    raise RuntimeError(
        f"Triton backend is unhealthy and fallback is disabled for tenant {tenant_backend.tenant_id}"
    )
