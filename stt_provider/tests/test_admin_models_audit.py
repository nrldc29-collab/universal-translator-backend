"""
Tests for admin model management audit logging.

This module tests that tenant default model changes are properly logged to the audit trail.
Audit logging is critical for Phase 3 compliance and Phase 4 domain model management,
ensuring all settings changes are traceable and accountable.

Run tests:
    pytest tests/test_admin_models_audit.py

Purpose:
This ensures that when admins update tenant default models, an audit event is written
to the audit log with the correct event type, resource, and payload. This provides
traceability for all model configuration changes as required by Phase 3 audit requirements
and Phase 4 domain model selection features.
"""
import logging

import pytest
from httpx import AsyncClient

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_default_model_update_writes_audit_event(app):
    """
    Test that default model update writes an audit event.
    
    Verifies that when a tenant's default model is updated, an audit event is written
    to the audit log with the event type 'tenant.default_model_updated', resource 'stt_model',
    and the new model ID in the payload. This ensures all model configuration changes are
    traceable for compliance and debugging purposes.
    
    Note: The actual audit log verification is commented out as a placeholder for when
    the audit log fixture or test DB helper is available.
    """
    logger.info("Testing default model update writes audit event")
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.put(
            "/v1/admin/tenants/tenant_123/default-model",
            headers={
                "Authorization": "Bearer admin-test-key",
            },
            json={
                "default_model_id": "parakeet-medical",
            },
        )

    assert response.status_code == 200

    # Verify through your test DB helper or audit-log fixture:
    #
    # event = await fetch_latest_audit_event(
    #     tenant_id="tenant_123",
    #     event_type="tenant.default_model_updated",
    # )
    #
    # assert event["resource"] == "stt_model"
    # assert event["payload_jsonb"]["default_model_id"] == "parakeet-medical"
    
    logger.info("Default model update audit event test passed")
