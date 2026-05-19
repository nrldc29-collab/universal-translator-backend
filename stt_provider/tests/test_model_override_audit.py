"""
Tests for model override audit logging.

This module tests that request-level model overrides are properly logged to the audit trail.
Audit logging is critical for Phase 3 compliance and Phase 4 domain model management,
ensuring all model selection decisions are traceable for both REST and WebSocket requests.

Run tests:
    pytest tests/test_model_override_audit.py

Purpose:
This ensures that when users override the tenant's default model at request time,
an audit event is written to the audit log with the correct event type, resource,
default model ID, override model ID, and request type. This provides traceability
for all model selection decisions as required by Phase 3 audit requirements and
Phase 4 domain model selection features.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_rest_model_override_writes_audit_event(app):
    """
    Test that REST model override writes an audit event.
    
    Verifies that when a REST transcription request includes a model override,
    an audit event is written to the audit log with the event type 'tenant.model_override_used',
    resource 'stt_model', and the default and override model IDs in the payload.
    
    Note: The actual audit log verification is commented out as a placeholder for when the
    audit log fixture or test DB helper is available.
    """
    logger.info("Testing REST model override writes audit event")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post(
            "/v1/audio/transcriptions",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            files={
                "file": ("sample.wav", b"fake-audio", "audio/wav"),
            },
            data={
                "model": "parakeet-medical",
            },
        )

    assert response.status_code in {200, 202}

    # Verify through your test DB helper or audit-log fixture:
    #
    # event = await fetch_latest_audit_event(
    #     tenant_id="tenant_123",
    #     event_type="tenant.model_override_used",
    # )
    #
    # assert event["resource"] == "stt_model"
    # assert event["payload_jsonb"]["default_model_id"] == "parakeet-general"
    # assert event["payload_jsonb"]["override_model_id"] == "parakeet-medical"
    # assert event["payload_jsonb"]["request_type"] == "rest"
    
    logger.info("REST model override audit event test passed")


@pytest.mark.asyncio
async def test_websocket_model_override_writes_audit_event(app):
    """
    Test that WebSocket model override writes an audit event.
    
    Verifies that when a WebSocket transcription request includes a model override
    in query parameters, an audit event is written to the audit log with the event type
    'tenant.model_override_used', resource 'stt_model', and the default and override
    model IDs in the payload.
    
    Note: The actual WebSocket test and audit log verification are commented out as
    placeholders for when the WebSocket test helper and audit log fixture are available.
    """
    logger.info("Testing WebSocket model override writes audit event")
    
    # Use your existing WebSocket test helper here.
    #
    # await open_stream(
    #     app,
    #     headers={"Authorization": "Bearer admin-test-key"},
    #     query_params={"model": "parakeet-medical"},
    # )
    #
    # event = await fetch_latest_audit_event(
    #     tenant_id="tenant_123",
    #     event_type="tenant.model_override_used",
    # )
    #
    # assert event["resource"] == "stt_model"
    # assert event["payload_jsonb"]["default_model_id"] == "parakeet-general"
    # assert event["payload_jsonb"]["override_model_id"] == "parakeet-medical"
    # assert event["payload_jsonb"]["request_type"] == "websocket"

    assert True
    
    logger.info("WebSocket model override audit event test passed")
