"""
Streaming transcription module for real-time audio processing.

This module provides streaming transcription capabilities with voice activity detection (VAD),
audio buffering, and support for both Triton and Whisper backends. It handles audio frame
processing, speech segment detection, and emission of partial and final transcripts.

Classes:
    TranscriptEvent: Data class representing a transcript event.
    StreamingTranscriptionSession: Manages a streaming transcription session with VAD and buffering.

Functions:
    pcm16le_to_float32: Convert PCM16 audio bytes to float32 numpy array.
    build_streaming_backend: Build the appropriate streaming backend based on configuration.

Usage:
    Create a StreamingTranscriptionSession instance and use receive_audio() to process
    incoming audio frames and yield transcript events.
"""
import asyncio
import logging
import os
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any, Optional
from uuid import UUID

import numpy as np

# Optional Triton backend import
try:
    from stt_server.backends.triton import TritonStreamingClient
    TRITON_AVAILABLE = True
except ImportError:
    TRITON_AVAILABLE = False
    TritonStreamingClient = None

from stt_server.config import settings
from stt_server.model import WhisperModel, transcribe_array
from stt_server.model_registry import validate_model_id
from stt_server.speaker_identity_audit import audit_speaker_identity_match
from stt_server.vad import VoiceActivityDetector

logger = logging.getLogger(__name__)


def pcm16le_to_float32(audio_bytes: bytes) -> np.ndarray:
    """
    Convert PCM16 little-endian audio bytes to float32 numpy array.
    
    Args:
        audio_bytes: PCM16 audio data in little-endian format
        
    Returns:
        Normalized float32 numpy array with values in range [-1.0, 1.0]
    """
    return np.frombuffer(audio_bytes, dtype=np.int16).astype(np.float32) / 32768.0


def build_streaming_backend() -> TritonStreamingClient | WhisperModel:
    """
    Build the appropriate streaming backend based on configuration.
    
    Returns:
        TritonStreamingClient if STT_BACKEND=triton, otherwise WhisperModel
    """
    backend = os.getenv("STT_BACKEND", "whisper")

    if backend == "triton":
        return TritonStreamingClient(
            grpc_url=os.environ["TRITON_GRPC_URL"],
            asr_model=os.environ["TRITON_ASR_MODEL"],
            diarization_model=os.environ["TRITON_DIARIZATION_MODEL"],
            timeout_ms=int(os.getenv("TRITON_REQUEST_TIMEOUT_MS", "5000")),
        )

    return WhisperModel()


@dataclass
class TranscriptEvent:
    """
    Represents a transcript event from streaming transcription.
    
    Attributes:
        type: Event type (e.g., "transcript", "error")
        text: Transcribed text
        is_final: Whether this transcript is final (True) or partial (False)
        words: List of word-level timestamps and metadata
    """
    type: str
    text: str
    is_final: bool = False
    words: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class StreamingTranscriptionSession:
    """
    Manages a streaming transcription session with VAD and buffering.
    
    This class handles audio frame processing, voice activity detection,
    buffering of speech segments, and emission of partial and final transcripts.
    """
    
    # Configuration
    language: Optional[str] = None
    decoder_options: dict[str, Any] = field(default_factory=dict)
    model_id: Optional[str] = None
    backend: TritonStreamingClient | WhisperModel | None = None

    # Voice Activity Detection
    vad: VoiceActivityDetector = field(
        default_factory=lambda: VoiceActivityDetector(
            sample_rate=settings.sample_rate,
            frame_ms=settings.frame_ms,
            mode=settings.vad_mode,
        )
    )

    # Buffer state
    speech_buffer: bytearray = field(default_factory=bytearray)
    silence_frames: int = 0
    speech_frames: int = 0
    last_partial_text: str = ""

    # VAD thresholds
    min_speech_frames: int = 8
    max_silence_frames: int = 20
    partial_every_frames: int = 35
    max_buffer_size: int = 10 * 1024 * 1024  # 10MB max buffer size
    
    # Session timeout handling
    session_timeout_seconds: float = 300.0  # 5 minutes
    inactivity_timeout_seconds: float = 60.0  # 1 minute
    last_audio_time: float = 0.0
    session_start_time: float = 0.0

    async def receive_audio(self, pcm16_audio: bytes) -> AsyncIterator[TranscriptEvent]:
        """
        Process incoming audio frames and yield transcript events.
        
        Args:
            pcm16_audio: PCM16 audio data bytes
            
        Yields:
            TranscriptEvent objects with partial or final transcripts
        """
        frames = self.vad.split_frames(pcm16_audio)
        
        self._update_audio_timing()

        for frame in frames:
            is_speech = self.vad.is_speech(frame)

            if is_speech:
                if not self._can_add_to_buffer(frame):
                    await self._handle_buffer_overflow()
                    continue

                self.speech_buffer.extend(frame)
                self.speech_frames += 1
                self.silence_frames = 0

                if self.speech_frames >= self.min_speech_frames:
                    if self.speech_frames % self.partial_every_frames == 0:
                        event = await self._transcribe_current_buffer(is_partial=True)
                        if event:
                            yield event
            else:
                self.silence_frames += 1

                if self.speech_frames >= self.min_speech_frames:
                    if self.silence_frames >= self.max_silence_frames:
                        event = await self._transcribe_current_buffer(is_partial=False)
                        self._reset()
                        if event:
                            yield event

    def _update_audio_timing(self) -> None:
        """Update session timing information on audio receipt."""
        if self.last_audio_time == 0.0:
            self.last_audio_time = time.time()
            self.session_start_time = time.time()
        else:
            self.last_audio_time = time.time()

    def _can_add_to_buffer(self, frame: bytes) -> bool:
        """
        Check if frame can be added to buffer without exceeding max size.
        
        Args:
            frame: Audio frame bytes
            
        Returns:
            True if frame can be added, False otherwise
        """
        return len(self.speech_buffer) + len(frame) <= self.max_buffer_size

    async def _handle_buffer_overflow(self) -> None:
        """Handle buffer overflow by forcing final transcription and reset."""
        if self.speech_buffer:
            await self._transcribe_current_buffer(is_partial=False)
            self._reset()

    def _reset(self) -> None:
        """Reset buffer and frame counters for next speech segment."""
        self.speech_buffer.clear()
        self.silence_frames = 0
        self.speech_frames = 0
        self.last_partial_text = ""

    async def _transcribe_current_buffer(self, is_partial: bool) -> Optional[TranscriptEvent]:
        """
        Transcribe the current speech buffer.
        
        Converts the buffered audio to float32 format, validates the model ID
        if specified, performs transcription, and returns a transcript event.
        Skips transcription if the buffer is empty or if the partial text
        hasn't changed.
        
        Args:
            is_partial: Whether this is a partial (True) or final (False) transcription
            
        Returns:
            TranscriptEvent if transcription succeeded, None otherwise
        """
        if not self.speech_buffer:
            return None

        audio_array = pcm16le_to_float32(bytes(self.speech_buffer))
        logger.debug(f"Transcribing buffer: {len(self.speech_buffer)} bytes, {len(audio_array)} samples")
        
        if self.model_id:
            validate_model_id(self.model_id)

        text = await asyncio.to_thread(
            transcribe_array,
            audio_array,
            language_override=self.language,
            **self.decoder_options,
        )
        words = []

        if not text:
            logger.debug("Transcription returned empty text")
            return None

        if is_partial and text == self.last_partial_text:
            logger.debug("Partial text unchanged, skipping event")
            return None

        self.last_partial_text = text

        event = TranscriptEvent(
            type="transcript.final" if not is_partial else "transcript.partial",
            text=text,
            is_final=not is_partial,
            words=words or [],
        )
        
        logger.debug(f"Transcription event: type={'final' if event.is_final else 'partial'}, text={text[:50]}...")

        return event

    async def flush(self) -> AsyncIterator[TranscriptEvent]:
        if not self.speech_buffer:
            return
        event = await self._transcribe_current_buffer(is_partial=False)
        self._reset()
        if event:
            yield event

    def check_session_timeout(self) -> bool:
        """
        Check if the session has timed out.
        
        Returns:
            True if session has exceeded timeout, False otherwise
        """
        if self.session_start_time == 0.0:
            return False

        current_time = time.time()
        session_duration = current_time - self.session_start_time
        inactivity_duration = current_time - self.last_audio_time

        # Check session timeout
        if session_duration > self.session_timeout_seconds:
            logger.warning(f"Session timeout: {session_duration:.1f}s > {self.session_timeout_seconds}s")
            return True

        # Check inactivity timeout
        if inactivity_duration > self.inactivity_timeout_seconds:
            logger.warning(f"Inactivity timeout: {inactivity_duration:.1f}s > {self.inactivity_timeout_seconds}s")
            return True

        return False
