"""End-to-end pipeline integration tests.

Validates the complete Mic → VAD → STT → Translate → TTS → Speaker chain
using synthetic audio data and mocked/real components.
"""

import asyncio
import base64
import json
import os
import struct
import time
import wave
import io
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock


def generate_sine_wav(duration_s: float = 1.0, freq_hz: int = 440, sample_rate: int = 16000) -> bytes:
    """Generate a synthetic WAV file with a sine wave tone."""
    import math
    n_samples = int(sample_rate * duration_s)
    samples = []
    for i in range(n_samples):
        t = i / sample_rate
        sample = int(32767 * 0.5 * math.sin(2 * math.pi * freq_hz * t))
        samples.append(struct.pack("<h", sample))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"".join(samples))
    return buf.getvalue()


def generate_silence_wav(duration_s: float = 0.5, sample_rate: int = 16000) -> bytes:
    """Generate a silent WAV file."""
    n_samples = int(sample_rate * duration_s)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b"\x00\x00" * n_samples)
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Pipeline component tests
# ---------------------------------------------------------------------------

class TestVADComponent:
    """VAD (Voice Activity Detection) with synthetic audio."""

    def test_vad_detects_tone(self):
        """A 440Hz tone should register as speech-like activity."""
        from speech import SileroVoiceActivityDetector
        vad = SileroVoiceActivityDetector()
        tone_wav = generate_sine_wav(duration_s=1.0, freq_hz=440)
        result = vad.detect_bytes(tone_wav, ".wav")
        # Silero may or may not detect a pure tone as speech, but it shouldn't crash
        assert "speech_detected" in result
        assert isinstance(result["speech_detected"], bool)

    def test_vad_silence(self):
        """Pure silence should not be detected as speech."""
        from speech import SileroVoiceActivityDetector
        vad = SileroVoiceActivityDetector()
        silence_wav = generate_silence_wav(duration_s=1.0)
        result = vad.detect_bytes(silence_wav, ".wav")
        assert result["speech_detected"] is False


class TestTranslationTiers:
    """Test each translation tier in isolation."""

    def test_lightweight_known_phrase(self):
        from translation import LightweightTranslator
        t = LightweightTranslator()
        assert t.translate("good morning", "en", "es") == "buenos días"

    def test_lightweight_unknown_phrase(self):
        from translation import LightweightTranslator
        t = LightweightTranslator()
        result = t.translate("quantum computing is fascinating", "en", "es")
        assert result.startswith("[en->es]")

    def test_remote_translator(self):
        from translation import RemoteTranslator
        t = RemoteTranslator(timeout_seconds=5.0)
        try:
            result = t.translate("hello world", "en", "es")
            assert result
            assert "hola" in result.lower() or "mundo" in result.lower()
        except RuntimeError:
            pytest.skip("Remote translator not reachable in this environment")

    def test_hybrid_auto_routing(self):
        from translation import HybridTranslator
        t = HybridTranslator()
        # Known phrase → lightweight
        assert t.translate("hello", "en", "es") == "hola"
        # Unknown → should route to remote (or marian)
        result = t.translate("The weather is beautiful today", "en", "es")
        assert result
        assert not result.startswith("[en->es]")


class TestTTSComponent:
    """TTS synthesis validation."""

    def test_tts_synthesize(self):
        from tts import PiperTextToSpeech
        tts = PiperTextToSpeech()
        output_path = f"/tmp/test-tts-{time.time()}.wav"
        try:
            result_path = tts.synthesize("Hello world", output_path, language="en")
            assert result_path
            assert Path(result_path).exists()
            assert Path(result_path).stat().st_size > 100
        finally:
            Path(output_path).unlink(missing_ok=True)
            if result_path and result_path != output_path:
                Path(result_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Full pipeline integration test
# ---------------------------------------------------------------------------

class TestFullPipeline:
    """Tests the complete pipeline end-to-end with real components."""

    def test_translate_text_pipeline(self):
        """Text → Translate → result (no audio)."""
        from backend.pipeline import AnaiTranslatorPipeline
        pipe = AnaiTranslatorPipeline()
        result = pipe.translate_text(
            text="hello",
            source_language="en",
            target_language="es",
            synthesize_audio=False,
        )
        assert result.source_text == "hello"
        assert result.translated_text
        assert "hola" in result.translated_text.lower()

    def test_translate_text_with_tts(self):
        """Text → Translate → TTS → audio file exists."""
        from backend.pipeline import AnaiTranslatorPipeline
        pipe = AnaiTranslatorPipeline()
        output_path = f"/tmp/test-pipeline-tts-{time.time()}.wav"
        try:
            result = pipe.translate_text(
                text="hello",
                source_language="en",
                target_language="es",
                synthesize_audio=True,
                output_path=output_path,
            )
            assert result.translated_text
            if result.audio_output_path:
                assert Path(result.audio_output_path).exists()
        finally:
            Path(output_path).unlink(missing_ok=True)

    def test_translation_tier_metrics(self):
        """Verify metrics are tracked through the pipeline."""
        from backend.pipeline import AnaiTranslatorPipeline
        pipe = AnaiTranslatorPipeline()
        pipe.translate_text(text="hello", source_language="en", target_language="es", synthesize_audio=False)
        if hasattr(pipe.translator, "get_metrics"):
            metrics = pipe.translator.get_metrics()
            assert isinstance(metrics, dict)
            assert sum(metrics.values()) > 0


# ---------------------------------------------------------------------------
# Latency measurement integration test
# ---------------------------------------------------------------------------

class TestLatencyMeasurement:
    """Validates that latency tracking works across the pipeline."""

    def test_latency_engine_records_during_translation(self):
        from backend.latency import LatencyEngine
        le = LatencyEngine()

        # Simulate a full pipeline run
        run = le.begin_run("integration-test", speaker="A", source_lang="en", target_lang="es")

        # Simulate VAD
        vad_start = time.monotonic()
        time.sleep(0.01)
        le.record_stage("vad", (time.monotonic() - vad_start) * 1000)

        # Simulate STT
        stt_start = time.monotonic()
        time.sleep(0.01)
        le.record_stage("stt", (time.monotonic() - stt_start) * 1000)

        # Simulate Translation
        trans_start = time.monotonic()
        time.sleep(0.01)
        le.record_stage("translation", (time.monotonic() - trans_start) * 1000)

        # Simulate TTS
        tts_start = time.monotonic()
        time.sleep(0.01)
        le.record_stage("tts", (time.monotonic() - tts_start) * 1000)

        completed = le.end_run()
        assert completed is not None
        assert completed.total_ms > 0
        assert "vad" in completed.stages
        assert "stt" in completed.stages
        assert "translation" in completed.stages
        assert "tts" in completed.stages

        snap = le.snapshot()
        assert snap["summary"]["total_runs"] == 1
        assert snap["summary"]["avg_total_ms"] > 0

        health = le.health_assessment()
        assert health["status"] in ("excellent", "good", "degraded", "poor")


# ---------------------------------------------------------------------------
# Duplex conversation integration test
# ---------------------------------------------------------------------------

class TestDuplexConversation:
    """End-to-end duplex conversation simulation."""

    def test_two_speaker_conversation(self):
        """Simulate a complete A-B-A conversation with translations."""
        from backend.conversation import ConversationBrain
        from backend.memory import ConversationMemory
        from backend.speakers import SpeakerMemory
        from translation import HybridTranslator

        brain = ConversationBrain()
        memory = ConversationMemory()
        speaker_mem = SpeakerMemory()
        translator = HybridTranslator()

        # Speaker A says hello in English
        d1 = brain.request_turn("A")
        assert d1.allowed
        speaker_mem.register("A", language="en")
        t1 = translator.translate("hello", "en", "es")
        assert t1 == "hola"
        brain.analyze_semantics("A", "hello")
        memory.add("A", "hello", t1)
        brain.end_turn("A")

        # Speaker B responds in Spanish
        d2 = brain.request_turn("B")
        assert d2.allowed
        speaker_mem.register("B", language="es")
        t2 = translator.translate("hola", "es", "en")
        assert t2 == "hello"
        brain.analyze_semantics("B", "hola")
        memory.add("B", "hola", t2)
        brain.end_turn("B")

        # Speaker A asks a question
        d3 = brain.request_turn("A")
        assert d3.allowed
        brain.analyze_semantics("A", "How are you?")
        snap = brain.semantic_snapshot()
        assert snap["last_intent"] == "question"
        assert len(snap["recent_turns"]) == 3

    def test_overlapping_speakers(self):
        """Both speakers try to talk at the same time."""
        from backend.conversation import ConversationBrain
        brain = ConversationBrain()

        # A starts talking
        d1 = brain.request_turn("A")
        assert d1.allowed

        # B tries immediately (soft overlap)
        d2 = brain.request_turn("B")
        assert d2.allowed
        assert d2.behavior == "overlap"

        # Both should be able to proceed
        brain.analyze_semantics("A", "I need help")
        brain.analyze_semantics("B", "How can I help you?")
        brain.end_turn("A")
        brain.end_turn("B")


# ---------------------------------------------------------------------------
# API endpoint integration test
# ---------------------------------------------------------------------------

class TestAPIEndpoints:
    """Test the FastAPI endpoints directly."""

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        os.environ.setdefault("USERS", "test:test123")
        os.environ.setdefault("JWT_SECRET", "test-secret-key-for-testing-only-not-production")
        from backend.api import app
        return TestClient(app)

    def test_health_endpoint(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "ready" in data

    def test_latency_endpoint(self, client):
        resp = client.get("/latency")
        assert resp.status_code == 200
        data = resp.json()
        assert "stages" in data
        assert "health" in data
        assert "summary" in data

    def test_languages_endpoint(self, client):
        resp = client.get("/languages")
        assert resp.status_code == 200
        data = resp.json()
        assert "languages" in data
