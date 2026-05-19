"""
Tests for audio validation functionality.

This module tests the AudioValidator class which validates audio data for
the STT service, including PCM16 audio validation, file upload validation,
and custom configuration support. Tests verify that invalid audio is rejected
based on sample rate, channels, duration, silence, clipping, and file size.

Run tests:
    pytest server/tests/test_audio_validation.py

Purpose:
This ensures that the audio validation layer properly rejects malformed or
malicious audio data before it reaches the transcription backend, protecting
against resource exhaustion attacks and ensuring quality audio input.
"""
import logging

import numpy as np
import pytest

from stt_server.audio_validation import (
    AudioValidator,
    AudioValidationResult,
    get_audio_validator,
)

logger = logging.getLogger(__name__)


def test_audio_validator_defaults():
    """
    Test default audio validator configuration.
    
    Verifies that the AudioValidator is initialized with sensible defaults
    for sample rates, channels, and duration limits.
    """
    logger.info("Testing default audio validator configuration")
    
    validator = AudioValidator()
    
    assert validator.allowed_sample_rates == [16000]
    assert validator.allowed_channels == [1]
    assert validator.max_duration_seconds == 3600.0
    assert validator.min_duration_seconds == 0.1
    
    logger.info("Default configuration test passed")


def test_validate_pcm16_valid():
    """
    Test validation of valid PCM16 audio.
    
    Verifies that properly formatted PCM16 audio at the correct sample rate
    and channel count passes validation.
    """
    logger.info("Testing valid PCM16 audio validation")
    
    validator = AudioValidator()
    
    # Generate valid PCM16 audio (1 second at 16kHz)
    audio_data = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is True
    assert result.error_message is None
    assert result.sample_rate == 16000
    assert result.channels == 1
    assert result.duration_seconds == 1.0
    
    logger.info("Valid PCM16 audio test passed")


def test_validate_pcm16_invalid_sample_rate():
    """
    Test validation rejects unsupported sample rates.
    
    Verifies that audio with an unsupported sample rate is rejected
    with an appropriate error message.
    """
    logger.info("Testing invalid sample rate rejection")
    
    validator = AudioValidator()
    
    audio_data = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=8000, channels=1)
    
    assert result.is_valid is False
    assert "sample rate" in result.error_message.lower()
    
    logger.info("Invalid sample rate rejection test passed")


def test_validate_pcm16_invalid_channels():
    """
    Test validation rejects unsupported channel counts.
    
    Verifies that audio with an unsupported channel count is rejected
    with an appropriate error message.
    """
    logger.info("Testing invalid channel count rejection")
    
    validator = AudioValidator()
    
    audio_data = np.random.randint(-32768, 32767, size=16000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=2)
    
    assert result.is_valid is False
    assert "channel" in result.error_message.lower()
    
    logger.info("Invalid channel count rejection test passed")


def test_validate_pcm16_empty():
    """
    Test validation rejects empty audio.
    
    Verifies that empty audio data is rejected with an appropriate error message.
    """
    logger.info("Testing empty audio rejection")
    
    validator = AudioValidator()
    
    result = validator.validate_pcm16(b"", sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "empty" in result.error_message.lower()
    
    logger.info("Empty audio rejection test passed")


def test_validate_pcm16_too_short():
    """
    Test validation rejects audio that's too short.
    
    Verifies that audio shorter than the minimum duration is rejected
    with an appropriate error message.
    """
    logger.info("Testing too-short audio rejection")
    
    validator = AudioValidator(min_duration_seconds=1.0)
    
    # 0.5 seconds of audio
    audio_data = np.random.randint(-32768, 32767, size=8000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "too short" in result.error_message.lower()
    
    logger.info("Too-short audio rejection test passed")


def test_validate_pcm16_too_long():
    """
    Test validation rejects audio that's too long.
    
    Verifies that audio exceeding the maximum duration is rejected
    with an appropriate error message.
    """
    logger.info("Testing too-long audio rejection")
    
    validator = AudioValidator(max_duration_seconds=10.0)
    
    # 20 seconds of audio
    audio_data = np.random.randint(-32768, 32767, size=320000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "exceeds maximum" in result.error_message.lower()
    
    logger.info("Too-long audio rejection test passed")


def test_validate_pcm16_silence():
    """
    Test validation rejects audio that's all silence (zeros).
    
    Verifies that audio with no signal (all zeros) is rejected
    with an appropriate error message.
    """
    logger.info("Testing silence rejection")
    
    validator = AudioValidator()
    
    # All zeros
    audio_data = np.zeros(16000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "silence" in result.error_message.lower()
    
    logger.info("Silence rejection test passed")


def test_validate_pcm16_clipped():
    """
    Test validation rejects audio that's clipped (max values).
    
    Verifies that audio with clipping at the maximum value is rejected
    with an appropriate error message.
    """
    logger.info("Testing clipped audio rejection (max)")
    
    validator = AudioValidator()
    
    # All max values
    audio_data = np.full(16000, 32767, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "clipped" in result.error_message.lower()
    
    logger.info("Clipped audio rejection test passed (max)")


def test_validate_pcm16_clipped_negative():
    """
    Test validation rejects audio that's clipped (min values).
    
    Verifies that audio with clipping at the minimum value is rejected
    with an appropriate error message.
    """
    logger.info("Testing clipped audio rejection (min)")
    
    validator = AudioValidator()
    
    # All min values
    audio_data = np.full(16000, -32768, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=1)
    
    assert result.is_valid is False
    assert "clipped" in result.error_message.lower()
    
    logger.info("Clipped audio rejection test passed (min)")


def test_validate_file_upload_valid():
    """
    Test validation of valid file upload.
    
    Verifies that a file upload within size limits passes validation.
    """
    logger.info("Testing valid file upload validation")
    
    validator = AudioValidator()
    
    result = validator.validate_file_upload(file_size=1024 * 1024)  # 1MB
    
    assert result.is_valid is True
    assert result.error_message is None
    
    logger.info("Valid file upload test passed")


def test_validate_file_upload_empty():
    """
    Test validation rejects empty file.
    
    Verifies that an empty file upload is rejected with an appropriate error message.
    """
    logger.info("Testing empty file rejection")
    
    validator = AudioValidator()
    
    result = validator.validate_file_upload(file_size=0)
    
    assert result.is_valid is False
    assert "empty" in result.error_message.lower()
    
    logger.info("Empty file rejection test passed")


def test_validate_file_upload_too_large():
    """
    Test validation rejects file that's too large.
    
    Verifies that a file upload exceeding size limits is rejected
    with an appropriate error message.
    """
    logger.info("Testing too-large file rejection")
    
    validator = AudioValidator(max_file_size=10 * 1024 * 1024)  # 10MB
    
    result = validator.validate_file_upload(file_size=20 * 1024 * 1024)  # 20MB
    
    assert result.is_valid is False
    assert "exceeds maximum" in result.error_message.lower()
    
    logger.info("Too-large file rejection test passed")


def test_global_audio_validator():
    """
    Test global audio validator instance.
    
    Verifies that the global validator singleton returns the same instance
    across multiple calls.
    """
    logger.info("Testing global audio validator singleton")
    
    validator = get_audio_validator()
    
    assert validator is not None
    assert isinstance(validator, AudioValidator)
    
    # Subsequent calls should return same instance
    validator2 = get_audio_validator()
    assert validator is validator2
    
    logger.info("Global validator singleton test passed")


def test_audio_validation_result_fields():
    """
    Test AudioValidationResult dataclass fields.
    
    Verifies that the AudioValidationResult dataclass correctly stores
    validation result information.
    """
    logger.info("Testing AudioValidationResult fields")
    
    result = AudioValidationResult(
        is_valid=True,
        sample_rate=16000,
        channels=1,
        duration_seconds=10.5,
    )
    
    assert result.is_valid is True
    assert result.sample_rate == 16000
    assert result.channels == 1
    assert result.duration_seconds == 10.5
    assert result.error_message is None
    
    logger.info("AudioValidationResult fields test passed")


def test_validate_pcm16_custom_allowed_rates():
    """
    Test validation with custom allowed sample rates.
    
    Verifies that custom sample rate configurations are properly enforced.
    """
    logger.info("Testing custom allowed sample rates")
    
    validator = AudioValidator(allowed_sample_rates=[8000, 16000, 48000])
    
    # 48000 should be valid
    audio_data = np.random.randint(-32768, 32767, size=48000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=48000, channels=1)
    
    assert result.is_valid is True
    
    logger.info("Custom allowed sample rates test passed")


def test_validate_pcm16_custom_allowed_channels():
    """
    Test validation with custom allowed channels.
    
    Verifies that custom channel configurations are properly enforced.
    """
    logger.info("Testing custom allowed channels")
    
    validator = AudioValidator(allowed_channels=[1, 2])
    
    # Stereo should be valid
    audio_data = np.random.randint(-32768, 32767, size=32000, dtype=np.int16)
    audio_bytes = audio_data.tobytes()
    
    result = validator.validate_pcm16(audio_bytes, sample_rate=16000, channels=2)
    
    assert result.is_valid is True
    
    logger.info("Custom allowed channels test passed")
