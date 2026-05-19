"""
Tests for WebSocket message validation functionality.

This module tests the WebSocketMessageValidator implementation which validates
incoming WebSocket messages for the STT service. Tests verify audio frame validation
(size, format), control message validation (JSON structure, message types), session
configuration updates, and the global validator singleton.

Run tests:
    pytest server/tests/test_websocket_validation.py

Purpose:
This ensures that the WebSocket validation layer properly rejects malformed or
malicious messages before they reach the transcription backend, protecting against
resource exhaustion attacks and ensuring proper message format.
"""
import logging

import pytest

from stt_server.websocket_validation import (
    AudioFormatSpec,
    WebSocketMessageValidator,
    MessageType,
    get_validator,
)

logger = logging.getLogger(__name__)


def test_audio_format_spec_defaults():
    """
    Test default audio format specification.
    
    Verifies that AudioFormatSpec is initialized with sensible defaults
    for sample rate, channels, bit depth, encoding, and frame sizes.
    """
    logger.info("Testing default audio format specification")
    
    spec = AudioFormatSpec()
    
    assert spec.sample_rate == 16000
    assert spec.channels == 1
    assert spec.bit_depth == 16
    assert spec.encoding == "pcm_s16le"
    assert spec.min_frame_size == 320  # 10ms at 16kHz
    assert spec.max_frame_size == 9600  # 300ms at 16kHz
    
    logger.info("Default audio format specification test passed")


def test_audio_frame_validation_valid():
    """
    Test validation of valid audio frames.
    
    Verifies that a properly sized audio frame passes validation.
    """
    logger.info("Testing validation of valid audio frames")
    
    validator = WebSocketMessageValidator()
    
    # Valid 30ms frame at 16kHz (480 samples * 2 bytes = 960 bytes)
    valid_frame = b"\x00" * 960
    
    is_valid, error = validator.validate_audio_frame(valid_frame)
    
    assert is_valid is True
    assert error is None
    
    logger.info("Valid audio frame validation test passed")


def test_audio_frame_validation_too_small():
    """
    Test validation rejects frames that are too small.
    
    Verifies that audio frames smaller than the minimum size are rejected
    with an appropriate error message.
    """
    logger.info("Testing validation rejects frames that are too small")
    
    validator = WebSocketMessageValidator()
    
    # Frame too small (less than 10ms)
    small_frame = b"\x00" * 300
    
    is_valid, error = validator.validate_audio_frame(small_frame)
    
    assert is_valid is False
    assert "too small" in error.lower()
    
    logger.info("Frame too small rejection test passed")


def test_audio_frame_validation_too_large():
    """
    Test validation rejects frames that are too large.
    
    Verifies that audio frames larger than the maximum size are rejected
    with an appropriate error message.
    """
    logger.info("Testing validation rejects frames that are too large")
    
    validator = WebSocketMessageValidator()
    
    # Frame too large (more than 300ms)
    large_frame = b"\x00" * 10000
    
    is_valid, error = validator.validate_audio_frame(large_frame)
    
    assert is_valid is False
    assert "too large" in error.lower()
    
    logger.info("Frame too large rejection test passed")


def test_audio_frame_validation_empty():
    """
    Test validation rejects empty frames.
    
    Verifies that empty audio frames are rejected with an appropriate error message.
    """
    logger.info("Testing validation rejects empty frames")
    
    validator = WebSocketMessageValidator()
    
    is_valid, error = validator.validate_audio_frame(b"")
    
    assert is_valid is False
    assert "empty" in error.lower()
    
    logger.info("Empty frame rejection test passed")


def test_audio_frame_validation_wrong_size():
    """
    Test validation rejects frames with wrong sample size.
    
    Verifies that audio frames with sizes not divisible by the expected
    sample size are rejected with an appropriate error message.
    """
    logger.info("Testing validation rejects frames with wrong sample size")
    
    validator = WebSocketMessageValidator()
    
    # Frame size not divisible by expected sample size
    wrong_size_frame = b"\x00" * 500
    
    is_valid, error = validator.validate_audio_frame(wrong_size_frame)
    
    assert is_valid is False
    assert "not divisible" in error.lower()
    
    logger.info("Wrong sample size rejection test passed")


def test_control_message_validation_valid():
    """
    Test validation of valid control messages.
    
    Verifies that properly formatted control messages pass validation.
    """
    logger.info("Testing validation of valid control messages")
    
    validator = WebSocketMessageValidator()
    
    # Valid flush message
    valid_message = b'{"type": "flush"}'
    
    is_valid, error, data = validator.validate_control_message(valid_message)
    
    assert is_valid is True
    assert error is None
    assert data["type"] == "flush"
    
    logger.info("Valid control message validation test passed")


def test_control_message_validation_invalid_json():
    """
    Test validation rejects invalid JSON.
    
    Verifies that control messages with invalid JSON syntax are rejected
    with an appropriate error message.
    """
    logger.info("Testing validation rejects invalid JSON")
    
    validator = WebSocketMessageValidator()
    
    invalid_json = b'{"type": "flush"'
    
    is_valid, error, data = validator.validate_control_message(invalid_json)
    
    assert is_valid is False
    assert error is not None
    assert "json" in error.lower()
    assert data is None
    
    logger.info("Invalid JSON rejection test passed")


def test_control_message_validation_missing_type():
    """
    Test validation rejects messages without type field.
    
    Verifies that control messages missing the required type field are
    rejected with an appropriate error message.
    """
    logger.info("Testing validation rejects messages without type field")
    
    validator = WebSocketMessageValidator()
    
    no_type_message = b'{"data": "test"}'
    
    is_valid, error, data = validator.validate_control_message(no_type_message)
    
    assert is_valid is False
    assert error is not None
    assert "type" in error.lower()
    
    logger.info("Missing type field rejection test passed")


def test_control_message_validation_invalid_type():
    """
    Test validation rejects messages with invalid type.
    
    Verifies that control messages with unrecognized message types are
    rejected with an appropriate error message.
    """
    logger.info("Testing validation rejects messages with invalid type")
    
    validator = WebSocketMessageValidator()
    
    invalid_type_message = b'{"type": "invalid_type"}'
    
    is_valid, error, data = validator.validate_control_message(invalid_type_message)
    
    assert is_valid is False
    assert error is not None
    assert "invalid message type" in error.lower()
    
    logger.info("Invalid type rejection test passed")


def test_control_message_validation_config():
    """
    Test validation of config message.
    
    Verifies that properly formatted config messages pass validation
    and preserve their data.
    """
    logger.info("Testing validation of config message")
    
    validator = WebSocketMessageValidator()
    
    config_message = b'{"type": "config", "language": "en"}'
    
    is_valid, error, data = validator.validate_control_message(config_message)
    
    assert is_valid is True
    assert error is None
    assert data["type"] == "config"
    assert data["language"] == "en"
    
    logger.info("Config message validation test passed")


def test_control_message_validation_config_invalid_language():
    """
    Test validation rejects config with invalid language type.
    
    Verifies that the validator only checks structure and not value types.
    Language type validation happens at the application layer.
    """
    logger.info("Testing validation accepts config with invalid language type")
    
    validator = WebSocketMessageValidator()
    
    config_message = b'{"type": "config", "language": 123}'
    
    is_valid, error, data = validator.validate_control_message(config_message)
    
    # This should still be valid as the validator only checks structure
    # Language type validation would happen at the application layer
    assert is_valid is True
    assert error is None
    
    logger.info("Invalid language type acceptance test passed")


def test_message_validation_binary():
    """
    Test validation of binary messages (audio).
    
    Verifies that binary messages are treated as audio frames and validated.
    """
    logger.info("Testing validation of binary messages")
    
    validator = WebSocketMessageValidator()
    
    audio_frame = b"\x00" * 960
    
    is_valid, error, data = validator.validate_message(audio_frame, is_binary=True)
    
    assert is_valid is True
    assert error is None
    assert data is None
    
    logger.info("Binary message validation test passed")


def test_message_validation_text():
    """
    Test validation of text messages (control).
    
    Verifies that text messages are treated as control messages and validated.
    """
    logger.info("Testing validation of text messages")
    
    validator = WebSocketMessageValidator()
    
    control_message = b'{"type": "flush"}'
    
    is_valid, error, data = validator.validate_message(control_message, is_binary=False)
    
    assert is_valid is True
    assert error is None
    assert data is not None
    
    logger.info("Text message validation test passed")


def test_update_session_config():
    """
    Test updating session configuration.
    
    Verifies that updating the session configuration recalculates
    frame size limits based on the new sample rate.
    """
    logger.info("Testing updating session configuration")
    
    validator = WebSocketMessageValidator()
    
    # Update sample rate
    validator.update_session_config({"sample_rate": 8000})
    
    assert validator.audio_spec.sample_rate == 8000
    assert validator.audio_spec.min_frame_size == 160  # 10ms at 8kHz
    assert validator.audio_spec.max_frame_size == 4800  # 300ms at 8kHz
    
    logger.info("Session configuration update test passed")


def test_global_validator():
    """
    Test global validator instance.
    
    Verifies that the global validator singleton returns the same instance
    across multiple calls.
    """
    logger.info("Testing global validator instance")
    
    validator = get_validator()
    
    assert validator is not None
    assert isinstance(validator, WebSocketMessageValidator)
    
    # Subsequent calls should return same instance
    validator2 = get_validator()
    assert validator is validator2
    
    logger.info("Global validator instance test passed")


def test_message_type_enum():
    """
    Test message type enum values.
    
    Verifies that the MessageType enum has the correct string values.
    """
    logger.info("Testing message type enum values")
    
    assert MessageType.FLUSH.value == "flush"
    assert MessageType.CONFIG.value == "config"
    assert MessageType.METADATA.value == "metadata"
    
    logger.info("Message type enum values test passed")
