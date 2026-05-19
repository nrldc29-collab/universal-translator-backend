"""
Speaker profile database operations.

This module provides async functions for managing speaker profiles in the database,
including creation, soft deletion, and listing of active profiles. All operations
include audit logging for compliance tracking.

Functions:
    create_speaker_profile: Create a new speaker profile with encrypted embedding
    delete_speaker_profile: Soft-delete a speaker profile
    list_active_speaker_profiles: List all non-deleted profiles for a tenant
"""
import logging
from typing import Dict
from uuid import UUID

from stt_server.audit import write_audit_event

logger = logging.getLogger(__name__)


async def create_speaker_profile(
    db,
    *,
    tenant_id: UUID,
    actor_id: str,
    speaker_id: UUID,
    display_name: str,
    encrypted_embedding: bytes,
    embedding_model: str,
    consent_record_id: str | None = None,
) -> Dict:
    """
    Create a new speaker profile with encrypted voice embedding.
    
    Inserts a new speaker profile record into the database with the provided
    encrypted embedding and metadata. Writes an audit event for compliance.
    
    Args:
        db: Database connection
        tenant_id: Tenant ID that owns this profile
        actor_id: ID of the user creating the profile
        speaker_id: Unique ID for the speaker profile
        display_name: Human-readable name for the speaker
        encrypted_embedding: Encrypted speaker embedding bytes
        embedding_model: Model version used for embedding
        consent_record_id: Optional consent record ID for compliance
        
    Returns:
        Dictionary containing the created profile record
        
    Raises:
        Exception: If database insertion fails
    """
    logger.info(
        f"Creating speaker profile {speaker_id} for tenant {tenant_id}, "
        f"display_name={display_name}, model={embedding_model}"
    )

    row = await db.fetchrow(
        """
        INSERT INTO speaker_profiles (
            id,
            tenant_id,
            display_name,
            encrypted_embedding,
            embedding_model,
            consent_record_id
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING
            id,
            tenant_id,
            display_name,
            embedding_model,
            consent_record_id,
            created_at
        """,
        speaker_id,
        tenant_id,
        display_name,
        encrypted_embedding,
        embedding_model,
        consent_record_id,
    )

    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type="speaker_profile.created",
        resource="speaker_profile",
        payload={
            "speaker_profile_id": str(speaker_id),
            "display_name": display_name,
            "embedding_model": embedding_model,
            "consent_record_id": consent_record_id,
        },
    )

    logger.debug(f"Created speaker profile {speaker_id} with audit event")
    return dict(row)


async def delete_speaker_profile(
    db,
    *,
    tenant_id: UUID,
    actor_id: str,
    speaker_id: UUID,
) -> None:
    """
    Soft-delete a speaker profile by setting deleted_at timestamp.
    
    Marks a speaker profile as deleted without removing it from the database.
    The profile remains in the database for audit purposes but is excluded
    from active queries. Writes an audit event for compliance.
    
    Args:
        db: Database connection
        tenant_id: Tenant ID that owns the profile
        actor_id: ID of the user deleting the profile
        speaker_id: Speaker profile ID to delete
        
    Raises:
        Exception: If database update fails
    """
    logger.info(f"Soft-deleting speaker profile {speaker_id} for tenant {tenant_id}")

    await db.execute(
        """
        UPDATE speaker_profiles
        SET deleted_at = now()
        WHERE id = $1
          AND tenant_id = $2
          AND deleted_at IS NULL
        """,
        speaker_id,
        tenant_id,
    )

    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type="speaker_profile.deleted",
        resource="speaker_profile",
        payload={
            "speaker_profile_id": str(speaker_id),
        },
    )

    logger.debug(f"Deleted speaker profile {speaker_id} with audit event")


async def list_active_speaker_profiles(
    db,
    *,
    tenant_id: UUID,
) -> list[Dict]:
    """
    List all active (non-deleted) speaker profiles for a tenant.
    
    Retrieves all speaker profiles for the specified tenant that have not been
    soft-deleted, ordered by creation date descending.
    
    Args:
        db: Database connection
        tenant_id: Tenant ID to list profiles for
        
    Returns:
        List of dictionaries containing speaker profile records
        
    Raises:
        Exception: If database query fails
    """
    logger.debug(f"Listing active speaker profiles for tenant {tenant_id}")

    rows = await db.fetch(
        """
        SELECT
            id,
            tenant_id,
            display_name,
            embedding_model,
            consent_record_id,
            created_at
        FROM speaker_profiles
        WHERE tenant_id = $1
          AND deleted_at IS NULL
        ORDER BY created_at DESC
        """,
        tenant_id,
    )

    profiles = [dict(row) for row in rows]
    logger.debug(f"Found {len(profiles)} active speaker profiles for tenant {tenant_id}")

    return profiles
