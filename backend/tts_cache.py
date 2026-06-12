import base64
import hashlib
import shutil
import threading
import wave
from pathlib import Path
from typing import Callable
from uuid import uuid4

_render_locks: dict[str, threading.Lock] = {}
_render_locks_guard = threading.Lock()


def tts_cache_path(cache_key: str) -> Path:
    return Path("models/tts/cache") / f"{cache_key}.wav"


def is_tts_cache_key(cache_key: str) -> bool:
    return len(cache_key) == 64 and all(character in "0123456789abcdef" for character in cache_key)


def tts_cache_key(text: str, language: str, emotion_fingerprint: str = "") -> str:
    try:
        from backend.voice_effects import voice_cache_fingerprint

        voice_fingerprint = voice_cache_fingerprint()
    except Exception:
        voice_fingerprint = ""
    payload = f"{language}\0{text}\0{voice_fingerprint}"
    if emotion_fingerprint:
        payload = f"{payload}\0{emotion_fingerprint}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def legacy_tts_cache_key(text: str, language: str) -> str:
    return hashlib.sha256(f"{language}\0{text}".encode("utf-8")).hexdigest()


def is_valid_tts_wav(
    path: Path,
    minimum_duration_seconds: float = 0.08,
    maximum_duration_seconds: float | None = None,
) -> bool:
    try:
        if not path.is_file() or path.stat().st_size <= 128:
            return False
        with wave.open(str(path), "rb") as wav_file:
            frame_rate = wav_file.getframerate()
            frames = wav_file.getnframes()
            duration_seconds = frames / frame_rate if frame_rate else 0.0
            return (
                frame_rate > 0
                and frames >= int(frame_rate * minimum_duration_seconds)
                and (maximum_duration_seconds is None or duration_seconds <= maximum_duration_seconds)
                and wav_file.getnchannels() in {1, 2}
                and wav_file.getsampwidth() in {1, 2, 3, 4}
            )
    except (OSError, EOFError, wave.Error):
        return False


def _maximum_expected_duration(text: str) -> float:
    normalized = " ".join(text.split())
    word_count = max(1, len(normalized.split()))
    character_count = max(1, len(normalized))
    return max(5.0, (word_count * 1.2) + 2.0, (character_count / 6.0) + 3.0)


def _file_ready(path: Path, maximum_duration_seconds: float | None = None) -> bool:
    return is_valid_tts_wav(path, maximum_duration_seconds=maximum_duration_seconds)


def _lock_for_key(cache_key: str) -> threading.Lock:
    with _render_locks_guard:
        lock = _render_locks.get(cache_key)
        if lock is None:
            lock = threading.Lock()
            _render_locks[cache_key] = lock
        return lock


def _ready_cache_path(paths: list[Path], maximum_duration_seconds: float | None = None) -> Path | None:
    for path in paths:
        if _file_ready(path, maximum_duration_seconds):
            return path
        try:
            path.unlink(missing_ok=True)
        except (OSError, PermissionError):
            pass
    return None


def _copy_cache_alias(
    source: Path,
    target: Path,
    maximum_duration_seconds: float | None = None,
) -> None:
    if source == target or _file_ready(target, maximum_duration_seconds):
        return
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    except (OSError, PermissionError):
        pass


def _ensure_cache_audio_quality(path: Path, language: str) -> Path:
    try:
        from backend.voice_effects import ensure_tts_wav_quality

        return Path(ensure_tts_wav_quality(path, language=language))
    except Exception:
        return path


def cached_tts_payload(
    text: str,
    language: str,
    response_format: str,
    render_to_path: Callable[[Path], str | Path],
    *,
    emotion_fingerprint: str = "",
) -> dict:
    cache_dir = Path("models/tts/cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_key = tts_cache_key(text, language, emotion_fingerprint)
    legacy_key = legacy_tts_cache_key(text, language)
    output_path = tts_cache_path(cache_key)
    legacy_path = tts_cache_path(legacy_key)
    maximum_duration_seconds = _maximum_expected_duration(text)
    if emotion_fingerprint:
        candidate_paths = [output_path]
    else:
        candidate_paths = [output_path] if legacy_path == output_path else [output_path, legacy_path]
    ready_path = None
    cache_hit = False
    audio_bytes = None

    with _lock_for_key(cache_key):
        ready_path = _ready_cache_path(candidate_paths, maximum_duration_seconds)
        cache_hit = ready_path is not None
        if cache_hit:
            ready_path = _ensure_cache_audio_quality(ready_path, language)
        else:
            temp_path = Path("models/tts") / f"{uuid4()}.wav"
            temp_path.parent.mkdir(parents=True, exist_ok=True)
            rendered_path = _ensure_cache_audio_quality(Path(render_to_path(temp_path)), language)
            if not is_valid_tts_wav(rendered_path, maximum_duration_seconds=maximum_duration_seconds):
                raise RuntimeError("TTS returned invalid WAV audio.")
            audio_bytes = rendered_path.read_bytes()
            output_path.write_bytes(audio_bytes)
            if legacy_path != output_path:
                legacy_path.write_bytes(audio_bytes)
            ready_path = output_path
            if rendered_path != output_path and rendered_path != legacy_path:
                try:
                    rendered_path.unlink(missing_ok=True)
                except (OSError, PermissionError):
                    pass

    if ready_path is None:
        ready_path = output_path
    if ready_path == legacy_path:
        _copy_cache_alias(legacy_path, output_path, maximum_duration_seconds)

    audio_size = ready_path.stat().st_size if _file_ready(ready_path, maximum_duration_seconds) else 0

    response_dict = {
        "text": text,
        "language": language,
        "mime_type": "audio/wav",
        "audio_output_path": str(ready_path),
        "audio_url": f"/tts/audio/{cache_key}.wav",
        "audio_bytes": audio_size,
        "cache_hit": cache_hit,
    }
    if response_format in {"base64", "both"}:
        if audio_bytes is None:
            audio_bytes = ready_path.read_bytes()
        response_dict["audio_base64"] = base64.b64encode(audio_bytes).decode("ascii")
    return response_dict
