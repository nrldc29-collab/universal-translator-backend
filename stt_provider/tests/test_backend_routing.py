"""
Tests for backend routing logic.

This module tests the tenant-level backend routing behavior for the Phase 2B rollout.
Tests verify that the system uses Triton when healthy, falls back to Whisper when allowed,
and fails closed when fallback is disabled, ensuring safe rollout behavior.

Run tests:
    pytest tests/test_backend_routing.py

Purpose:
This ensures that the backend selection logic correctly routes requests based on backend health
and tenant configuration, providing the foundation for safe Phase 2B Triton rollout with optional
fallback to Whisper for resilience.
"""
import logging

import pytest

from stt_server.backend_fallback import select_healthy_backend
from stt_server.backend_routing import BackendName, TenantBackendConfig
from stt_server.model import WhisperModel

logger = logging.getLogger(__name__)


class FakeTritonClient:
    """
    Fake Triton client for testing.
    
    Simulates a Triton client with configurable readiness state.
    """
    def __init__(self, ready: bool):
        """
        Initialize the fake Triton client.
        
        Args:
            ready: Whether the Triton client is ready to serve requests.
        """
        self.ready = ready

    def is_ready(self) -> bool:
        """
        Check if the Triton client is ready.
        
        Returns:
            The configured readiness state.
        """
        return self.ready


class FakeDb:
    """
    Fake database for testing.
    
    Provides a no-op execute method for database operations.
    """
    async def execute(self, *args, **kwargs):
        """
        No-op database execute method.
        
        Args:
            *args: Query arguments.
            **kwargs: Query keyword arguments.
        """
        return None


@pytest.mark.asyncio
async def test_uses_triton_when_triton_is_ready():
    """
    Test that Triton is used when it is ready.
    
    Verifies that when Triton is healthy and the tenant is configured to use Triton,
    the routing logic selects Triton as the backend.
    """
    logger.info("Testing Triton is used when Triton is ready")
    
    tenant_backend = TenantBackendConfig(
        tenant_id="tenant_123",
        backend=BackendName.TRITON,
        allow_fallback=True,
    )

    triton = FakeTritonClient(ready=True)

    backend = await select_healthy_backend(
        db=FakeDb(),
        tenant_backend=tenant_backend,
        triton=triton,
    )

    assert backend is triton
    
    logger.info("Triton ready test passed")


@pytest.mark.asyncio
async def test_falls_back_to_whisper_when_triton_is_unhealthy_and_fallback_allowed():
    """
    Test that fallback to Whisper occurs when Triton is unhealthy and fallback is allowed.
    
    Verifies that when Triton is not ready but the tenant has fallback enabled,
    the routing logic falls back to Whisper to maintain service availability.
    """
    logger.info("Testing fallback to Whisper when Triton unhealthy and fallback allowed")
    
    tenant_backend = TenantBackendConfig(
        tenant_id="tenant_123",
        backend=BackendName.TRITON,
        allow_fallback=True,
    )

    triton = FakeTritonClient(ready=False)

    backend = await select_healthy_backend(
        db=FakeDb(),
        tenant_backend=tenant_backend,
        triton=triton,
    )

    assert isinstance(backend, WhisperModel)
    
    logger.info("Fallback to Whisper test passed")


@pytest.mark.asyncio
async def test_raises_when_triton_is_unhealthy_and_fallback_disabled():
    """
    Test that an error is raised when Triton is unhealthy and fallback is disabled.
    
    Verifies that when Triton is not ready and the tenant has fallback disabled,
    the routing logic raises a RuntimeError to fail closed and prevent using
    an unavailable backend.
    """
    logger.info("Testing error raised when Triton unhealthy and fallback disabled")
    
    tenant_backend = TenantBackendConfig(
        tenant_id="tenant_123",
        backend=BackendName.TRITON,
        allow_fallback=False,
    )

    triton = FakeTritonClient(ready=False)

    with pytest.raises(RuntimeError):
        await select_healthy_backend(
            db=FakeDb(),
            tenant_backend=tenant_backend,
            triton=triton,
        )
    
    logger.info("Fail closed test passed")
