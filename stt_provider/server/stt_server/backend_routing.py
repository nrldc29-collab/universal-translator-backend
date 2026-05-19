"""
Backend routing configuration module.

This module provides functionality for determining which transcription backend
to use for a specific tenant, supporting per-tenant backend selection between
Triton and Whisper with optional fallback configuration.
"""
import logging
from dataclasses import dataclass
from enum import StrEnum

logger = logging.getLogger(__name__)


class BackendName(StrEnum):
    """
    Available transcription backend names.
    
    Defines the supported backend options for speech transcription.
    
    Attributes:
        TRITON: Triton inference server backend
        WHISPER: Whisper model backend
    """
    TRITON = "triton"
    WHISPER = "whisper"


@dataclass
class TenantBackendConfig:
    """
    Backend configuration for a tenant.
    
    Represents the backend configuration for a specific tenant,
    including the preferred backend and whether fallback is allowed.
    
    Attributes:
        tenant_id: Tenant identifier
        backend: Preferred backend for the tenant
        allow_fallback: Whether to allow fallback to alternate backend (default: True)
    """
    tenant_id: str
    backend: BackendName
    allow_fallback: bool = True


async def get_tenant_backend_config(db, tenant_id: str) -> TenantBackendConfig:
    """
    Get the backend configuration for a tenant.
    
    Queries the database for the tenant's backend configuration.
    Returns the configured backend and fallback preference, or defaults
    to Triton with fallback enabled if the tenant is not found or has
    no configuration.
    
    Args:
        db: Database connection
        tenant_id: Tenant identifier
        
    Returns:
        TenantBackendConfig with the tenant's backend configuration
    """
    row = await db.fetchrow(
        """
        SELECT
            id,
            COALESCE(backend, 'triton') AS backend,
            COALESCE(allow_backend_fallback, true) AS allow_fallback
        FROM tenants
        WHERE id = $1
        """,
        tenant_id,
    )

    if row is None:
        logger.info(f"Tenant {tenant_id} not found, using default backend config")
        return TenantBackendConfig(
            tenant_id=tenant_id,
            backend=BackendName.TRITON,
            allow_fallback=True,
        )

    config = TenantBackendConfig(
        tenant_id=str(row["id"]),
        backend=BackendName(row["backend"]),
        allow_fallback=bool(row["allow_fallback"]),
    )
    logger.debug(f"Retrieved backend config for tenant {tenant_id}: {config.backend}, fallback={config.allow_fallback}")
    return config


# Add these columns to your tenants table:
#
# ALTER TABLE tenants
# ADD COLUMN IF NOT EXISTS backend TEXT NOT NULL DEFAULT 'triton';
#
# ALTER TABLE tenants
# ADD COLUMN IF NOT EXISTS allow_backend_fallback BOOLEAN NOT NULL DEFAULT true;
#
# Then update your streaming backend builder to accept the tenant setting:
#
# def build_streaming_backend(
#     backend_name: str,
# ) -> TritonStreamingClient | WhisperModel:
#     if backend_name == "triton":
#         return TritonStreamingClient(
#             grpc_url=os.environ["TRITON_GRPC_URL"],
#             asr_model=os.environ["TRITON_ASR_MODEL"],
#             diarization_model=os.environ["TRITON_DIARIZATION_MODEL"],
#             timeout_ms=int(os.getenv("TRITON_REQUEST_TIMEOUT_MS", "5000")),
#         )
#
#     return WhisperModel()
#
# Use it when opening a stream:
#
# tenant_backend = await get_tenant_backend_config(db, tenant.id)
#
# backend = build_streaming_backend(
#     tenant_backend.backend,
# )
#
# This gives you per-tenant routing between the self-hosted Triton backend and the Whisper fallback, which supports the guide's Phase 2B rollout model: roll out by tenant tier while keeping Whisper available during ramp.
