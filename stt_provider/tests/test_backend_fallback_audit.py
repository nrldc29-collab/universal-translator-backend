"""
Tests for backend fallback audit logging.

This module tests that backend fallback and unavailability events are properly logged to the audit trail.
Audit logging is critical for enterprise compliance and traceability during the self-hosted Triton rollout,
ensuring all backend selection decisions and fallback behavior are recorded.

Run tests:
    pytest tests/test_backend_fallback_audit.py

Purpose:
This ensures that when the system falls back from Triton to Whisper or when a backend is unavailable,
appropriate audit events are written to the audit log. This provides traceability for all backend routing
decisions and supports enterprise auditability requirements during the Phase 2B rollout.
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
    Fake database for testing audit event logging.
    
    Records executed queries and their arguments for verification.
    """
    def __init__(self):
        """Initialize the fake database with an empty event list."""
        self.events = []

    async def execute(self, query, *args):
        """
        Record a database query execution.
        
        Args:
            query: The SQL query that would be executed.
            *args: Arguments passed to the query.
        """
        self.events.append(
            {
                "query": query,
                "args": args,
            }
        )
        return None


@pytest.mark.asyncio
async def test_audit_event_written_when_falling_back_to_whisper():
    """
    Test that audit event is written when falling back to Whisper.
    
    Verifies that when Triton is not ready and fallback is allowed, the system
    falls back to Whisper and writes a 'tenant.backend_fallback' audit event to the database.
    """
    logger.info("Testing audit event written when falling back to Whisper")
    
    db = FakeDb()

    tenant_backend = TenantBackendConfig(
        tenant_id="tenant_123",
        backend=BackendName.TRITON,
        allow_fallback=True,
    )

    triton = FakeTritonClient(ready=False)

    backend = await select_healthy_backend(
        db=db,
        tenant_backend=tenant_backend,
        triton=triton,
    )

    assert isinstance(backend, WhisperModel)
    assert len(db.events) == 1
    assert "tenant.backend_fallback" in str(db.events[0]["args"])
    
    logger.info("Fallback audit event test passed")


@pytest.mark.asyncio
async def test_audit_event_written_when_backend_unavailable_without_fallback():
    """
    Test that audit event is written when backend is unavailable without fallback.
    
    Verifies that when Triton is not ready and fallback is not allowed, the system
    raises a RuntimeError and writes a 'tenant.backend_unavailable' audit event to the database.
    """
    logger.info("Testing audit event written when backend unavailable without fallback")
    
    db = FakeDb()

    tenant_backend = TenantBackendConfig(
        tenant_id="tenant_123",
        backend=BackendName.TRITON,
        allow_fallback=False,
    )

    triton = FakeTritonClient(ready=False)

    with pytest.raises(RuntimeError):
        await select_healthy_backend(
            db=db,
            tenant_backend=tenant_backend,
            triton=triton,
        )

    assert len(db.events) == 1
    assert "tenant.backend_unavailable" in str(db.events[0]["args"])
    
    logger.info("Backend unavailable audit event test passed")
