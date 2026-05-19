"""
Tenant rollout configuration module.

This module provides data classes and functions for managing tenant-specific
backend configurations during phased rollouts. It supports retrieving backend
settings, fallback behavior, stream limits, model selection, and regional
configuration for individual tenants.

Classes:
    TenantRolloutConfig: Data class for tenant rollout configuration.
    TenantBackendConfig: Data class for tenant backend configuration.

Functions:
    get_tenant_rollout_config: Retrieve backend configuration for a specific tenant.
    list_tenants_by_backend: List all tenants configured for a specific backend.

Usage:
    Use get_tenant_rollout_config() when opening a stream so backend routing,
    fallback behavior, stream limits, model selection, and home region all come
    from one tenant rollout record. This supports phased tenant-by-tenant rollout
    while keeping Whisper available as fallback during ramp.
"""
import logging
from dataclasses import dataclass
from uuid import UUID

logger = logging.getLogger(__name__)


@dataclass
class TenantRolloutConfig:
    """
    Tenant rollout configuration data class.

    Contains comprehensive configuration for a tenant's backend rollout
    including backend selection, fallback settings, stream limits, model
    configuration, and regional settings.

    Attributes:
        tenant_id: Unique tenant identifier (UUID)
        backend: Backend type (e.g., "triton", "whisper")
        allow_backend_fallback: Whether to allow fallback to alternate backend
        max_concurrent_streams: Maximum concurrent streaming sessions allowed
        default_model_id: Default transcription model ID for the tenant
        home_region: Primary region for the tenant
    """
    tenant_id: UUID
    backend: str
    allow_backend_fallback: bool
    max_concurrent_streams: int
    default_model_id: str
    home_region: str


@dataclass
class TenantBackendConfig:
    """
    Tenant backend configuration data class.

    Contains operational backend configuration for a tenant including
    backend selection, fallback settings, stream limits, model selection,
    and regional configuration.

    Attributes:
        tenant_id: Unique tenant identifier (UUID)
        backend: Backend type (e.g., "triton", "whisper")
        allow_fallback: Whether to allow fallback to alternate backend
        stream_limit: Maximum streaming requests per minute
        model_id: Transcription model ID to use
        home_region: Primary region for the tenant
    """
    tenant_id: UUID
    backend: str
    allow_fallback: bool
    stream_limit: int
    model_id: str
    home_region: str


async def get_tenant_rollout_config(
    db,
    *,
    tenant_id: UUID,
) -> TenantBackendConfig:
    """
    Retrieve backend configuration for a specific tenant from the database.

    Fetches the tenant's backend configuration including backend type,
    fallback settings, stream limits, model selection, and home region.
    Raises an error if the tenant is not found.

    Args:
        db: Database connection for querying tenant configuration
        tenant_id: Tenant UUID to retrieve configuration for

    Returns:
        TenantBackendConfig with the tenant's backend configuration

    Raises:
        ValueError: If the tenant ID is not found in the database
    """
    logger.debug(f"Retrieving tenant rollout config for tenant {tenant_id}")
    
    row = await db.fetchrow(
        """
        SELECT
            backend,
            allow_backend_fallback,
            stream_limit_per_minute,
            model_id,
            home_region
        FROM tenants
        WHERE id = $1
        """,
        tenant_id,
    )

    if not row:
        logger.warning(f"Tenant not found in database: {tenant_id}")
        raise ValueError(
            f"Tenant not found: {tenant_id}. "
            f"Please verify the tenant ID is correct and the tenant exists in the database."
        )

    config = TenantBackendConfig(
        tenant_id=tenant_id,
        backend=row["backend"],
        allow_fallback=row["allow_backend_fallback"],
        stream_limit=row["stream_limit_per_minute"],
        model_id=row["model_id"],
        home_region=row["home_region"],
    )
    
    logger.debug(
        f"Retrieved tenant config: backend={config.backend}, "
        f"model={config.model_id}, region={config.home_region}"
    )
    
    return config


async def list_tenants_by_backend(
    db,
    *,
    backend: str,
    limit: int = 100,
) -> list[TenantRolloutConfig]:
    """
    List all tenants configured for a specific backend.

    Retrieves a list of tenants that are configured to use the specified
    backend, ordered by creation date. This is useful for tracking rollout
    progress and managing phased deployments.

    Args:
        db: Database connection for querying tenant configurations
        backend: Backend type to filter tenants by (e.g., "triton", "whisper")
        limit: Maximum number of tenants to return (default: 100)

    Returns:
        List of TenantRolloutConfig objects for tenants using the specified backend
    """
    logger.debug(f"Listing tenants for backend: {backend}, limit={limit}")
    
    rows = await db.fetch(
        """
        SELECT
            id,
            backend,
            allow_backend_fallback,
            max_concurrent_streams,
            default_model_id,
            home_region
        FROM tenants
        WHERE backend = $1
        ORDER BY created_at ASC
        LIMIT $2
        """,
        backend,
        limit,
    )

    configs = [
        TenantRolloutConfig(
            tenant_id=row["id"],
            backend=row["backend"],
            allow_backend_fallback=row["allow_backend_fallback"],
            max_concurrent_streams=row["max_concurrent_streams"],
            default_model_id=row["default_model_id"],
            home_region=row["home_region"],
        )
        for row in rows
    ]
    
    logger.info(f"Found {len(configs)} tenants configured for backend {backend}")
    
    return configs
