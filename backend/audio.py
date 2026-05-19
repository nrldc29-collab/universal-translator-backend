import contextlib
import wave
import os
from typing import Tuple, Optional

import numpy as np

try:
    # Optional RNNoise binding; if unavailable, we no-op
    from rnnoise import RNNoise  # type: ignore

    _RN = RNNoise()
    _HAS_RNNOISE = True
except (ImportError, ModuleNotFoundError):  # pragma: no cover - optional dep
    _RN = None
    _HAS_RNNOISE = False


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    max_val = float(np.max(np.abs(audio))) if audio.size else 0.0
    if max_val > 0:
        audio = audio / max_val
    return audio


def compute_rms(audio: np.ndarray) -> float:
    if audio.size == 0:
        return 0.0
    return float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))


def _read_wav_mono_int16(path: str) -> Tuple[int, Optional[np.ndarray]]:
    try:
        with contextlib.closing(wave.open(path, 'rb')) as wf:
            nch = wf.getnchannels()
            sw = wf.getsampwidth()
            sr = wf.getframerate()
            nframes = wf.getnframes()
            if sw != 2 or nframes == 0:
                return sr, None
            raw = wf.readframes(nframes)
            data = np.frombuffer(raw, dtype=np.int16)
            if nch > 1:
                data = data.reshape(-1, nch).mean(axis=1).astype(np.int16)
            return sr, data
    except (OSError, ValueError, wave.Error):
        return 0, None


def _write_wav_mono_int16(path: str, sr: int, data: np.ndarray) -> None:
    data_i16 = np.asarray(data, dtype=np.int16)
    with contextlib.closing(wave.open(path, 'wb')) as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(data_i16.tobytes())


def _denoise_with_rnnoise(audio_f32: np.ndarray, sr: int) -> np.ndarray:
    if not _HAS_RNNOISE:
        return audio_f32
    # RNNoise expects 480-sample frames at 48kHz
    if sr != 48000:
        return audio_f32
    out = np.empty_like(audio_f32)
    frame = 480
    length = audio_f32.shape[0]
    # Process in 480-sample windows; leftover tail is copied as-is
    for i in range(0, length - (length % frame), frame):
        out[i:i+frame] = _RN.process_frame(audio_f32[i:i+frame])
    if length % frame:
        out[length - (length % frame):] = audio_f32[length - (length % frame):]
    return out


def process_wav_for_stt(path: str) -> Tuple[str, dict] | Tuple[None, None]:
    """
    Best-effort clean-up for STT input.
    - Read 16-bit PCM WAV, convert to mono if needed.
    - Optional RNNoise denoise (if installed and 48kHz).
    - Normalize amplitude to [-1, 1].
    - Write processed WAV alongside original.
    Returns (processed_path, metrics) or (None, None) on pass-through.
    """
    sr, data_i16 = _read_wav_mono_int16(path)
    if data_i16 is None or data_i16.size == 0:
        return None, None
    audio_f32 = data_i16.astype(np.float32) / 32768.0
    rms_before = compute_rms(audio_f32)
    audio_f32 = _denoise_with_rnnoise(audio_f32, sr)
    audio_f32 = normalize_audio(audio_f32)
    rms_after = compute_rms(audio_f32)
    out_i16 = np.clip(audio_f32 * 32768.0, -32768, 32767).astype(np.int16)
    base, ext = os.path.splitext(path)
    out_path = f"{base}-proc.wav"
    _write_wav_mono_int16(out_path, sr, out_i16)
    return out_path, {"rms_before": rms_before, "rms_after": rms_after, "sample_rate": sr}
