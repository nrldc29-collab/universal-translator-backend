"""
Tests for backend fallback functionality.

This module tests the backend fallback decision logic which determines whether
to use Triton or Whisper as the transcription backend based on tenant configuration,
backend availability, and health status. Tests verify fallback triggering when
Triton is unavailable or unhealthy, respect of fallback settings, and proper
dataclass behavior.

Run tests:
    pytest server/tests/test_backend_fallback.py

Purpose:
This ensures that the backend fallback system correctly routes transcription
requests to appropriate backends based on health and configuration, providing
graceful degradation when the primary backend fails.
"""
import logging

import pytest

from stt_server.backend_fallback import (
    decide_backend,
    FallbackDecision,
    BackendStatus,
)

logger = logging.getLogger(__name__)


def test_decide_backend_uses_titon_when_available():
    """
    Test that Triton is used when available and configured.
    
    Verifies that when Triton is the configured backend and is available
    and healthy, it is selected without triggering fallback.
    """
    logger.info("Testing Triton usage when available and configured")
    
    tenant = {
        "backend": "triton",
        "allow_backend_fallback": True,
    }
    
    triton_status = BackendStatus(
        available=True,
        healthy=True,
        last_check="2024-01-01T00:00:00Z",
    )
    
    decision = decide_backend(
        tenant=tenant,
        triton_status=triton_status,
    )
    
    assert decision.backend == "triton"
    assert decision.fallback_triggered is False
    assert decision.reason is None
    
    logger.info("Triton usage when available test passed")


def test_decide_backend_falls_back_to_whisper_when_triton_unavailable():
    """
    Test fallback to Whisper when Triton is unavailable.
    
    Verifies that when Triton is configured but unavailable, the system
    falls back to Whisper if fallback is enabled.
    """
    logger.info("Testing fallback to Whisper when Triton unavailable")
    
    tenant = {
        "backend": "triton",
        "allow_backend_fallback": True,
    }
    
    triton_status = BackendStatus(
        available=False,
        healthy=False,
        last_check="2024-01-01T00:00:00Z",
    )
    
    decision = decide_backend(
        tenant=tenant,
        triton_status=triton_status,
    )
    
    assert decision.backend == "whisper"
    assert decision.fallback_triggered is True
    assert decision.reason == "triton_unavailable"
    
    logger.info("Fallback to Whisper when Triton unavailable test passed")


def test_decide_backend_no_fallback_when_disabled():
    """
    Test that fallback is not triggered when disabled.
    
    Verifies that when fallback is disabled for a tenant, the system
    keeps the configured backend even if it's unavailable.
    """
    logger.info("Testing no fallback when disabled")
    
    tenant = {
        "backend": "triton",
        "allow_backend_fallback": False,
    }
    
    triton_status = BackendStatus(
        available=False,
        healthy=False,
        last_check="2024-01-01T00:00:00Z",
    )
    
    decision = decide_backend(
        tenant=tenant,
        triton_status=triton_status,
    )
    
    assert decision.backend == "triton"
    assert decision.fallback_triggered is False
    assert decision.reason == "fallback_disabled"
    
    logger.info("No fallback when disabled test passed")


def test_decide_backend_uses_whisper_when_configured():
    """
    Test that Whisper is used when explicitly configured.
    
    Verifies that when Whisper is the configured backend, it is used
    regardless of Triton's status.
    """
    logger.info("Testing Whisper usage when explicitly configured")
    
    tenant = {
        "backend": "whisper",
        "allow_backend_fallback": True,
    }
    
    triton_status = BackendStatus(
        available=True,
        healthy=True,
        last_check="2024-01-01T00:00:00Z",
    )
    
    decision = decide_backend(
        tenant=tenant,
        triton_status=triton_status,
    )
    
    assert decision.backend == "whisper"
    assert decision.fallback_triggered is False
    
    logger.info("Whisper usage when configured test passed")


def test_decide_backend_falls_back_when_triton_unhealthy():
    """
    Test fallback when Triton is available but unhealthy.
    
    Verifies that when Triton is available but marked unhealthy,
    the system falls back to Whisper if fallback is enabled.
    """
    logger.info("Testing fallback when Triton unhealthy")
    
    tenant = {
        "backend": "triton",
        "allow_backend_fallback": True,
    }
    
    triton_status = BackendStatus(
        available=True,
        healthy=False,
        last_check="2024-01-01T00:00:00Z",
    )
    
    decision = decide_backend(
        tenant=tenant,
        triton_status=triton_status,
    )
    
    assert decision.backend == "whisper"
    assert decision.fallback_triggered is True
    assert decision.reason == "triton_unhealthy"
    
    logger.info("Fallback when Triton unhealthy test passed")


def test_backend_status_dataclass():
    """
    Test BackendStatus dataclass.
    
    Verifies that the BackendStatus dataclass correctly stores
    availability, health, and last check timestamp.
    """
    logger.info("Testing BackendStatus dataclass")
    
    status = BackendStatus(
        available=True,
        healthy=True,
        last_check="2024-01-01T00:00:00Z",
    )
    
    assert status.available is True
    assert status.healthy is True
    assert status.last_check == "2024-01-01T00:00:00Z"
    
    logger.info("BackendStatus dataclass test passed")


def test_fallback_decision_dataclass():
    """
    Test FallbackDecision dataclass.
    
    Verifies that the FallbackDecision dataclass correctly stores
    the selected backend, fallback trigger status, and reason.
    """
    logger.info("Testing FallbackDecision dataclass")
    
    decision = FallbackDecision(
        backend="whisper",
        fallback_triggered=True,
        reason="triton_unavailable",
    )
    
    assert decision.backend == "whisper"
    assert decision.fallback_triggered is True
    assert decision.reason == "triton_unavailable"
    
    logger.info("FallbackDecision dataclass test passed")
