import logging
import math
import struct
import wave
from pathlib import Path
from tempfile import NamedTemporaryFile

from speech.audio_decode import transcode_to_wav

logger = logging.getLogger(__name__)

_FRAME_MS = 30
_ENERGY_THRESHOLD = 0.01
_MIN_SPEECH_FRAMES = 3


def _rms(samples: list) -> float:
    if not samples:
        return 0.0
    return math.sqrt(sum(s * s for s in samples) / len(samples))


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

    all_samples = [s / divisor for s in struct.unpack(fmt, raw)]
    if n_channels > 1:
        mono = [sum(all_samples[i::n_channels]) / n_channels for i in range(n_frames)]
    else:
        mono = all_samples

    frame_size = int(framerate * _FRAME_MS / 1000)
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
    return {
        "speech_detected": bool(segments),
        "segments": segments,
        "speech_seconds": speech_seconds,
    }


class SileroVoiceActivityDetector:
    def __init__(self, threshold: float = 0.3, min_speech_duration_ms: int = 200):
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms

    def detect_file(self, audio_path: str) -> dict:
        path = Path(audio_path)
        if not path.exists() or path.stat().st_size == 0:
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0}

        transcoded_path = None
        try:
            if path.suffix.lower() == ".wav":
                try:
                    return _energy_vad(str(path), threshold=_ENERGY_THRESHOLD, min_speech_duration_ms=self.min_speech_duration_ms)
                except Exception as exc:
                    logger.warning("Direct WAV read failed (%s); transcoding via ffmpeg", exc)

            transcoded_path = transcode_to_wav(str(path))
            if not transcoded_path:
                logger.warning("ffmpeg could not transcode %s; assuming speech present", audio_path)
                return {"speech_detected": True, "segments": [], "speech_seconds": 0.0}
            return _energy_vad(transcoded_path, threshold=_ENERGY_THRESHOLD, min_speech_duration_ms=self.min_speech_duration_ms)
        except Exception as exc:
            logger.warning("VAD failed for %s (%s); assuming speech present", audio_path, exc)
            return {"speech_detected": True, "segments": [], "speech_seconds": 0.0}
        finally:
            if transcoded_path:
                Path(transcoded_path).unlink(missing_ok=True)

    def detect_bytes(self, audio_bytes: bytes, suffix: str = ".webm") -> dict:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            return self.detect_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
