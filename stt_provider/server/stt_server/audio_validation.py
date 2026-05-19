"""
Audio validation module for STT processing.

This module provides functionality for validating audio data for speech-to-text
processing, including PCM16 audio validation, file upload size validation, and
checks for sample rate, channels, duration, and audio quality issues.
"""
import logging
import numpy as np
from dataclasses import dataclass
from typing import Optional, List

logger = logging.getLogger(__name__)


@dataclass
class AudioValidationResult:
    """
    Result of audio validation.
    
    Represents the outcome of an audio validation operation, including
    validation status, audio properties, and any error messages.
    
    Attributes:
        is_valid: Whether the audio passed validation
        sample_rate: Sample rate in Hz (if valid)
        channels: Number of audio channels (if valid)
        duration_seconds: Audio duration in seconds (if valid)
        error_message: Error message if validation failed
        snr: Signal-to-noise ratio (optional, not currently calculated)
    """
    is_valid: bool
    sample_rate: Optional[int] = None
    channels: Optional[int] = None
    duration_seconds: Optional[float] = None
    error_message: Optional[str] = None
    snr: Optional[float] = None


class AudioValidator:
    """
    Validate audio data for STT processing.
    
    Provides validation for PCM16 audio data and file uploads, checking
    sample rate, channels, duration, file size, and audio quality issues
    like silence, clipping, and invalid values.
    
    Attributes:
        allowed_sample_rates: List of allowed sample rates in Hz
        allowed_channels: List of allowed channel counts
        max_duration_seconds: Maximum allowed audio duration in seconds
        min_duration_seconds: Minimum allowed audio duration in seconds
        max_file_size: Maximum allowed file size in bytes
    """
    
    def __init__(
        self,
        allowed_sample_rates: Optional[List[int]] = None,
        allowed_channels: Optional[List[int]] = None,
        max_duration_seconds: float = 3600.0,
        min_duration_seconds: float = 0.1,
        max_file_size: int = 100 * 1024 * 1024,
    ) -> None:
        """
        Initialize the audio validator.
        
        Args:
            allowed_sample_rates: List of allowed sample rates (default: [16000])
            allowed_channels: List of allowed channel counts (default: [1])
            max_duration_seconds: Maximum audio duration in seconds (default: 3600)
            min_duration_seconds: Minimum audio duration in seconds (default: 0.1)
            max_file_size: Maximum file size in bytes (default: 100MB)
        """
        self.allowed_sample_rates = allowed_sample_rates or [16000]
        self.allowed_channels = allowed_channels or [1]
        self.max_duration_seconds = max_duration_seconds
        self.min_duration_seconds = min_duration_seconds
        self.max_file_size = max_file_size
        logger.info(f"AudioValidator initialized with sample_rates={self.allowed_sample_rates}, channels={self.allowed_channels}")
    
    def validate_pcm16(
        self,
        audio_data: bytes,
        sample_rate: int,
        channels: int,
    ) -> AudioValidationResult:
        """
        Validate PCM16 audio data.
        
        Performs comprehensive validation of PCM16 audio data including sample rate,
        channel count, duration, data consistency, and audio quality checks.
        
        Args:
            audio_data: The audio bytes to validate
            sample_rate: Sample rate in Hz
            channels: Number of audio channels
            
        Returns:
            AudioValidationResult with validation status and details
        """
        # Check sample rate
        if sample_rate not in self.allowed_sample_rates:
            logger.warning(f"Invalid sample rate: {sample_rate} (allowed: {self.allowed_sample_rates})")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"Sample rate {sample_rate} not allowed. Allowed: {self.allowed_sample_rates}",
            )
        
        # Check channels
        if channels not in self.allowed_channels:
            logger.warning(f"Invalid channel count: {channels} (allowed: {self.allowed_channels})")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"Channel count {channels} not allowed. Allowed: {self.allowed_channels}",
            )
        
        # Check if data is empty
        if not audio_data:
            logger.warning("Audio data is empty")
            return AudioValidationResult(
                is_valid=False,
                error_message="Audio data is empty",
            )
        
        # Calculate duration
        bytes_per_sample = 2  # PCM16 = 2 bytes per sample
        samples = len(audio_data) // bytes_per_sample
        duration_seconds = samples / (sample_rate * channels)
        
        # Check minimum duration
        if duration_seconds < self.min_duration_seconds:
            logger.warning(f"Audio duration too short: {duration_seconds:.3f}s (minimum: {self.min_duration_seconds}s)")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"Audio duration {duration_seconds:.3f}s is too short (minimum {self.min_duration_seconds}s)",
            )
        
        # Check maximum duration
        if duration_seconds > self.max_duration_seconds:
            logger.warning(f"Audio duration too long: {duration_seconds:.3f}s (maximum: {self.max_duration_seconds}s)")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"Audio duration {duration_seconds:.3f}s exceeds maximum {self.max_duration_seconds}s",
            )
        
        # Check if data length is consistent with sample rate and channels
        expected_bytes = int(duration_seconds * sample_rate * channels * bytes_per_sample)
        if len(audio_data) != expected_bytes:
            # Allow small rounding differences
            if abs(len(audio_data) - expected_bytes) > sample_rate * channels:
                logger.warning(f"Audio data length inconsistent: {len(audio_data)} bytes vs expected {expected_bytes} bytes")
                return AudioValidationResult(
                    is_valid=False,
                    error_message=f"Audio data length {len(audio_data)} bytes inconsistent with expected {expected_bytes} bytes for {duration_seconds:.3f}s at {sample_rate}Hz",
                )
        
        # Try to decode as numpy array to verify it's valid PCM16
        try:
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            
            # Check for potential issues
            if len(audio_array) == 0:
                logger.warning("Audio data decodes to empty array")
                return AudioValidationResult(
                    is_valid=False,
                    error_message="Audio data decodes to empty array",
                )
            
            # Check for clipping (all zeros or all max values)
            if np.all(audio_array == 0):
                logger.warning("Audio data contains only silence (all zeros)")
                return AudioValidationResult(
                    is_valid=False,
                    error_message="Audio data contains only silence (all zeros)",
                )
            
            if np.all(audio_array == 32767) or np.all(audio_array == -32768):
                logger.warning("Audio data appears to be clipped (constant max/min values)")
                return AudioValidationResult(
                    is_valid=False,
                    error_message="Audio data appears to be clipped (constant max/min values)",
                )
            
            # Check for NaN or inf
            if np.any(np.isnan(audio_array.astype(float))) or np.any(np.isinf(audio_array.astype(float))):
                logger.warning("Audio data contains invalid values (NaN or Inf)")
                return AudioValidationResult(
                    is_valid=False,
                    error_message="Audio data contains invalid values (NaN or Inf)",
                )
            
        except Exception as e:
            logger.error(f"Failed to decode audio as PCM16: {e}")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"Failed to decode audio as PCM16: {str(e)}",
            )
        
        logger.debug(f"Audio validation passed: {duration_seconds:.3f}s at {sample_rate}Hz, {channels} channels")
        return AudioValidationResult(
            is_valid=True,
            sample_rate=sample_rate,
            channels=channels,
            duration_seconds=duration_seconds,
        )
    
    def validate_file_upload(self, file_size: int, max_file_size: int = 100 * 1024 * 1024) -> AudioValidationResult:
        """
        Validate file upload size.
        
        Checks that the file size is non-zero and does not exceed the maximum limit.
        
        Args:
            file_size: Size of the file in bytes
            max_file_size: Maximum allowed file size in bytes (default: 100MB)
            
        Returns:
            AudioValidationResult with validation status
        """
        if file_size == 0:
            logger.warning("File is empty")
            return AudioValidationResult(
                is_valid=False,
                error_message="File is empty",
            )
        
        if file_size > max_file_size:
            logger.warning(f"File size exceeds maximum: {file_size} bytes (maximum: {max_file_size} bytes)")
            return AudioValidationResult(
                is_valid=False,
                error_message=f"File size {file_size} bytes exceeds maximum {max_file_size} bytes",
            )
        
        logger.debug(f"File size validation passed: {file_size} bytes")
        return AudioValidationResult(is_valid=True)


# Global validator instance
_global_audio_validator = AudioValidator()


def get_audio_validator() -> AudioValidator:
    """
    Get the global audio validator.
    
    Returns the singleton validator instance for use across the application.
    
    Returns:
        Global AudioValidator instance
    """
    return _global_audio_validator
