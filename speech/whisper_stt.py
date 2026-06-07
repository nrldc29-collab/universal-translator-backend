import logging
from pathlib import Path
from threading import BoundedSemaphore, Lock
from time import time
from typing import Optional

from backend.config import (
    get_stt_max_concurrency,
    get_stt_queue_max_depth,
    get_whisper_beam_size,
    get_whisper_cpu_threads,
    get_whisper_num_workers,
)
from speech.audio_decode import transcode_to_wav

logger = logging.getLogger(__name__)


class WhisperSpeechToText:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._model_lock = Lock()
        self._semaphore = BoundedSemaphore(get_stt_max_concurrency())
        self._lock = Lock()
        self._queue_depth = 0
        self._active = 0
        self._rejected = 0
        self._wait_times = []

    def _load_model(self):
        if self._model is not None:
            return self._model

        # Double-checked locking: serialize the first load so concurrent
        # requests share one WhisperModel instead of each building their own
        # (which would double the model's memory footprint on GPU/CPU).
        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Install requirements or use text input mode."
                ) from exc

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=get_whisper_cpu_threads(),
                num_workers=get_whisper_num_workers(),
            )
            return self._model

    def preload(self) -> bool:
        self._load_model()
        return True

    def _run_transcribe(self, model, audio_path: str, source_language):
        language = None
        if source_language and str(source_language).lower() not in {"auto", "detect", "none"}:
            language = source_language
        segments, _ = model.transcribe(
            audio_path,
            language=language,
            beam_size=get_whisper_beam_size(),
            best_of=1,
            temperature=0,
            condition_on_previous_text=False,
            vad_filter=False,
            without_timestamps=True,
            word_timestamps=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    def transcribe(self, audio_path: str, source_language=None):
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError("Audio file not found: " + str(audio_path))

        model = self._load_model()
        queued_at = time()
        with self._lock:
            if self._queue_depth >= get_stt_queue_max_depth():
                self._rejected += 1
                raise RuntimeError("STT queue is full. Please retry shortly.")
            self._queue_depth += 1
        with self._semaphore:
            wait_seconds = time() - queued_at
            with self._lock:
                self._queue_depth = max(0, self._queue_depth - 1)
                self._active += 1
                self._wait_times.append(wait_seconds)
                self._wait_times = self._wait_times[-200:]
            transcoded_path = None
            try:
                try:
                    return self._run_transcribe(model, str(path), source_language)
                except (RuntimeError, ValueError, OSError) as exc:
                    logger.warning(
                        "Whisper failed to read %s (%s); attempting ffmpeg transcode fallback",
                        audio_path,
                        exc,
                    )
                    transcoded_path = transcode_to_wav(str(path))
                    if not transcoded_path:
                        raise
                    return self._run_transcribe(model, transcoded_path, source_language)
            finally:
                with self._lock:
                    self._active = max(0, self._active - 1)
                if transcoded_path:
                    Path(transcoded_path).unlink(missing_ok=True)

    def queue_snapshot(self):
        with self._lock:
            avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0
            return {
                "queued": self._queue_depth,
                "active": self._active,
                "max_depth": get_stt_queue_max_depth(),
                "rejected": self._rejected,
                "avg_wait_seconds": round(avg_wait, 4),
                "max_wait_seconds": round(max(self._wait_times), 4) if self._wait_times else 0,
            }
