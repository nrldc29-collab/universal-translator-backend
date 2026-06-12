import contextlib
import wave
from pathlib import Path

import numpy as np

from backend.tts_cache import cached_tts_payload, legacy_tts_cache_key, tts_cache_key, tts_cache_path
from backend.streaming import _synthesize_live_tts_chunk, _unlink_temp_tts_file


def _write_wav(path, sample_rate=22050, amplitude=1.0, duration_seconds=0.25):
    path.parent.mkdir(parents=True, exist_ok=True)
    t = np.arange(int(sample_rate * duration_seconds), dtype=np.float32) / sample_rate
    audio = amplitude * np.sin(2 * np.pi * 440 * t)
    pcm = np.clip(audio * 32767.0, -32768, 32767).astype(np.int16)
    with contextlib.closing(wave.open(str(path), "wb")) as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())


def _peak(path):
    with contextlib.closing(wave.open(str(path), "rb")) as wav_file:
        samples = np.frombuffer(wav_file.readframes(wav_file.getnframes()), dtype=np.int16)
    return float(np.max(np.abs(samples.astype(np.float32) / 32768.0)))


def test_cached_tts_payload_reuses_existing_audio(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    calls = []

    def render(temp_path):
        calls.append(temp_path)
        _write_wav(temp_path)
        return temp_path

    first = cached_tts_payload("Bonjour.", "fr", "url", render)
    second = cached_tts_payload("Bonjour.", "fr", "url", render)

    assert first["cache_hit"] is False
    assert second["cache_hit"] is True
    assert first["audio_output_path"] == second["audio_output_path"]
    assert len(calls) == 1


def test_cached_tts_payload_repairs_clipped_cache_hit(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("TTS_SOFTENING_ENABLED", "true")
    monkeypatch.setenv("TTS_SOFTENING_BACKGROUND_AIR", "0")
    text = "Bonjour."
    language = "fr"
    cache_path = tts_cache_path(tts_cache_key(text, language))
    _write_wav(cache_path, amplitude=1.0)
    assert _peak(cache_path) > 0.985

    def render(_temp_path):
        raise AssertionError("render should not be called for an existing cache hit")

    payload = cached_tts_payload(text, language, "url", render)

    assert payload["cache_hit"] is True
    assert payload["audio_output_path"] == str(cache_path)
    assert _peak(cache_path) <= 0.83


def test_cached_tts_payload_regenerates_invalid_riff_stub(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    text = "Bonjou"
    language = "ht"
    cache_path = tts_cache_path(tts_cache_key(text, language))
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(b"RIFF" + (b"\0" * 96))
    calls = []

    def render(temp_path):
        calls.append(temp_path)
        _write_wav(temp_path)
        return temp_path

    payload = cached_tts_payload(text, language, "url", render)

    assert payload["cache_hit"] is False
    assert len(calls) == 1
    with contextlib.closing(wave.open(payload["audio_output_path"], "rb")) as wav_file:
        assert wav_file.getnframes() > 0


def test_cached_tts_payload_regenerates_implausibly_long_legacy_audio(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    text = "Hola"
    language = "es"
    legacy_path = tts_cache_path(legacy_tts_cache_key(text, language))
    _write_wav(legacy_path, duration_seconds=12.0)
    calls = []

    def render(temp_path):
        calls.append(temp_path)
        _write_wav(temp_path, duration_seconds=0.5)
        return temp_path

    payload = cached_tts_payload(text, language, "url", render)

    assert payload["cache_hit"] is False
    assert len(calls) == 1
    with contextlib.closing(wave.open(payload["audio_output_path"], "rb")) as wav_file:
        assert wav_file.getnframes() / wav_file.getframerate() == 0.5


def test_live_neutral_tts_chunk_uses_shared_cache(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class FakeTts:
        def __init__(self):
            self.calls = 0

        def synthesize(self, text, output_path, language=None, google_api_key=None, emotion_config=None):
            self.calls += 1
            _write_wav(Path(output_path))
            return output_path

    engine = FakeTts()
    first = _synthesize_live_tts_chunk(engine, "Bonjour.", tmp_path / "first.wav", "fr")
    second = _synthesize_live_tts_chunk(engine, "Bonjour.", tmp_path / "second.wav", "fr")

    assert first == second
    assert engine.calls == 1


def test_live_cache_cleanup_preserves_shared_cache(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class FakeTts:
        def __init__(self):
            self.calls = 0

        def synthesize(self, text, output_path, language=None, google_api_key=None, emotion_config=None):
            self.calls += 1
            _write_wav(Path(output_path))
            return output_path

    engine = FakeTts()
    cached_path = _synthesize_live_tts_chunk(engine, "Bonjour.", tmp_path / "first.wav", "fr")
    temp_path = tmp_path / "models" / "tts" / "temporary-live.wav"
    temp_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path.write_bytes(b"temp")

    _unlink_temp_tts_file(cached_path)
    _unlink_temp_tts_file(temp_path)
    second = _synthesize_live_tts_chunk(engine, "Bonjour.", tmp_path / "second.wav", "fr")

    assert temp_path.exists() is False
    assert tts_cache_path(tts_cache_key("Bonjour.", "fr")).is_file()
    assert second == cached_path
    assert engine.calls == 1


def test_live_emotional_tts_chunk_uses_separate_cache(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)

    class FakeTts:
        def __init__(self):
            self.calls = 0

        def synthesize(self, text, output_path, language=None, google_api_key=None, emotion_config=None):
            self.calls += 1
            _write_wav(Path(output_path))
            return output_path

    engine = FakeTts()
    neutral = _synthesize_live_tts_chunk(engine, "Bonjour.", tmp_path / "neutral.wav", "fr")
    emotional = _synthesize_live_tts_chunk(
        engine,
        "Bonjour.",
        tmp_path / "emotional.wav",
        "fr",
        emotion_config={"speed": 0.85},
    )

    assert "cache" in neutral.replace("\\", "/")
    assert "cache" in emotional.replace("\\", "/")
    assert neutral != emotional
    assert engine.calls == 2
