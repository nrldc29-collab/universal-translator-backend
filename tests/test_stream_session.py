"""Tests for backend.stream_session.StreamSessionState."""

import asyncio
import time
import pytest

from backend.stream_session import StreamSessionState
from backend.confidence import ConfidenceEngine
from backend.latency import LatencyEngine


class TestStreamSessionStateDefaults:
    def test_default_languages(self):
        state = StreamSessionState()
        assert state.source_language == "en"
        assert state.target_language == "ht"

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

    def test_session_metadata_initialized(self):
        state = StreamSessionState()
        assert state.created_at > 0
        assert state.last_activity_at > 0
        assert state.total_chunks_received == 0
        assert state.total_segments_processed == 0
        assert state.error_count == 0


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

    def test_reset_increments_total_segments_processed(self):
        state = StreamSessionState()
        assert state.total_segments_processed == 0
        state.reset_segment()
        assert state.total_segments_processed == 1
        state.reset_segment()
        assert state.total_segments_processed == 2

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


class TestStreamSessionStateActivityTracking:
    def test_update_activity_updates_timestamp(self):
        state = StreamSessionState()
        original_time = state.last_activity_at
        time.sleep(0.01)
        state.update_activity()
        assert state.last_activity_at > original_time

    def test_get_session_age_returns_positive(self):
        state = StreamSessionState()
        age = state.get_session_age()
        assert age >= 0
        assert age < 1  # Should be very recent

    def test_get_idle_time_increases_without_activity(self):
        state = StreamSessionState()
        idle1 = state.get_idle_time()
        time.sleep(0.01)
        idle2 = state.get_idle_time()
        assert idle2 > idle1

    def test_get_idle_time_resets_after_update_activity(self):
        state = StreamSessionState()
        time.sleep(0.01)
        idle_before = state.get_idle_time()
        state.update_activity()
        idle_after = state.get_idle_time()
        assert idle_after < idle_before


class TestStreamSessionStateBufferOverflow:
    def test_is_buffer_overflow_false_when_empty(self):
        state = StreamSessionState()
        assert state.is_buffer_overflow() is False

    def test_is_buffer_overflow_false_when_under_limit(self):
        state = StreamSessionState()
        state.audio_chunks.extend(b"\x00" * 1024)
        assert state.is_buffer_overflow() is False

    def test_is_buffer_overflow_true_when_over_limit(self):
        state = StreamSessionState()
        state.audio_chunks.extend(b"\x00" * (state.max_buffer_bytes + 1))
        assert state.is_buffer_overflow() is True


class TestStreamSessionStateTaskCleanup:
    def test_cleanup_tasks_with_no_tasks(self):
        state = StreamSessionState()
        state.cleanup_tasks()
        assert state.partial_task is None
        assert state.live_text_task is None

    @pytest.mark.asyncio
    async def test_cleanup_tasks_with_done_task(self):
        state = StreamSessionState()
        state.partial_task = asyncio.create_task(asyncio.sleep(0))
        await state.partial_task
        state.cleanup_tasks()
        assert state.partial_task is None

    @pytest.mark.asyncio
    async def test_cleanup_tasks_cancels_pending_task(self):
        state = StreamSessionState()
        state.partial_task = asyncio.create_task(asyncio.sleep(10))
        state.cleanup_tasks()
        assert state.partial_task is None
        # Task was cancelled, just verify cleanup didn't crash


class TestStreamSessionStateStats:
    def test_get_stats_returns_all_fields(self):
        state = StreamSessionState()
        stats = state.get_stats()
        assert "session_id" in stats
        assert "age_seconds" in stats
        assert "idle_seconds" in stats
        assert "total_chunks" in stats
        assert "total_segments" in stats
        assert "segment_generation" in stats
        assert "buffer_size" in stats
        assert "buffer_max" in stats
        assert "error_count" in stats
        assert "vad_errors" in stats
        assert "speech_started" in stats
        assert "tts_active" in stats

    def test_get_stats_reflects_current_state(self):
        state = StreamSessionState()
        state.speech_started = True
        state.vad_error_count = 3
        state.error_count = 2
        state.audio_chunks.extend(b"\x00" * 100)
        
        stats = state.get_stats()
        assert stats["speech_started"] is True
        assert stats["vad_errors"] == 3
        assert stats["error_count"] == 2
        assert stats["buffer_size"] == 100
