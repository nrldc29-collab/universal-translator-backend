import contextlib
import hashlib
import math
import os
import wave
from pathlib import Path

import numpy as np


FALSE_VALUES = {"0", "false", "no", "off"}


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() not in FALSE_VALUES


def _env_float(name: str, default: float, low: float | None = None, high: float | None = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if low is not None:
        value = max(low, value)
    if high is not None:
        value = min(high, value)
    return value


def voice_cache_fingerprint() -> str:
    """Fingerprint settings that materially change rendered TTS audio."""
    keys = (
        "PREFER_EDGE_TTS",
        "TTS_SOFTENING_ENABLED",
        "TTS_VOICE_PROFILE",
        "TTS_SOFTENING_LOW_PASS_HZ",
        "TTS_SOFTENING_TARGET_RMS",
        "TTS_SOFTENING_PEAK_LIMIT",
        "TTS_SOFTENING_ROOM",
        "TTS_SOFTENING_BACKGROUND_AIR",
        "TTS_SOFTENING_FADE_MS",
    )
    return "|".join(f"{key}={os.getenv(key, '')}" for key in keys)


def _read_wav(path: Path) -> tuple[int, np.ndarray] | None:
    try:
        with contextlib.closing(wave.open(str(path), "rb")) as wav_file:
            channels = wav_file.getnchannels()
            sample_width = wav_file.getsampwidth()
            sample_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            if sample_width != 2 or channels < 1 or frames <= 0:
                return None
            raw = wav_file.readframes(frames)
    except (OSError, ValueError, wave.Error):
        return None

    samples = np.frombuffer(raw, dtype=np.int16)
    if channels > 1:
        samples = samples.reshape(-1, channels)
    else:
        samples = samples.reshape(-1, 1)
    audio = samples.astype(np.float32) / 32768.0
    return sample_rate, audio


def _write_wav(path: Path, sample_rate: int, audio: np.ndarray) -> None:
    audio = np.asarray(audio, dtype=np.float32)
    if audio.ndim == 1:
        audio = audio.reshape(-1, 1)
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with contextlib.closing(wave.open(str(path), "wb")) as wav_file:
        wav_file.setnchannels(pcm.shape[1])
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.reshape(-1).tobytes())


def _one_pole_lowpass(audio: np.ndarray, sample_rate: int, cutoff_hz: float) -> np.ndarray:
    if audio.size == 0 or cutoff_hz <= 0 or cutoff_hz >= sample_rate / 2:
        return audio
    alpha = 1.0 - math.exp(-2.0 * math.pi * cutoff_hz / sample_rate)
    filtered = np.empty_like(audio, dtype=np.float32)
    state = np.zeros(audio.shape[1], dtype=np.float32)
    for index in range(audio.shape[0]):
        state = state + alpha * (audio[index] - state)
        filtered[index] = state

    # Reverse pass reduces the phase smear that makes short chunks clicky.
    state = np.zeros(audio.shape[1], dtype=np.float32)
    for index in range(filtered.shape[0] - 1, -1, -1):
        state = state + alpha * (filtered[index] - state)
        filtered[index] = state
    return filtered


def _soft_room(audio: np.ndarray, sample_rate: int, amount: float) -> np.ndarray:
    if audio.size == 0 or amount <= 0:
        return audio
    out = audio.copy()
    for delay_ms, gain in ((28, 0.34), (57, 0.21), (91, 0.12)):
        delay = max(1, int(sample_rate * delay_ms / 1000.0))
        if delay >= out.shape[0]:
            continue
        out[delay:] += audio[:-delay] * (amount * gain)
    return out


def _add_background_air(audio: np.ndarray, sample_rate: int, amount: float, seed: int) -> np.ndarray:
    if audio.size == 0 or amount <= 0:
        return audio
    rng = np.random.default_rng(seed)
    air = rng.normal(0.0, 1.0, size=audio.shape).astype(np.float32)
    air = _one_pole_lowpass(air, sample_rate, 1100.0)
    air_rms = float(np.sqrt(np.mean(np.square(air), dtype=np.float64))) or 1.0
    air = air / air_rms * amount

    voice_mono = np.mean(np.abs(audio), axis=1, keepdims=True)
    voice_gate = np.clip((voice_mono - 0.01) / 0.08, 0.0, 1.0)
    bed = air * (0.35 + 0.65 * voice_gate)
    return audio + bed


def _apply_fades(audio: np.ndarray, sample_rate: int, fade_ms: float) -> np.ndarray:
    fade_samples = int(sample_rate * fade_ms / 1000.0)
    if fade_samples <= 1 or audio.shape[0] <= fade_samples * 2:
        return audio
    curve = np.sin(np.linspace(0, math.pi / 2, fade_samples, dtype=np.float32)) ** 2
    audio[:fade_samples] *= curve.reshape(-1, 1)
    audio[-fade_samples:] *= curve[::-1].reshape(-1, 1)
    return audio


def _shape_dynamics(audio: np.ndarray, target_rms: float, peak_limit: float) -> np.ndarray:
    if audio.size == 0:
        return audio
    rms = float(np.sqrt(np.mean(np.square(audio), dtype=np.float64)))
    if rms > 0:
        audio = audio * np.clip(target_rms / rms, 0.55, 1.15)
    audio = np.tanh(audio * 1.12) / math.tanh(1.12)
    peak = float(np.max(np.abs(audio))) if audio.size else 0.0
    if peak > peak_limit > 0:
        audio = audio * (peak_limit / peak)
    return audio


def tts_wav_quality(path: str | Path) -> dict | None:
    loaded = _read_wav(Path(path))
    if loaded is None:
        return None

    sample_rate, audio = loaded
    mono = audio.mean(axis=1) if audio.ndim > 1 else audio.reshape(-1)
    if mono.size == 0:
        return {
            "duration_seconds": 0.0,
            "rms": 0.0,
            "peak": 0.0,
            "high_frequency_ratio": 1.0,
        }

    rms = float(np.sqrt(np.mean(np.square(mono), dtype=np.float64)))
    peak = float(np.max(np.abs(mono)))
    frequencies = np.fft.rfftfreq(mono.size, 1.0 / sample_rate)
    power = np.abs(np.fft.rfft(mono)) ** 2
    high_frequency_ratio = float(power[frequencies >= 6500].sum() / (power.sum() or 1.0))
    return {
        "duration_seconds": mono.size / float(sample_rate),
        "rms": rms,
        "peak": peak,
        "high_frequency_ratio": high_frequency_ratio,
    }


def cached_tts_wav_needs_repair(path: str | Path) -> bool:
    if not _env_bool("TTS_SOFTENING_ENABLED", True):
        return False

    quality = tts_wav_quality(path)
    if quality is None:
        return False

    max_peak = _env_float("TTS_CACHE_REPAIR_PEAK", 0.985, 0.2, 0.999)
    max_high_frequency_ratio = _env_float("TTS_CACHE_REPAIR_HIGH_FREQUENCY_RATIO", 0.055, 0.01, 0.5)
    return (
        quality["peak"] > max_peak
        or quality["high_frequency_ratio"] > max_high_frequency_ratio
    )


def ensure_tts_wav_quality(path: str | Path, language: str | None = None) -> str:
    wav_path = Path(path)
    if cached_tts_wav_needs_repair(wav_path):
        return postprocess_tts_wav(wav_path, language=language)
    return str(wav_path)


def postprocess_tts_wav(path: str | Path, language: str | None = None) -> str:
    """Make generated TTS less harsh while keeping the words intelligible."""
    if not _env_bool("TTS_SOFTENING_ENABLED", True):
        return str(path)

    wav_path = Path(path)
    loaded = _read_wav(wav_path)
    if loaded is None:
        return str(path)

    sample_rate, audio = loaded
    digest = hashlib.sha256(audio[: min(len(audio), sample_rate)].tobytes()).digest()
    seed = int.from_bytes(digest[:8], "little", signed=False)

    audio = audio - np.mean(audio, axis=0, keepdims=True)
    low_cut = _env_float("TTS_SOFTENING_LOW_PASS_HZ", 6200.0, 2600.0, sample_rate / 2 - 100)
    target_rms = _env_float("TTS_SOFTENING_TARGET_RMS", 0.115, 0.04, 0.35)
    peak_limit = _env_float("TTS_SOFTENING_PEAK_LIMIT", 0.82, 0.2, 0.98)
    room = _env_float("TTS_SOFTENING_ROOM", 0.08, 0.0, 0.35)
    air = _env_float("TTS_SOFTENING_BACKGROUND_AIR", 0.0022, 0.0, 0.012)
    fade_ms = _env_float("TTS_SOFTENING_FADE_MS", 16.0, 2.0, 60.0)

    audio = _one_pole_lowpass(audio, sample_rate, low_cut)
    audio = _soft_room(audio, sample_rate, room)
    audio = _add_background_air(audio, sample_rate, air, seed)
    audio = _shape_dynamics(audio, target_rms, peak_limit)
    audio = _apply_fades(audio, sample_rate, fade_ms)
    _write_wav(wav_path, sample_rate, audio)
    return str(wav_path)
