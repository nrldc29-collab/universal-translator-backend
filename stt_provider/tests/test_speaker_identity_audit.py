"""
Tests for speaker identity audit logging.

This module tests that speaker identity matches are properly logged to the audit trail.
Audit logging is critical for compliance and traceability of biometric data usage,
ensuring all speaker identity matches are recorded without exposing raw voice embeddings.

Run tests:
    pytest tests/test_speaker_identity_audit.py

Purpose:
This ensures that resolved speaker identity matches are audit-visible with appropriate
context (tenant ID, speaker profile ID, display name, confidence score, session ID)
while maintaining privacy by not exposing raw voice embeddings. This supports the
guide's requirement for speaker enrollment to handle voice embeddings as biometric data
with encryption, deletion, and privacy controls.
"""
import logging

from uuid import UUID

import pytest

from stt_server.speaker_identity_audit import audit_speaker_identity_match

logger = logging.getLogger(__name__)


TENANT_ID = UUID("00000000-0000-0000-0000-000000000123")
SPEAKER_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000456")


class FakeDb:
    """
    Fake database for testing audit event logging.
    
    Records executed queries and their arguments for verification.
    """
    def __init__(self):
        """Initialize the fake database with an empty event list."""
        self.events = []

    async def execute(self, query, *args):
        """
        Record a database query execution.
        
        Args:
            query: The SQL query that would be executed.
            *args: Arguments passed to the query.
        """
        self.events.append(
            {
                "query": query,
                "args": args,
            }
        )
        return None


@pytest.mark.asyncio
async def test_audit_speaker_identity_match_writes_event():
    """
    Test that speaker identity match writes an audit event.
    
    Verifies that when a speaker identity match is resolved, an audit event is written
    to the audit log with the event type 'speaker_identity.matched', resource 'speaker_profile',
    and the speaker profile ID, display name, confidence score, and session ID in the payload.
    """
    logger.info("Testing speaker identity match writes audit event")
    
    db = FakeDb()

    await audit_speaker_identity_match(
        db,
        tenant_id=TENANT_ID,
        speaker_profile_id=SPEAKER_PROFILE_ID,
        display_name="Alex",
        confidence=0.91,
        session_id="session_123",
    )

    assert len(db.events) == 1

    event_args = str(db.events[0]["args"])

    assert "speaker_identity.matched" in event_args
    assert "speaker_profile" in event_args
    assert str(SPEAKER_PROFILE_ID) in event_args
    assert "Alex" in event_args
    assert "0.91" in event_args
    assert "session_123" in event_args
    
    logger.info("Speaker identity match audit event test passed")
