"""
Tests for speaker identity threshold validation.

This module tests the confidence threshold logic for speaker identity matches.
Tests verify that speaker identities are only accepted when confidence meets or exceeds
the minimum threshold, preventing low-confidence biometric identity guesses from appearing
in transcripts.

Run tests:
    pytest tests/test_speaker_identity_threshold.py

Purpose:
This ensures that resolved speaker identities are emitted only when confidence meets
the minimum threshold (0.85), preventing false positive speaker identifications in transcripts.
This supports the guide's requirement for speaker enrollment to resolve spk_* labels to real
names only with privacy controls for encrypted, deletable voice embeddings.
"""
import logging

from uuid import UUID

from stt_server.speaker_identity import (
    SpeakerIdentityMatch,
    accept_speaker_identity_match,
)

logger = logging.getLogger(__name__)


SPEAKER_PROFILE_ID = UUID("00000000-0000-0000-0000-000000000456")


def test_accepts_speaker_identity_match_at_or_above_threshold():
    """
    Test that speaker identity match is accepted at or above threshold.
    
    Verifies that when a speaker identity match has a confidence score of 0.85
    or higher, the match is accepted and returned unchanged.
    """
    logger.info("Testing speaker identity match accepted at or above threshold")
    
    match = SpeakerIdentityMatch(
        speaker_profile_id=SPEAKER_PROFILE_ID,
        display_name="Alex",
        confidence=0.85,
    )

    accepted = accept_speaker_identity_match(match)

    assert accepted == match
    
    logger.info("Speaker identity match acceptance test passed")


def test_rejects_speaker_identity_match_below_threshold():
    """
    Test that speaker identity match is rejected below threshold.
    
    Verifies that when a speaker identity match has a confidence score below
    the minimum threshold (0.85), the match is rejected and None is returned.
    """
    logger.info("Testing speaker identity match rejected below threshold")
    
    match = SpeakerIdentityMatch(
        speaker_profile_id=SPEAKER_PROFILE_ID,
        display_name="Alex",
        confidence=0.84,
    )

    accepted = accept_speaker_identity_match(match)

    assert accepted is None
    
    logger.info("Speaker identity match rejection test passed")


def test_rejects_missing_speaker_identity_match():
    """
    Test that missing speaker identity match is rejected.
    
    Verifies that when no speaker identity match is provided (None),
    the function returns None without raising an error.
    """
    logger.info("Testing missing speaker identity match is rejected")
    
    accepted = accept_speaker_identity_match(None)

    assert accepted is None
    
    logger.info("Missing speaker identity match rejection test passed")
