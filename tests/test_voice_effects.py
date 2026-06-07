import contextlib
import wave

import numpy as np

from backend.voice_effects import postprocess_tts_wav, voice_cache_fingerprint


def _write_wav(path, sample_rate, audio):
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with contextlib.closing(wave.open(str(path), "wb")) as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def _read_wav(path):
    with contextlib.closing(wave.open(str(path), "rb")) as wav_file:
        sample_rate = wav_file.getframerate()
        raw = wav_file.readframes(wav_file.getnframes())
    return sample_rate, np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0


def _high_frequency_ratio(audio, sample_rate, cutoff=6500):
    spectrum = np.fft.rfft(audio)
    freqs = np.fft.rfftfreq(audio.size, 1.0 / sample_rate)
    power = np.abs(spectrum) ** 2
    total = float(np.sum(power)) or 1.0
    return float(np.sum(power[freqs >= cutoff]) / total)


def test_postprocess_tts_wav_softens_harsh_audio(tmp_path, monkeypatch):
    monkeypatch.setenv("TTS_SOFTENING_ENABLED", "true")
    monkeypatch.setenv("TTS_SOFTENING_BACKGROUND_AIR", "0")
    sample_rate = 22050
    duration = 0.5
    t = np.arange(int(sample_rate * duration), dtype=np.float32) / sample_rate
    audio = 0.35 * np.sin(2 * np.pi * 450 * t) + 0.2 * np.sin(2 * np.pi * 8200 * t)
    path = tmp_path / "robotic.wav"
    _write_wav(path, sample_rate, audio)

    before_ratio = _high_frequency_ratio(audio, sample_rate)
    postprocess_tts_wav(path, language="en")
    out_rate, softened = _read_wav(path)

    assert out_rate == sample_rate
    assert softened.size == audio.size
    assert np.max(np.abs(softened)) <= 0.83
    assert _high_frequency_ratio(softened, sample_rate) < before_ratio


def test_voice_cache_fingerprint_includes_voice_profile(monkeypatch):
    monkeypatch.setenv("TTS_VOICE_PROFILE", "soothing")
    soothing = voice_cache_fingerprint()
    monkeypatch.setenv("TTS_VOICE_PROFILE", "plain")
    assert voice_cache_fingerprint() != soothing


def test_soothing_profile_softens_more_than_plain(tmp_path, monkeypatch):
    monkeypatch.setenv("TTS_SOFTENING_ENABLED", "true")
    monkeypatch.setenv("TTS_SOFTENING_BACKGROUND_AIR", "0")
    sample_rate = 22050
    duration = 0.5
    t = np.arange(int(sample_rate * duration), dtype=np.float32) / sample_rate
    harsh = 0.35 * np.sin(2 * np.pi * 450 * t) + 0.2 * np.sin(2 * np.pi * 8200 * t)

    plain_path = tmp_path / "plain.wav"
    soothing_path = tmp_path / "soothing.wav"
    _write_wav(plain_path, sample_rate, harsh)
    _write_wav(soothing_path, sample_rate, harsh)

    monkeypatch.setenv("TTS_VOICE_PROFILE", "plain")
    postprocess_tts_wav(plain_path, language="en")
    monkeypatch.setenv("TTS_VOICE_PROFILE", "soothing")
    postprocess_tts_wav(soothing_path, language="en")

    _, plain_audio = _read_wav(plain_path)
    _, soothing_audio = _read_wav(soothing_path)
    assert _high_frequency_ratio(soothing_audio, sample_rate) <= _high_frequency_ratio(plain_audio, sample_rate)
