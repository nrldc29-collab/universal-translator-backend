import logging
import math
import struct
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Optional

from speech.audio_decode import transcode_to_wav

logger = logging.getLogger(__name__)

_FRAME_MS = 30
_ENERGY_THRESHOLD = 0.01
_MIN_SPEECH_FRAMES = 3
_MAX_FILE_SIZE_MB = 100  # Reject files larger than 100MB


def _rms(samples: list) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


def _validate_wav_file(wav_path: str) -> bool:
    """Validate WAV file is readable and not corrupted."""
    try:
        with wave.open(wav_path, "rb") as wf:
            return wf.getnframes() > 0
    except Exception:
        return False


def _energy_vad(wav_path: str, threshold: float = _ENERGY_THRESHOLD, min_speech_duration_ms: int = 200) -> dict:
    """Pure-Python energy-based VAD using stdlib wave. No ML required."""
    try:
        with wave.open(wav_path, "rb") as wf:
            n_channels = wf.getnchannels()
            sampwidth = wf.getsampwidth()
            framerate = wf.getframerate()
            n_frames = wf.getnframes()
            raw = wf.readframes(n_frames)
    except Exception as exc:
        raise RuntimeError(f"Cannot read WAV {wav_path}: {exc}") from exc

    if sampwidth == 2:
        fmt = f"<{n_frames * n_channels}h"
        divisor = 32768.0
    elif sampwidth == 4:
        fmt = f"<{n_frames * n_channels}i"
        divisor = 2147483648.0
    else:
        raise ValueError(f"Unsupported sample width: {sampwidth}")

    try:
        all_samples = [s / divisor for s in struct.unpack(fmt, raw)]
    except struct.error as exc:
        raise RuntimeError(f"Failed to unpack audio data: {exc}") from exc

    if n_channels > 1:
        # Downmix to mono by averaging each frame's interleaved channel samples.
        mono = [
            sum(all_samples[f * n_channels:(f + 1) * n_channels]) / n_channels
            for f in range(n_frames)
        ]
    else:
        mono = all_samples

    frame_size = int(framerate * _FRAME_MS / 1000)
    if frame_size < 1:
        frame_size = 1
    min_frames = max(1, int(min_speech_duration_ms / _FRAME_MS))
    segments = []
    speech_start = None
    silent_count = 0
    silence_merge_frames = 5

    for i in range(0, len(mono) - frame_size + 1, frame_size):
        frame = mono[i:i + frame_size]
        energy = _rms(frame)
        sample_pos = i
        if energy >= threshold:
            if speech_start is None:
                speech_start = sample_pos
            silent_count = 0
        else:
            if speech_start is not None:
                silent_count += 1
                if silent_count >= silence_merge_frames:
                    end_pos = sample_pos
                    duration_frames = (end_pos - speech_start) // frame_size
                    if duration_frames >= min_frames:
                        segments.append({"start": speech_start, "end": end_pos})
                    speech_start = None
                    silent_count = 0

    if speech_start is not None:
        end_pos = len(mono)
        duration_frames = (end_pos - speech_start) // frame_size
        if duration_frames >= min_frames:
            segments.append({"start": speech_start, "end": end_pos})

    speech_seconds = sum((s["end"] - s["start"]) / framerate for s in segments)
    frame_energies = [
        _rms(mono[i:i + frame_size])
        for i in range(0, max(0, len(mono) - frame_size + 1), frame_size)
    ]
    avg_energy = sum(frame_energies) / len(frame_energies) if frame_energies else 0.0
    return {
        "speech_detected": bool(segments),
        "segments": segments,
        "speech_seconds": speech_seconds,
        "avg_energy": avg_energy,
    }


class SileroVoiceActivityDetector:
    """Energy-threshold voice activity detector (stdlib wave + RMS; no ML model loaded)."""
    def __init__(self, threshold: float = 0.3, min_speech_duration_ms: int = 200):
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self.energy_threshold = _ENERGY_THRESHOLD

    def set_energy_threshold(self, threshold: float) -> None:
        self.energy_threshold = max(0.01, min(0.2, float(threshold)))

    def detect_file(self, audio_path: str, *, energy_threshold: float | None = None) -> dict:
        path = Path(audio_path)
        if not path.exists():
            logger.warning(f"Audio file does not exist: {audio_path}")
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "error": "file_not_found"}
        
        if path.stat().st_size == 0:
            logger.warning(f"Audio file is empty: {audio_path}")
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "error": "empty_file"}
        
        if path.stat().st_size > _MAX_FILE_SIZE_MB * 1024 * 1024:
            logger.warning(f"Audio file too large ({path.stat().st_size / 1024 / 1024:.1f}MB): {audio_path}")
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "error": "file_too_large"}

        transcoded_path = None
        try:
            if path.suffix.lower() == ".wav":
                if _validate_wav_file(str(path)):
                    try:
                        threshold = energy_threshold if energy_threshold is not None else self.energy_threshold
                        return _energy_vad(str(path), threshold=threshold, min_speech_duration_ms=self.min_speech_duration_ms)
                    except Exception as exc:
                        logger.warning("Direct WAV read failed (%s); transcoding via ffmpeg", exc)
                else:
                    logger.warning("WAV file validation failed; transcoding via ffmpeg")

            transcoded_path = transcode_to_wav(str(path))
            if not transcoded_path:
                return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "fallback": "transcode_failed"}
            threshold = energy_threshold if energy_threshold is not None else self.energy_threshold
            return _energy_vad(transcoded_path, threshold=threshold, min_speech_duration_ms=self.min_speech_duration_ms)
        except Exception as exc:
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "fallback": "vad_error", "error": str(exc)}
        finally:
            if transcoded_path:
                try:
                    Path(transcoded_path).unlink(missing_ok=True)
                except Exception:
                    pass

    def detect_bytes(self, audio_bytes, suffix=".webm", *, energy_threshold: float | None = None):
        if not audio_bytes:
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "error": "empty_bytes"}
        if len(audio_bytes) > _MAX_FILE_SIZE_MB * 1024 * 1024:
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0, "error": "data_too_large"}
        temp_file = None
        try:
            temp_file = NamedTemporaryFile(delete=False, suffix=suffix)
            temp_file.write(audio_bytes)
            temp_file.flush()
            return self.detect_file(temp_file.name, energy_threshold=energy_threshold)
        except Exception as exc:
            return {"speech_detected": True, "segments": [], "speech_seconds": 0.0, "fallback": "bytes_error", "error": str(exc)}
        finally:
            if temp_file:
                try:
                    temp_file.close()
                    Path(temp_file.name).unlink(missing_ok=True)
                except Exception:
                    pass
