"""
Tests for model transcription and streaming functionality.

This module tests the model transcription and streaming audio processing functionality.
Tests verify audio format conversion, array transcription, segment joining,
and streaming session transcription with decoder options.

Run tests:
    pytest server/tests/test_model_and_streaming.py

Purpose:
This ensures that the transcription model correctly processes audio arrays,
converts between PCM16 and float32 formats, joins text segments, and that
the streaming session properly handles audio bytes with decoder options.
"""
from dataclasses import dataclass
import logging

import numpy as np
import pytest

from stt_server import model, streaming

logger = logging.getLogger(__name__)

CUSTOM_BEAM_SIZE = 4


@dataclass
class FakeSegment:
    """Fake segment for testing transcription output."""
    text: str


class FakeWhisperModel:
    """Fake Whisper model for testing transcription."""
    
    def __init__(self) -> None:
        self.calls = []

    def transcribe(self, source, **kwargs):
        """Fake transcribe method that records calls and returns fake segments."""
        self.calls.append((source, kwargs))
        return [FakeSegment(" hello "), FakeSegment(""), FakeSegment("world ")], object()


def test_transcribe_array_converts_to_float32_and_joins_segments(monkeypatch):
    """
    Test that transcribe array converts to float32 and joins segments.
    
    Verifies that the transcription function converts input audio to float32,
    passes correct decoder options to the model, and joins text segments properly.
    """
    logger.info("Testing transcribe array converts to float32 and joins segments")
    
    fake_model = FakeWhisperModel()
    monkeypatch.setattr(model, "get_whisper_model", lambda: fake_model)

    text = model.transcribe_array(
        np.array([0, 1], dtype=np.int16),
        language_override="auto",
        beam_size=CUSTOM_BEAM_SIZE,
        hotwords=["alpha", "beta"],
    )

    source, kwargs = fake_model.calls[0]
    assert text == "hello world"
    assert source.dtype == np.float32
    assert kwargs["language"] is None
    assert kwargs["beam_size"] == CUSTOM_BEAM_SIZE
    assert kwargs["hotwords"] == "alpha, beta"
    assert kwargs["vad_filter"] is False
    assert kwargs["condition_on_previous_text"] is False
    
    logger.info("Transcribe array test passed")


def test_pcm16le_to_float32_converts_signed_samples():
    """
    Test that PCM16LE to float32 converts signed samples.
    
    Verifies that the audio conversion function correctly converts PCM16
    signed samples to float32 range [-1.0, 1.0).
    """
    logger.info("Testing PCM16LE to float32 converts signed samples")
    
    pcm16 = np.array([-32768, 0, 32767], dtype=np.int16).tobytes()

    audio = streaming.pcm16le_to_float32(pcm16)

    assert audio.dtype == np.float32
    assert audio.tolist() == pytest.approx([-1.0, 0.0, 32767 / 32768])
    
    logger.info("PCM16LE to float32 conversion test passed")


def test_streaming_transcribes_pcm_bytes_as_array(monkeypatch):
    """
    Test that streaming transcribes PCM bytes as array.
    
    Verifies that the streaming session correctly converts PCM bytes to float32
    and passes language and decoder options to the transcription function.
    """
    logger.info("Testing streaming transcribes PCM bytes as array")
    
    captured = {}

    def fake_transcribe_array(audio, language_override=None, **decoder_options):
        captured["audio"] = audio
        captured["language_override"] = language_override
        captured["decoder_options"] = decoder_options
        return "ok"

    monkeypatch.setattr(streaming, "transcribe_array", fake_transcribe_array)

    session = streaming.StreamingTranscriptionSession(
        language="en",
        decoder_options={"beam_size": 2, "temperature": 0.1},
    )
    text = session._transcribe_bytes(np.array([0, 32767], dtype=np.int16).tobytes())

    assert text == "ok"
    assert captured["audio"].dtype == np.float32
    assert captured["audio"].tolist() == pytest.approx([0.0, 32767 / 32768])
    assert captured["language_override"] == "en"
    assert captured["decoder_options"] == {"beam_size": 2, "temperature": 0.1}
    
    logger.info("Streaming PCM bytes transcription test passed")
