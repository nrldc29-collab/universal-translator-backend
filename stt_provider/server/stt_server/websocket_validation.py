"""
WebSocket message validation module.

This module provides functionality for validating WebSocket messages for streaming
speech-to-text, including audio frame validation and control message validation
with configurable audio format specifications.
"""
import json
import logging
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class MessageType(StrEnum):
    """
    WebSocket message types.
    
    Defines the valid message types for WebSocket communication.
    
    Attributes:
        FLUSH: Flush buffer message
        CONFIG: Configuration update message
        METADATA: Metadata message
        AUDIO: Audio data message
    """
    FLUSH = "flush"
    CONFIG = "config"
    METADATA = "metadata"
    AUDIO = "audio"


@dataclass
class AudioFormatSpec:
    """
    Specification for valid audio formats.
    
    Defines the expected audio format parameters for validation,
    including sample rate, channels, bit depth, encoding, and frame size limits.
    
    Attributes:
        sample_rate: Audio sample rate in Hz (default: 16000)
        channels: Number of audio channels (default: 1)
        bit_depth: Audio bit depth in bits (default: 16)
        encoding: Audio encoding format (default: "pcm_s16le")
        min_frame_size: Minimum frame size in bytes (default: 320, 10ms at 16kHz)
        max_frame_size: Maximum frame size in bytes (default: 9600, 300ms at 16kHz)
    """
    sample_rate: int = 16000
    channels: int = 1
    bit_depth: int = 16
    encoding: str = "pcm_s16le"
    min_frame_size: int = 320  # 10ms at 16kHz
    max_frame_size: int = 9600  # 300ms at 16kHz


class WebSocketMessageValidator:
    """
    Validate WebSocket messages for streaming STT.
    
    Provides validation for both binary audio frames and JSON control messages,
    with configurable audio format specifications and session configuration.
    
    Attributes:
        audio_spec: Audio format specification for validation
        _session_config: Current session configuration
    """
    
    def __init__(self, audio_spec: Optional[AudioFormatSpec] = None) -> None:
        """
        Initialize the WebSocket message validator.
        
        Args:
            audio_spec: Optional audio format specification
        """
        self.audio_spec = audio_spec or AudioFormatSpec()
        self._session_config: Dict[str, Any] = {}
    
    def validate_audio_frame(self, data: bytes) -> Tuple[bool, Optional[str]]:
        """
        Validate an audio frame.
        
        Checks that the audio frame is not empty, falls within size limits,
        and has a size divisible by the expected sample size.
        
        Args:
            data: Audio frame bytes to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not data:
            return False, "Audio frame cannot be empty"
        
        frame_size = len(data)
        
        if frame_size < self.audio_spec.min_frame_size:
            return False, f"Audio frame too small: {frame_size} bytes (minimum {self.audio_spec.min_frame_size})"
        
        if frame_size > self.audio_spec.max_frame_size:
            return False, f"Audio frame too large: {frame_size} bytes (maximum {self.audio_spec.max_frame_size})"
        
        # Check if frame size is divisible by expected sample size
        expected_sample_size = self.audio_spec.sample_rate * (self.audio_spec.bit_depth // 8) * self.audio_spec.channels
        if frame_size % expected_sample_size != 0:
            return False, f"Audio frame size {frame_size} not divisible by expected sample size {expected_sample_size}"
        
        logger.debug(f"Audio frame validated: {frame_size} bytes")
        return True, None
    
    def validate_control_message(
        self, message: bytes
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a control message (JSON).
        
        Parses and validates JSON control messages, checking for required
        fields and valid message types.
        
        Args:
            message: The message bytes to validate
            
        Returns:
            Tuple of (is_valid, error_message, parsed_data)
        """
        try:
            message_data = json.loads(message.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            return False, f"Invalid JSON: {str(e)}", None
        
        if not isinstance(message_data, dict):
            return False, "Message must be a JSON object", None
        
        msg_type = message_data.get("type")
        
        if not msg_type:
            return False, "Message missing 'type' field", None
        
        try:
            message_type = MessageType(msg_type.lower())
        except ValueError:
            return False, f"Invalid message type: {msg_type}. Valid types: {[t.value for t in MessageType]}", None
        
        # Validate specific message types
        if message_type == MessageType.FLUSH:
            # Flush messages have no additional required fields
            pass
        elif message_type == MessageType.CONFIG:
            # Config messages must have valid config
            if "language" in message_data and not isinstance(message_data["language"], str):
                return False, "Config 'language' must be a string", None
        
        logger.debug(f"Control message validated: type={message_type}")
        return True, None, message_data
    
    def validate_message(
        self, message: bytes, is_binary: bool
    ) -> Tuple[bool, Optional[str], Optional[Dict[str, Any]]]:
        """
        Validate a WebSocket message (either audio or control).
        
        Routes the message to the appropriate validation function based
        on whether it is binary (audio) or text (control).
        
        Args:
            message: The message bytes to validate
            is_binary: Whether the message is binary (audio) or text (control)
            
        Returns:
            Tuple of (is_valid, error_message, parsed_data)
        """
        if is_binary:
            is_valid, error = self.validate_audio_frame(message)
            return is_valid, error, None
        else:
            return self.validate_control_message(message)
    
    def update_session_config(self, config: dict) -> None:
        """
        Update session configuration for validation.
        
        Updates the session configuration and adjusts audio format
        specifications if sample rate is provided.
        
        Args:
            config: Configuration dictionary
        """
        self._session_config.update(config)
        
        # Update audio spec if sample rate provided
        if "sample_rate" in config:
            self.audio_spec.sample_rate = config["sample_rate"]
            self.audio_spec.min_frame_size = self.audio_spec.sample_rate * 2  # 10ms
            self.audio_spec.max_frame_size = self.audio_spec.sample_rate * 60  # 300ms
            logger.info(f"Updated audio spec with sample_rate={config['sample_rate']}")


# Global validator instance
_global_validator = WebSocketMessageValidator()


def get_validator() -> WebSocketMessageValidator:
    """
    Get the global WebSocket message validator.
    
    Returns the singleton validator instance for use across the application.
    
    Returns:
        Global WebSocketMessageValidator instance
    """
    return _global_validator
