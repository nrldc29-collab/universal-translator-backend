"""
Model override audit module for transcription model tracking.

This module provides functionality for auditing when a transcription request
uses a model override instead of the tenant's default model. This supports
compliance and monitoring of model usage patterns across the system.
"""
import logging

from stt_server.audit import write_audit_event

logger = logging.getLogger(__name__)


async def audit_model_override(
    db,
    *,
    tenant_id: str,
    actor_id: str,
    default_model_id: str,
    override_model_id: str,
    request_type: str,
) -> None:
    """
    Audit a model override event for compliance tracking.
    
    Records an audit event when a transcription request uses a model override
    instead of the tenant's configured default model. This provides visibility
    into model usage patterns and supports compliance requirements.
    
    Args:
        db: Database connection for audit logging
        tenant_id: Tenant identifier for the request
        actor_id: User or system identifier initiating the request
        default_model_id: The tenant's configured default model ID
        override_model_id: The model ID used for this request override
        request_type: Type of request (e.g., "streaming", "batch", "admin")
    """
    logger.info(
        f"Model override audit for tenant {tenant_id}: "
        f"default={default_model_id}, override={override_model_id}, "
        f"type={request_type}, actor={actor_id}"
    )
    
    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type="tenant.model_override_used",
        resource="stt_model",
        payload={
            "default_model_id": default_model_id,
            "override_model_id": override_model_id,
            "request_type": request_type,
        },
    )
    
    logger.debug(
        f"Successfully audited model override for tenant {tenant_id}"
    )
