"""
Admin models API module for tenant default model configuration.

This module provides a FastAPI router for administrators to update tenant default
model configurations, allowing safe selection of Triton domain models with validation
against the approved allowlist and audit logging for compliance tracking.
"""
import logging
from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from stt_server.audit import write_audit_event
from stt_server.model_registry import validate_model_id
from stt_server.rbac import Scope, require_scope

logger = logging.getLogger(__name__)

router = APIRouter()


class TenantDefaultModelUpdate(BaseModel):
    """
    Request body for updating tenant default model configuration.
    
    Attributes:
        default_model_id: Default model ID to use for transcription
    """
    default_model_id: str


@router.put("/v1/admin/tenants/{tenant_id}/default-model")
async def update_tenant_default_model(
    tenant_id: str,
    body: TenantDefaultModelUpdate,
    db = Depends(lambda: None),
    api_key = Depends(lambda: None),
) -> Dict[str, str]:
    """
    Update tenant default model configuration.
    
    Allows administrators to update a tenant's default model ID for transcription.
    Validates the model ID against the approved allowlist and records an audit
    event for the change to support compliance tracking.
    
    Args:
        tenant_id: Tenant identifier
        body: Default model update request
        db: Database connection (injected via dependency)
        api_key: API key for authentication (injected via dependency)
        
    Returns:
        Dictionary containing the updated default model configuration
        
    Raises:
        PermissionError: If API key lacks ADMIN_ALL scope
        HTTPException: If model_id is not supported (422 Unprocessable Entity)
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)
    
    logger.info(
        f"Updating default model for tenant {tenant_id}",
        extra={
            "tenant_id": tenant_id,
            "default_model_id": body.default_model_id,
        },
    )

    try:
        model_id = validate_model_id(body.default_model_id)
    except ValueError as exc:
        logger.warning(
            f"Invalid model_id requested for tenant {tenant_id}: {body.default_model_id}",
            extra={
                "tenant_id": tenant_id,
                "requested_model_id": body.default_model_id,
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "unsupported_model_id",
                "message": str(exc),
            },
        ) from exc

    await db.execute(
        """
        UPDATE tenants
        SET default_model_id = $2
        WHERE id = $1
        """,
        tenant_id,
        model_id,
    )

    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=api_key.id,
        event_type="tenant.default_model_updated",
        resource="stt_model",
        payload={
            "default_model_id": model_id,
        },
    )
    
    logger.info(
        f"Successfully updated default model for tenant {tenant_id} to {model_id}"
    )

    return {
        "tenant_id": tenant_id,
        "default_model_id": model_id,
    }
