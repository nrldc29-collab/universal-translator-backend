"""Tests for backend.stream_session.StreamSessionState."""

import asyncio

from backend.stream_session import StreamSessionState
from backend.confidence import ConfidenceEngine
from backend.latency import LatencyEngine


class TestStreamSessionStateDefaults:
    def test_default_languages(self):
        state = StreamSessionState()
        assert state.source_language == "en"
        assert state.target_language == "es"

    def test_default_speaker_identity(self):
        state = StreamSessionState()
        assert state.speaker == "speaker"
        assert state.speaker_label == "Person 1"
        assert state.speaker_index == 1
        assert state.speaker_mode == "manual"
        assert state.device_id is None

    def test_default_audio_buffer_empty(self):
        state = StreamSessionState()
        assert len(state.audio_chunks) == 0
        assert state.recent_chunks == []
        assert state.speech_started is False
        assert state.finalizing is False

    def test_default_partial_state_empty(self):
        state = StreamSessionState()
        assert state.partial_text == ""
        assert state.partial_buffer == ""
        assert state.last_sent_translation == ""
        assert state.segment_generation == 0

    def test_engines_are_created_per_instance(self):
        s1 = StreamSessionState()
        s2 = StreamSessionState()
        assert s1.latency_engine is not s2.latency_engine
        assert s1.confidence_engine is not s2.confidence_engine
        assert isinstance(s1.latency_engine, LatencyEngine)
        assert isinstance(s1.confidence_engine, ConfidenceEngine)

    def test_pipeline_queue_created_per_instance(self):
        s1 = StreamSessionState()
        s2 = StreamSessionState()
        assert s1.pipeline_queue is not s2.pipeline_queue
        assert isinstance(s1.pipeline_queue, asyncio.Queue)

    def test_max_buffer_bytes_is_positive(self):
        state = StreamSessionState()
        assert state.max_buffer_bytes > 0


class TestStreamSessionStateResetSegment:
    def test_reset_clears_audio_chunks(self):
        state = StreamSessionState()
        state.audio_chunks.extend(b"\x00" * 1024)
        state.reset_segment()
        assert len(state.audio_chunks) == 0

    def test_reset_clears_recent_chunks(self):
        state = StreamSessionState()
        state.recent_chunks.append(b"\x00" * 100)
        state.reset_segment()
        assert state.recent_chunks == []

    def test_reset_clears_speech_flags(self):
        state = StreamSessionState()
        state.speech_started = True
        state.silent_checks = 5
        state.vad_error_count = 2
        state.reset_segment()
        assert state.speech_started is False
        assert state.silent_checks == 0
        assert state.vad_error_count == 0

    def test_reset_clears_partial_translation_state(self):
        state = StreamSessionState()
        state.partial_text = "hello"
        state.partial_buffer = "world"
        state.partial_tts_text = "hola"
        state.last_sent_translation = "hola mundo"
        state.reset_segment()
        assert state.partial_text == ""
        assert state.partial_buffer == ""
        assert state.partial_tts_text == ""
        assert state.last_sent_translation == ""

    def test_reset_increments_segment_generation(self):
        state = StreamSessionState()
        assert state.segment_generation == 0
        state.reset_segment()
        assert state.segment_generation == 1
        state.reset_segment()
        assert state.segment_generation == 2

    def test_reset_clears_turn_state(self):
        state = StreamSessionState()
        state.turn_announced_for_segment = True
        state.last_active_speaker = "A"
        state.reset_segment()
        assert state.turn_announced_for_segment is False
        assert state.last_active_speaker is None

    def test_reset_preserves_identity_fields(self):
        state = StreamSessionState()
        state.speaker = "A"
        state.speaker_label = "Doctor"
        state.source_language = "fr"
        state.target_language = "de"
        state.reset_segment()
        assert state.speaker == "A"
        assert state.speaker_label == "Doctor"
        assert state.source_language == "fr"
        assert state.target_language == "de"

    def test_multiple_resets_do_not_share_bytearray(self):
        state = StreamSessionState()
        state.audio_chunks.extend(b"\xAB" * 50)
        state.reset_segment()
        assert state.audio_chunks == bytearray()
        state.audio_chunks.extend(b"\xCD" * 10)
        state.reset_segment()
        assert state.audio_chunks == bytearray()
