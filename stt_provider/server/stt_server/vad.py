"""
Voice Activity Detection (VAD) module.

This module provides a wrapper around the WebRTC VAD library for detecting
speech in audio frames. It supports configurable sample rates, frame durations,
and VAD aggressiveness modes.
"""
import logging
import warnings
from typing import List

# Suppress pkg_resources deprecation warning from webrtcvad
with warnings.catch_warnings():
    warnings.filterwarnings(
        "ignore",
        message="pkg_resources is deprecated as an API.*",
        category=UserWarning,
    )
    import webrtcvad

logger = logging.getLogger(__name__)


class VoiceActivityDetector:
    """
    Voice Activity Detector using WebRTC VAD.
    
    This class provides methods to detect speech in PCM16 audio frames
    and split audio into frames compatible with the VAD model.
    
    Attributes:
        sample_rate: Audio sample rate in Hz (default: 16000)
        frame_ms: Frame duration in milliseconds (must be 10, 20, or 30)
        frame_bytes: Number of bytes per frame
        vad: WebRTC VAD instance
    """
    
    def __init__(
        self,
        sample_rate: int = 16000,
        frame_ms: int = 30,
        mode: int = 3,
    ):
        """
        Initialize the Voice Activity Detector.
        
        Args:
            sample_rate: Audio sample rate in Hz (default: 16000)
            frame_ms: Frame duration in milliseconds (must be 10, 20, or 30)
            mode: VAD aggressiveness mode (0-3, where 3 is most aggressive)
            
        Raises:
            ValueError: If frame_ms is not 10, 20, or 30
        """
        if frame_ms not in (10, 20, 30):
            raise ValueError(
                f"frame_ms must be 10, 20, or 30, got {frame_ms}. "
                f"Frame duration must match the VAD model's expected input."
            )

        if mode not in (0, 1, 2, 3):
            raise ValueError(
                f"mode must be 0, 1, 2, or 3, got {mode}. "
                f"VAD mode controls aggressiveness (0=least, 3=most)."
            )

        self.sample_rate = sample_rate
        self.frame_ms = frame_ms
        self.frame_bytes = int(sample_rate * frame_ms / 1000) * 2
        self.vad = webrtcvad.Vad(mode)
        
        logger.debug(
            f"VAD initialized: sample_rate={sample_rate}, frame_ms={frame_ms}, "
            f"frame_bytes={self.frame_bytes}, mode={mode}"
        )

    def is_speech(self, pcm16_frame: bytes) -> bool:
        """
        Detect if a PCM16 audio frame contains speech.
        
        Args:
            pcm16_frame: PCM16 audio frame bytes
            
        Returns:
            True if the frame contains speech, False otherwise
        """
        if len(pcm16_frame) != self.frame_bytes:
            logger.warning(
                f"Frame size mismatch: expected {self.frame_bytes} bytes, "
                f"got {len(pcm16_frame)} bytes"
            )
            return False

        return self.vad.is_speech(pcm16_frame, self.sample_rate)

    def split_frames(self, pcm16_audio: bytes) -> List[bytes]:
        """
        Split PCM16 audio into frames compatible with VAD.
        
        Args:
            pcm16_audio: PCM16 audio bytes
            
        Returns:
            List of audio frames, each of size frame_bytes
        """
        frames = []

        for start in range(0, len(pcm16_audio), self.frame_bytes):
            frame = pcm16_audio[start:start + self.frame_bytes]

            if len(frame) == self.frame_bytes:
                frames.append(frame)
            else:
                # Discard incomplete final frame
                logger.debug(f"Discarding incomplete final frame of {len(frame)} bytes")

        logger.debug(f"Split {len(pcm16_audio)} bytes into {len(frames)} frames")
        return frames
