"""
Tests for streaming event schema serialization.

This module tests the serialization of transcript events for WebSocket streaming.
Tests verify that partial and final transcript events are properly formatted with
word-level details and optional speaker identity information.

Run tests:
    pytest tests/test_streaming_event_schema.py

Purpose:
This ensures that transcript events can carry both the original diarization label
(like spk_0) and a resolved speaker identity when confidence is high enough.
This supports the guide's speaker enrollment step requirement to resolve spk_* labels
to real names only with privacy controls around encrypted, deletable voice embeddings.
"""
import logging

from uuid import UUID

from stt_server.backends.triton import (
    TritonSpeakerIdentity,
    TritonTranscriptResult,
    TritonTranscriptWord,
)

logger = logging.getLogger(__name__)


def serialize_transcript_event(result: TritonTranscriptResult) -> dict:
    """
    Serialize a TritonTranscriptResult to a WebSocket event dictionary.
    
    Args:
        result: The TritonTranscriptResult to serialize.
        
    Returns:
        A dictionary with event type, text, and word-level details including
        optional speaker identity information.
    """
    event_type = "transcript.final" if result.is_final else "transcript.partial"

    return {
        "type": event_type,
        "text": result.text,
        "words": [
            {
                "word": word.word,
                "start": word.start,
                "end": word.end,
                "speaker": word.speaker,
                "confidence": word.confidence,
                "speaker_identity": (
                    {
                        "speaker_profile_id": str(word.speaker_identity.speaker_profile_id),
                        "display_name": word.speaker_identity.display_name,
                        "confidence": word.speaker_identity.confidence,
                    }
                    if word.speaker_identity is not None
                    else None
                ),
            }
            for word in result.words
        ],
    }


def test_partial_transcript_event_schema():
    """
    Test that partial transcript events are properly serialized.
    
    Verifies that partial transcript results are serialized with the correct
    event type, text, and word-level details without speaker identity information.
    """
    logger.info("Testing partial transcript event schema")
    
    result = TritonTranscriptResult(
        text="hello wor",
        is_final=False,
        words=[
            TritonTranscriptWord(
                word="hello",
                start=0.10,
                end=0.42,
                speaker="spk_0",
                confidence=0.94,
            )
        ],
    )

    event = serialize_transcript_event(result)

    assert event == {
        "type": "transcript.partial",
        "text": "hello wor",
        "words": [
            {
                "word": "hello",
                "start": 0.10,
                "end": 0.42,
                "speaker": "spk_0",
                "confidence": 0.94,
            }
        ],
    }
    
    logger.info("Partial transcript event schema test passed")


def test_final_transcript_event_schema():
    """
    Test that final transcript events are properly serialized.
    
    Verifies that final transcript results are serialized with the correct
    event type, text, and word-level details for all words.
    """
    logger.info("Testing final transcript event schema")
    
    result = TritonTranscriptResult(
        text="hello world",
        is_final=True,
        words=[
            TritonTranscriptWord(
                word="hello",
                start=0.10,
                end=0.42,
                speaker="spk_0",
                confidence=0.94,
            ),
            TritonTranscriptWord(
                word="world",
                start=0.44,
                end=0.88,
                speaker="spk_0",
                confidence=0.91,
            ),
        ],
    )

    event = serialize_transcript_event(result)

    assert event["type"] == "transcript.final"
    assert event["text"] == "hello world"
    assert event["words"][0]["speaker"] == "spk_0"
    assert event["words"][1]["confidence"] == 0.91
    
    logger.info("Final transcript event schema test passed")


def test_final_transcript_event_supports_speaker_identity():
    """
    Test that final transcript events support speaker identity resolution.
    
    Verifies that when speaker identity is available, it is serialized with
    the speaker profile ID, display name, and confidence score alongside the
    original diarization label.
    """
    logger.info("Testing final transcript event supports speaker identity")
    
    speaker_profile_id = UUID("00000000-0000-0000-0000-000000000456")

    result = TritonTranscriptResult(
        text="thanks for joining",
        is_final=True,
        words=[
            TritonTranscriptWord(
                word="thanks",
                start=0.10,
                end=0.42,
                speaker="spk_0",
                confidence=0.94,
                speaker_identity=TritonSpeakerIdentity(
                    speaker_profile_id=speaker_profile_id,
                    display_name="Alex",
                    confidence=0.91,
                ),
            )
        ],
    )

    event = serialize_transcript_event(result)

    assert event["type"] == "transcript.final"
    assert event["words"][0]["speaker"] == "spk_0"
    assert event["words"][0]["speaker_identity"] == {
        "speaker_profile_id": "00000000-0000-0000-0000-000000000456",
        "display_name": "Alex",
        "confidence": 0.91,
    }
    
    logger.info("Speaker identity support test passed")
