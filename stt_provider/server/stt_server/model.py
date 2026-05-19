"""
Whisper model wrapper for speech transcription.

This module provides functions for loading and using the Whisper model
for audio transcription, including support for file-based and array-based
audio input, language overrides, and model warmup.
"""
import logging
from functools import lru_cache
from typing import Any, Optional

import numpy as np
from faster_whisper import WhisperModel

from stt_server.config import settings

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def get_whisper_model() -> WhisperModel:
    """
    Get the cached Whisper model instance.
    
    Loads and caches the Whisper model using configuration settings.
    The model is cached to avoid reloading on each transcription request.
    
    Returns:
        WhisperModel instance configured with settings
    """
    logger.info(f"Loading Whisper model: {settings.whisper_model_size}")
    return WhisperModel(
        settings.whisper_model_size,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )


def _transcription_language(language_override: Optional[str] = None) -> Optional[str]:
    """
    Determine the transcription language.
    
    Returns the language to use for transcription, preferring the override
    parameter over the default setting. Returns None for "auto" language.
    
    Args:
        language_override: Language code override (e.g., "en", "es")
        
    Returns:
        Language code or None for auto-detection
    """
    requested_language = language_override or settings.transcription_language
    return None if requested_language == "auto" else requested_language


def _join_segment_text(segments: Any) -> str:
    """
    Join text from transcription segments.
    
    Concatenates the text from all segments, stripping whitespace and
    filtering out empty segments.
    
    Args:
        segments: Whisper transcription segments
        
    Returns:
        Joined transcription text
    """
    text_parts = []

    for segment in segments:
        clean_text = segment.text.strip()
        if clean_text:
            text_parts.append(clean_text)

    return " ".join(text_parts).strip()


def _normalize_decoder_options_for_whisper(options: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize decoder options for Whisper model.
    
    Converts list-based hotwords to comma-separated string format
    expected by the Whisper model.
    
    Args:
        options: Raw decoder options dictionary
        
    Returns:
        Normalized decoder options dictionary
    """
    normalized = dict(options)
    hotwords = normalized.get("hotwords")

    if isinstance(hotwords, list):
        normalized["hotwords"] = ", ".join(str(word) for word in hotwords)

    return normalized


def _transcribe_source(
    source: str | np.ndarray,
    language_override: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Transcribe audio from a file path or numpy array.
    
    Internal function that performs the actual transcription using the
    Whisper model with configured decoder options.
    
    Args:
        source: File path or numpy array containing audio data
        language_override: Language code override (e.g., "en", "es")
        **kwargs: Additional decoder options for Whisper
        
    Returns:
        Transcribed text
    """
    model = get_whisper_model()

    transcribe_kwargs: dict[str, Any] = {
        "beam_size": 1,
        "vad_filter": False,
        "language": _transcription_language(language_override),
        "condition_on_previous_text": False,
    }
    transcribe_kwargs.update(kwargs)
    transcribe_kwargs = _normalize_decoder_options_for_whisper(transcribe_kwargs)

    segments, _info = model.transcribe(source, **transcribe_kwargs)

    return _join_segment_text(segments)


def transcribe_array(
    audio: np.ndarray,
    language_override: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Transcribe audio from a numpy array.
    
    Converts the audio array to float32 format if necessary and
    transcribes it using the Whisper model.
    
    Args:
        audio: Numpy array containing audio data
        language_override: Language code override (e.g., "en", "es")
        **kwargs: Additional decoder options for Whisper
        
    Returns:
        Transcribed text
    """
    if audio.dtype != np.float32:
        audio = audio.astype(np.float32)

    return _transcribe_source(audio, language_override=language_override, **kwargs)


def transcribe_pcm16_file(
    path: str,
    language_override: Optional[str] = None,
    **kwargs: Any,
) -> str:
    """
    Transcribe audio from a PCM16 file.
    
    Transcribes audio from the specified file path using the Whisper model.
    
    Args:
        path: Path to the audio file
        language_override: Language code override (e.g., "en", "es")
        **kwargs: Additional decoder options for Whisper
        
    Returns:
        Transcribed text
    """
    return _transcribe_source(path, language_override=language_override, **kwargs)


def warmup_model() -> None:
    """
    Warm up the Whisper model by loading it and running a test transcription.
    
    Loads the model into memory and runs a small test transcription to
    ensure the model is ready for production use. This should be called
    during application startup to reduce latency on first real request.
    """
    logger.info("Warming up Whisper model...")
    get_whisper_model()
    transcribe_array(np.zeros(settings.sample_rate, dtype=np.float32), language_override="en")
    logger.info("Whisper model warmup complete")
