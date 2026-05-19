"""
Speaker profiles API endpoints for voice enrollment and management.

This module provides FastAPI endpoints for managing speaker profiles, including
enrollment of new speaker voiceprints, listing profiles for a tenant, and deleting
profiles. All endpoints use encrypted speaker embeddings and support consent tracking.

Endpoints:
- POST /v1/admin/tenants/{tenant_id}/speaker-profiles - Enroll a new speaker profile
- GET /v1/admin/tenants/{tenant_id}/speaker-profiles - List speaker profiles for a tenant
- DELETE /v1/admin/tenants/{tenant_id}/speaker-profiles/{speaker_id} - Delete a speaker profile (admin)
- DELETE /v1/me/speaker-profiles/{speaker_id} - Delete the current user's speaker profile
"""
import logging
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from pydantic import BaseModel, Field

from stt_server.encryption import encrypt_bytes
from stt_server.rbac import Scope, get_api_key, get_tenant, require_scope
from stt_server.speaker_profiles import (
    create_speaker_profile,
    delete_speaker_profile,
    list_active_speaker_profiles,
)
from stt_server.types import AsyncPGConnection

logger = logging.getLogger(__name__)

router = APIRouter()


# Pydantic models for OpenAPI documentation
class SpeakerProfileResponse(BaseModel):
    """
    Response model for speaker profile creation/retrieval.
    
    Attributes:
        id: Unique identifier for the speaker profile
        tenant_id: Tenant ID that owns this profile
        display_name: Human-readable name for the speaker
        embedding_model: Model version used for embedding
        created_at: ISO timestamp when profile was created
    """
    id: UUID = Field(..., description="Unique identifier for the speaker profile")
    tenant_id: UUID = Field(..., description="Tenant ID that owns this profile")
    display_name: str = Field(..., description="Human-readable name for the speaker")
    embedding_model: str = Field(..., description="Model version used for embedding")
    created_at: str = Field(..., description="ISO timestamp when profile was created")
    
    class Config:
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "tenant_id": "123e4567-e89b-12d3-a456-426614174001",
                "display_name": "John Doe",
                "embedding_model": "speaker-embedding-v1",
                "created_at": "2024-01-01T00:00:00Z",
            }
        }


class SpeakerProfileListResponse(BaseModel):
    """
    Response model for listing speaker profiles.
    
    Attributes:
        tenant_id: Tenant ID
        speaker_profiles: List of active speaker profiles
    """
    tenant_id: UUID = Field(..., description="Tenant ID")
    speaker_profiles: list[SpeakerProfileResponse] = Field(..., description="List of active speaker profiles")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174001",
                "speaker_profiles": [],
            }
        }


class SpeakerProfileDeleteResponse(BaseModel):
    """
    Response model for speaker profile deletion.
    
    Attributes:
        tenant_id: Tenant ID
        speaker_profile_id: ID of deleted profile
        deleted: True if deletion was successful
    """
    tenant_id: UUID = Field(..., description="Tenant ID")
    speaker_profile_id: UUID = Field(..., description="ID of deleted profile")
    deleted: bool = Field(..., description="True if deletion was successful")
    
    class Config:
        json_schema_extra = {
            "example": {
                "tenant_id": "123e4567-e89b-12d3-a456-426614174001",
                "speaker_profile_id": "123e4567-e89b-12d3-a456-426614174000",
                "deleted": True,
            }
        }


@router.post(
    "/v1/admin/tenants/{tenant_id}/speaker-profiles",
    response_model=SpeakerProfileResponse,
    summary="Enroll a new speaker profile",
    description="Create a new speaker profile with encrypted voice embedding for a tenant. Requires ADMIN_ALL scope.",
)
async def enroll_speaker_profile(
    tenant_id: UUID,
    display_name: str = Form(..., description="Human-readable name for the speaker"),
    consent_record_id: str | None = Form(default=None, description="Optional consent record ID"),
    file: UploadFile = File(..., description="Audio file for speaker embedding extraction"),
    db: AsyncPGConnection = Depends(lambda: None),  # Database connection (stubbed when not configured)
    api_key = Depends(get_api_key),
):
    """
    Enroll a new speaker profile for a tenant.
    
    Processes an audio file to extract a speaker embedding, encrypts it, and stores
    it as a speaker profile. Requires ADMIN_ALL scope for authorization.
    
    Args:
        tenant_id: Tenant ID to create the profile for
        display_name: Human-readable name for the speaker
        consent_record_id: Optional consent record ID for compliance tracking
        file: Audio file for speaker embedding extraction
        db: Database connection (dependency injected)
        api_key: API key for authentication (dependency injected)
        
    Returns:
        SpeakerProfileResponse with the created profile details
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)

    logger.info(
        f"Enrolling speaker profile for tenant {tenant_id}, display_name={display_name}"
    )

    audio_bytes = await file.read()
    logger.debug(f"Read {len(audio_bytes)} bytes from audio file: {file.filename}")

    # Replace this with the real output from your speaker embedding model.
    raw_embedding = b"replace-with-raw-speaker-embedding"
    logger.debug("Extracted speaker embedding (placeholder)")

    encrypted_embedding = encrypt_bytes(raw_embedding)
    logger.debug("Encrypted speaker embedding")

    try:
        profile = await create_speaker_profile(
            db,
            tenant_id=tenant_id,
            actor_id=api_key.id,
            speaker_id=uuid4(),
            display_name=display_name,
            encrypted_embedding=encrypted_embedding,
            embedding_model="speaker-embedding-v1",
            consent_record_id=consent_record_id,
        )
    except Exception as exc:
        logger.warning(f"Speaker profile creation failed (database not configured): {exc}")
        raise HTTPException(status_code=503, detail="Speaker profile database not configured") from exc

    logger.info(f"Created speaker profile {profile['id']} for tenant {tenant_id}")
    return profile


@router.get(
    "/v1/admin/tenants/{tenant_id}/speaker-profiles",
    response_model=SpeakerProfileListResponse,
    summary="List speaker profiles for a tenant",
    description="Retrieve all active speaker profiles for a specific tenant. Requires ADMIN_ALL scope.",
)
async def list_speaker_profiles(
    tenant_id: UUID,
    db: AsyncPGConnection = Depends(lambda: None),  # Database connection (stubbed when not configured)
    api_key = Depends(get_api_key),
):
    """
    List all active speaker profiles for a tenant.
    
    Retrieves all non-deleted speaker profiles for the specified tenant.
    Requires ADMIN_ALL scope for authorization.
    
    Args:
        tenant_id: Tenant ID to list profiles for
        db: Database connection (dependency injected)
        api_key: API key for authentication (dependency injected)
        
    Returns:
        SpeakerProfileListResponse with tenant ID and list of profiles
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)

    logger.info(f"Listing speaker profiles for tenant {tenant_id}")

    try:
        profiles = await list_active_speaker_profiles(
            db,
            tenant_id=tenant_id,
        )
    except Exception as exc:
        logger.warning(f"Speaker profile listing failed (database not configured): {exc}")
        raise HTTPException(status_code=503, detail="Speaker profile database not configured") from exc

    logger.debug(f"Found {len(profiles)} active speaker profiles for tenant {tenant_id}")

    return {
        "tenant_id": tenant_id,
        "speaker_profiles": profiles,
    }


@router.delete(
    "/v1/admin/tenants/{tenant_id}/speaker-profiles/{speaker_id}",
    response_model=SpeakerProfileDeleteResponse,
    summary="Delete a speaker profile (admin)",
    description="Soft-delete a speaker profile for a tenant. Requires ADMIN_ALL scope.",
)
async def remove_speaker_profile(
    tenant_id: UUID,
    speaker_id: UUID,
    db: AsyncPGConnection = Depends(lambda: None),  # Database connection (stubbed when not configured)
    api_key = Depends(get_api_key),
):
    """
    Soft-delete a speaker profile (admin operation).
    
    Marks a speaker profile as deleted without removing it from the database.
    Requires ADMIN_ALL scope for authorization.
    
    Args:
        tenant_id: Tenant ID that owns the profile
        speaker_id: Speaker profile ID to delete
        db: Database connection (dependency injected)
        api_key: API key for authentication (dependency injected)
        
    Returns:
        SpeakerProfileDeleteResponse confirming deletion
    """
    require_scope(api_key.scopes, Scope.ADMIN_ALL)

    logger.info(
        f"Admin deleting speaker profile {speaker_id} for tenant {tenant_id}"
    )

    try:
        deleted = await delete_speaker_profile(
            db,
            tenant_id=tenant_id,
            speaker_id=speaker_id,
        )
    except Exception as exc:
        logger.warning(f"Speaker profile deletion failed (database not configured): {exc}")
        raise HTTPException(status_code=503, detail="Speaker profile database not configured") from exc

    logger.info(f"Deleted speaker profile {speaker_id}")

    return {
        "tenant_id": tenant_id,
        "speaker_profile_id": speaker_id,
        "deleted": True,
    }


@router.delete(
    "/v1/me/speaker-profiles/{speaker_id}",
    response_model=SpeakerProfileDeleteResponse,
    summary="Delete my speaker profile",
    description="Soft-delete the current user's speaker profile. No special scope required.",
)
async def delete_my_voiceprint(
    speaker_id: UUID,
    db: AsyncPGConnection = Depends(lambda: None),  # Database connection (stubbed when not configured)
    api_key = Depends(get_api_key),
    tenant = Depends(get_tenant),
):
    """
    Soft-delete the current user's speaker profile.
    
    Allows a user to delete their own speaker profile without requiring
    admin scope. The profile must belong to the user's tenant.
    
    Args:
        speaker_id: Speaker profile ID to delete
        db: Database connection (dependency injected)
        api_key: API key for authentication (dependency injected)
        tenant: Tenant object from API key (dependency injected)
        
    Returns:
        SpeakerProfileDeleteResponse confirming deletion
    """
    tenant_id = tenant.id

    logger.info(
        f"User deleting own speaker profile {speaker_id} for tenant {tenant_id}"
    )

    try:
        await delete_speaker_profile(
            db,
            tenant_id=tenant_id,
            actor_id=api_key.id,
            speaker_id=speaker_id,
        )
    except Exception as exc:
        logger.warning(f"Speaker profile deletion failed (database not configured): {exc}")
        raise HTTPException(status_code=503, detail="Speaker profile database not configured") from exc

    logger.info(f"Deleted user's speaker profile {speaker_id}")

    return {
        "tenant_id": tenant_id,
        "speaker_profile_id": speaker_id,
        "deleted": True,
    }
