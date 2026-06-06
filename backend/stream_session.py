"""Per-connection mutable state for the WebSocket audio streaming handler.

Extracting this from `websocket_audio_translation` separates *what state a
streaming session holds* from *how the WebSocket message loop drives it*,
making state transitions explicit and unit-testable without a live WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from backend.config import get_stream_buffer_max_mb
from backend.confidence import ConfidenceEngine
from backend.latency import LatencyEngine

logger = logging.getLogger(__name__)


@dataclass
class StreamSessionState:
    """Mutable state bundle for a single audio-streaming WebSocket session.

    Every field mirrors a local variable that previously lived inside the
    ``websocket_audio_translation`` closure.  Moving them here lets helpers
    accept a ``StreamSessionState`` instead of relying on ``nonlocal``.
    """

    # ── Language / speaker identity ────────────────────────────────────────
    source_language: str = "en"
    target_language: str = "ht"
    speaker: str = "speaker"
    speaker_label: str = "Person 1"
    speaker_index: int = 1
    speaker_mode: str = "manual"
    speaker_detection: str = "manual"
    device_id: Optional[str] = None
    session_id: str = "default"

    # ── Audio buffer ────────────────────────────────────────────────────────
    audio_chunks: bytearray = field(default_factory=bytearray)
    recent_chunks: list = field(default_factory=list)
    speech_started: bool = False
    finalizing: bool = False
    silent_checks: int = 0
    vad_error_count: int = 0
    last_chunk_meta: dict = field(default_factory=dict)
    client_mime_type: str = "audio/webm"
    audio_suffix: str = ".webm"
    last_speech_at: float = 0.0

    # ── Partial / live translation ──────────────────────────────────────────
    last_partial_at: float = 0.0
    partial_text: str = ""
    partial_buffer: str = ""
    partial_tts_text: str = ""
    last_sent_translation: str = ""
    last_active_speaker: Optional[str] = None
    segment_generation: int = 0

    # ── Live-text deduplication tasks ──────────────────────────────────────
    partial_task: Optional[asyncio.Task] = field(default=None, repr=False)
    live_text_task: Optional[asyncio.Task] = field(default=None, repr=False)
    live_text_pending: Optional[str] = None
    live_text_revision: int = 0
    live_text_active_until: float = 0.0

    # ── TTS / turn state ────────────────────────────────────────────────────
    tts_active: bool = False
    turn_announced_for_segment: bool = False
    active_speaker_notice_at: float = 0.0

    # ── Engines (created per session so they don't share state) ────────────
    latency_engine: LatencyEngine = field(default_factory=LatencyEngine)
    confidence_engine: ConfidenceEngine = field(default_factory=ConfidenceEngine)

    # ── Session metadata ──────────────────────────────────────────────────
    created_at: float = field(default_factory=time.time)
    last_activity_at: float = field(default_factory=time.time)
    total_chunks_received: int = 0
    total_segments_processed: int = 0
    error_count: int = 0

    def __post_init__(self):
        self.max_buffer_bytes: int = get_stream_buffer_max_mb() * 1024 * 1024
        self.pipeline_queue: asyncio.Queue[dict] = asyncio.Queue(maxsize=1)
        logger.debug(f"StreamSessionState created for session {self.session_id}")

    def reset_segment(self) -> None:
        """Clear per-utterance state between speaker turns."""
        self.audio_chunks = bytearray()
        self.recent_chunks = []
        self.speech_started = False
        self.silent_checks = 0
        self.vad_error_count = 0
        self.last_speech_at = 0.0
        self.partial_text = ""
        self.partial_buffer = ""
        self.partial_tts_text = ""
        self.last_partial_at = 0.0
        self.last_sent_translation = ""
        self.last_active_speaker = None
        self.turn_announced_for_segment = False
        self.segment_generation += 1
        self.total_segments_processed += 1

    def update_activity(self):
        self.last_activity_at = time.time()

    def get_session_age(self):
        return time.time() - self.created_at

    def get_idle_time(self):
        return time.time() - self.last_activity_at

    def is_buffer_overflow(self):
        return len(self.audio_chunks) > self.max_buffer_bytes

    def cleanup_tasks(self):
        for task in [self.partial_task, self.live_text_task]:
            if task and not task.done():
                task.cancel()
        self.partial_task = None
        self.live_text_task = None

    def get_stats(self):
        return {
            "session_id": self.session_id,
            "age_seconds": self.get_session_age(),
            "idle_seconds": self.get_idle_time(),
            "total_chunks": self.total_chunks_received,
            "total_segments": self.total_segments_processed,
            "segment_generation": self.segment_generation,
            "buffer_size": len(self.audio_chunks),
            "buffer_max": self.max_buffer_bytes,
            "error_count": self.error_count,
            "vad_errors": self.vad_error_count,
            "speech_started": self.speech_started,
            "tts_active": self.tts_active,
        }
