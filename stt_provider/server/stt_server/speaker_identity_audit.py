"""
Speaker identity audit logging module.

This module provides audit logging functionality for speaker identity matching events.
It records when a live speaker is matched against an enrolled speaker profile,
including confidence scores and session information for compliance and tracking.

Functions:
    audit_speaker_identity_match: Record a speaker identity match event to the audit log.
"""
import logging
from uuid import UUID

from stt_server.audit import write_audit_event

logger = logging.getLogger(__name__)


async def audit_speaker_identity_match(
    db,
    *,
    tenant_id: UUID,
    speaker_profile_id: UUID,
    display_name: str,
    confidence: float,
    session_id: str,
) -> None:
    """
    Record a speaker identity match event to the audit log.

    Logs when a live speaker is matched against an enrolled speaker profile,
    capturing the match confidence, profile information, and session context
    for compliance and security auditing purposes.

    Args:
        db: Database connection for writing audit events
        tenant_id: Tenant UUID that owns the speaker profile
        speaker_profile_id: UUID of the matched speaker profile
        display_name: Display name of the matched speaker
        confidence: Match confidence score (0.0 to 1.0)
        session_id: Session identifier for the transcription session
    """
    logger.debug(
        f"Auditing speaker identity match: tenant={tenant_id}, "
        f"profile={speaker_profile_id}, confidence={confidence:.2f}"
    )
    
    await write_audit_event(
        db,
        tenant_id=tenant_id,
        actor_id=None,
        event_type="speaker_identity.matched",
        resource="speaker_profile",
        payload={
            "speaker_profile_id": str(speaker_profile_id),
            "display_name": display_name,
            "confidence": confidence,
            "session_id": session_id,
        },
    )
    
    logger.info(f"Speaker identity match audited: profile={speaker_profile_id}")
