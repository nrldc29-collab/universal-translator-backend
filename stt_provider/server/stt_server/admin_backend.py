"""
Admin backend API module for tenant backend configuration.

This module provides a FastAPI router for administrators to update tenant backend
configurations, allowing controlled migration between Triton and Whisper backends
with support for fallback settings and default model selection.
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from stt_server.audit import write_audit_event
from stt_server.model_registry import validate_model_id
from stt_server.rbac import Scope, require_scope

logger = logging.getLogger(__name__)

router = APIRouter()


class TenantBackendUpdate(BaseModel):
    """
    Request body for updating tenant backend configuration.
    
    Attributes:
        backend: Backend to use (triton or whisper)
        allow_backend_fallback: Whether to allow fallback to Whisper if Triton fails (default: True)
        default_model_id: Default model ID for transcription (default: parakeet-general)
    """
    backend: str = Field(pattern="^(triton|whisper)$")
    allow_backend_fallback: bool = True
    default_model_id: str = Field(default="parakeet-general")


@router.put("/v1/admin/tenants/{tenant_id}/backend")
async def update_tenant_backend(
    tenant_id: str,
    body: TenantBackendUpdate,
    db = Depends(lambda: None),
    api_key = Depends(lambda: None),
) -> Dict[str, str | bool]:
    """
    Update tenant backend configuration.
    
    Allows administrators to update a tenant's backend configuration, including
    the selected backend (Triton or Whisper), fallback settings, and default model
    ID. Validates the model ID and records an audit event for the change.
    
    Args:
        tenant_id: Tenant identifier
        body: Backend configuration update request
        db: Database connection (injected via dependency)
        api_key: API key for authentication (injected via dependency)
        
    Returns:
        Dictionary containing the updated backend configuration
        
    Raises:
        PermissionError: If API key lacks ADMIN_ALL scope
        ValueError: If model_id is not supported
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)
    
    logger.info(
        f"Updating backend configuration for tenant {tenant_id}",
        extra={
            "tenant_id": tenant_id,
            "backend": body.backend,
            "allow_fallback": body.allow_backend_fallback,
            "default_model_id": body.default_model_id,
        },
    )
    
    validated_model_id = validate_model_id(body.default_model_id)

    await db.execute(
        """
        UPDATE tenants
        SET
            backend = $2,
            allow_backend_fallback = $3,
            default_model_id = $4
        WHERE id = $1
        """,
        tenant_id,
        body.backend,
        body.allow_backend_fallback,
        validated_model_id,
    )

    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=api_key.id,
        event_type="tenant.backend_updated",
        resource="stt_backend",
        payload={
            "backend": body.backend,
            "allow_backend_fallback": body.allow_backend_fallback,
            "default_model_id": validated_model_id,
        },
    )
    
    logger.info(
        f"Successfully updated backend configuration for tenant {tenant_id}"
    )

    return {
        "tenant_id": tenant_id,
        "backend": body.backend,
        "allow_backend_fallback": body.allow_backend_fallback,
        "default_model_id": validated_model_id,
    }
