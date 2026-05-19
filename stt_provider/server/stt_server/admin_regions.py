"""
Admin regions API module for tenant regional configuration.

This module provides a FastAPI router for administrators to update tenant regional
configurations, allowing controlled selection of home regions and cross-region
failover settings with validation against the approved region allowlist and audit
logging for compliance tracking.
"""
import logging
from typing import Dict, Set

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from stt_server.audit import write_audit_event
from stt_server.rbac import Scope, require_scope

logger = logging.getLogger(__name__)

router = APIRouter()

# Allowed regions for tenant deployment
ALLOWED_REGIONS: Set[str] = {
    "us-east-1",
    "us-west-2",
    "eu-west-1",
}


class TenantRegionUpdate(BaseModel):
    """
    Request body for updating tenant regional configuration.
    
    Attributes:
        home_region: Primary region for tenant deployment
        allow_cross_region_failover: Whether to allow failover to other regions (default: False)
    """
    home_region: str = Field(...)
    allow_cross_region_failover: bool = False


@router.put("/v1/admin/tenants/{tenant_id}/region")
async def update_tenant_region(
    tenant_id: str,
    body: TenantRegionUpdate,
    db = Depends(lambda: None),
    api_key = Depends(lambda: None),
) -> Dict[str, str | bool]:
    """
    Update tenant regional configuration.
    
    Allows administrators to update a tenant's home region and cross-region
    failover settings. Validates the region against the approved allowlist
    and records an audit event for the change to support compliance tracking.
    
    Args:
        tenant_id: Tenant identifier
        body: Regional configuration update request
        db: Database connection (injected via dependency)
        api_key: API key for authentication (injected via dependency)
        
    Returns:
        Dictionary containing the updated regional configuration
        
    Raises:
        PermissionError: If API key lacks ADMIN_ALL scope
        HTTPException: If region is not supported (422 Unprocessable Entity)
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)
    
    logger.info(
        f"Updating region configuration for tenant {tenant_id}",
        extra={
            "tenant_id": tenant_id,
            "home_region": body.home_region,
            "allow_cross_region_failover": body.allow_cross_region_failover,
        },
    )

    if body.home_region not in ALLOWED_REGIONS:
        logger.warning(
            f"Unsupported region requested for tenant {tenant_id}: {body.home_region}",
            extra={
                "tenant_id": tenant_id,
                "requested_region": body.home_region,
                "allowed_regions": sorted(ALLOWED_REGIONS),
            },
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "unsupported_region",
                "allowed_regions": sorted(ALLOWED_REGIONS),
            },
        )

    await db.execute(
        """
        UPDATE tenants
        SET
            home_region = $2,
            allow_cross_region_failover = $3
        WHERE id = $1
        """,
        tenant_id,
        body.home_region,
        body.allow_cross_region_failover,
    )

    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=api_key.id,
        event_type="tenant.region_updated",
        resource="regional_routing",
        payload={
            "home_region": body.home_region,
            "allow_cross_region_failover": body.allow_cross_region_failover,
        },
    )
    
    logger.info(
        f"Successfully updated region configuration for tenant {tenant_id}"
    )

    return {
        "tenant_id": tenant_id,
        "home_region": body.home_region,
        "allow_cross_region_failover": body.allow_cross_region_failover,
    }
