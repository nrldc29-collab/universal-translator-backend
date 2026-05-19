"""
Usage API endpoint for retrieving tenant usage statistics.

This module provides a FastAPI endpoint for querying usage statistics for a tenant
over a specified time period with pagination support. The endpoint requires the
USAGE_READ scope for authorization and retrieves data from the usage_counters table.

Endpoints:
- GET /v1/usage - Get tenant usage statistics with pagination

Classes:
    UsageRequest: Request model for usage query with validation.
    UsageResponse: Response model for usage data with example.

Usage:
    The router should be registered in main.py:
        from stt_server.usage_api import router as usage_router
        app.include_router(usage_router)
"""
import logging
from typing import Any
from fastapi import APIRouter, Query, Depends
from pydantic import BaseModel, Field, field_validator
from uuid import UUID

from stt_server.rbac import Scope, require_scope, get_api_key
from stt_server.pagination import PaginatedResponse, paginate, get_pagination_params

logger = logging.getLogger(__name__)

router = APIRouter()


class UsageRequest(BaseModel):
    """Request model for usage query."""
    tenant_id: str = Field(..., description="Tenant ID to query usage for")
    days: int = Field(
        default=30,
        ge=1,
        le=366,
        description="Number of days of usage history to retrieve (1-366)",
    )
    page: int = Field(default=1, ge=1, description="Page number (1-indexed)")
    page_size: int = Field(default=50, ge=1, le=100, description="Items per page (1-100)")
    
    @field_validator("tenant_id")
    @classmethod
    def validate_tenant_id(cls, v: str) -> str:
        """Validate that tenant_id is a valid UUID."""
        try:
            UUID(v)
            return v
        except ValueError:
            raise ValueError("tenant_id must be a valid UUID")


class UsageResponse(BaseModel):
    """Response model for usage data."""
    tenant_id: str = Field(..., description="Tenant ID")
    days: int = Field(..., description="Number of days queried")
    usage: list[dict] = Field(default_factory=list, description="Usage data per day")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174000",
                "days": 30,
                "usage": [
                    {
                        "usage_date": "2024-01-01",
                        "audio_seconds": 3600,
                        "stream_count": 100,
                        "transcription_count": 100,
                    }
                ],
            }
        }


@router.get(
    "/v1/usage",
    response_model=PaginatedResponse[dict],
    summary="Get tenant usage statistics",
    description="Retrieve usage statistics for a tenant over a specified time period with pagination. Requires USAGE_READ scope.",
)
async def get_usage(
    tenant_id: str = Query(..., description="Tenant ID to query usage for"),
    days: int = Query(default=30, ge=1, le=366, description="Number of days of usage history (1-366)"),
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page (1-100)"),
    api_key = Depends(get_api_key),
    db: Any = Depends(lambda: None),  # TODO: Add proper dependency injection
):
    """
    Get tenant usage statistics with pagination.
    
    Validates the tenant ID format, checks authorization scope, retrieves
    usage data from the usage_counters table, and returns paginated results.
    
    Args:
        tenant_id: Tenant ID to query usage for
        days: Number of days of usage history (1-366)
        page: Page number (1-indexed)
        page_size: Items per page (1-100)
        api_key: API key for authentication (dependency injected)
        db: Database connection (dependency injected)
        
    Returns:
        PaginatedResponse containing usage data and pagination metadata
        
    Raises:
        HTTPException: If tenant_id is not a valid UUID
    """
    logger.info(f"Usage query requested for tenant {tenant_id}, days={days}, page={page}")

    # Validate tenant_id format
    try:
        UUID(tenant_id)
    except ValueError:
        from fastapi import HTTPException
        logger.warning(f"Invalid tenant_id format: {tenant_id}")
        raise HTTPException(
            status_code=400,
            detail={
                "error": "invalid_tenant_id",
                "message": "tenant_id must be a valid UUID",
            },
        )
    
    require_scope(api_key.scopes, Scope.USAGE_READ)
    logger.debug(f"Authorization check passed for API key {api_key.id}")

    # Get pagination params
    pagination = get_pagination_params(page, page_size)
    
    # Get total count first
    count_row = await db.fetchrow(
        """
        SELECT COUNT(*) as total
        FROM usage_counters
        WHERE tenant_id = $1
          AND usage_date >= CURRENT_DATE - $2::int
        """,
        tenant_id,
        days,
    )
    total = count_row["total"] if count_row else 0
    logger.debug(f"Found {total} usage records for tenant {tenant_id} over {days} days")
    
    # Get paginated results
    rows = await db.fetch(
        """
        SELECT
            usage_date,
            audio_seconds,
            stream_count,
            transcription_count
        FROM usage_counters
        WHERE tenant_id = $1
          AND usage_date >= CURRENT_DATE - $2::int
        ORDER BY usage_date DESC
        LIMIT $3 OFFSET $4
        """,
        tenant_id,
        days,
        pagination.limit,
        pagination.offset,
    )

    items = [dict(row) for row in rows]
    logger.debug(f"Returning {len(items)} usage records for page {page}")
    
    return paginate(items, total, pagination)

# Register the router in main.py:
#
# from stt_server.usage_api import router as usage_router
#
# app.include_router(usage_router)
#
# This exposes tenant usage from the Postgres usage_counters table and protects it with the usage:read API-key scope, matching the externalized-state and RBAC requirements in the guide.
