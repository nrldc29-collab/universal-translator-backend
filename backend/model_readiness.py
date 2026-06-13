"""Evaluate whether required local models and tools are present for full operation."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from backend.config import get_preload_models, get_stt_provider, get_translation_backend
from tts.piper_tts import DEFAULT_VOICES
from tts.tts_readiness import is_neural_tts_ready


def espeak_available() -> bool:
    return shutil.which("espeak-ng") is not None or shutil.which("espeak") is not None


def check_piper_voices() -> dict[str, Any]:
    present: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    for lang, path in DEFAULT_VOICES.items():
        voice_path = Path(path)
        config_path = Path(f"{path}.json")
        entry = {"lang": lang, "path": path}
        if voice_path.exists() and config_path.exists():
            present.append(entry)
        else:
            missing.append(entry)
    return {"present": present, "missing": missing}


def _component_ok(value: Any) -> bool:
    if value is True:
        return True
    if isinstance(value, dict):
        return bool(value.get("ok"))
    return False


def evaluate_preload_result(preload: dict[str, Any] | None) -> dict[str, Any]:
    """Return readiness summary from pipeline.preload() output."""
    preload = preload or {}
    lazy_startup = not preload and not get_preload_models()
    blockers: list[str] = []
    warnings: list[str] = []

    stt_mode = get_stt_provider()
    if stt_mode == "streaming":
        if not lazy_startup and not _component_ok(preload.get("stt")):
            blockers.append("stt_streaming_provider_unreachable")
    elif not lazy_startup and not _component_ok(preload.get("stt")):
        blockers.append("stt_preload_failed")
    elif lazy_startup:
        warnings.append("stt_lazy_load_deferred")

    translation = preload.get("translation")
    backend = get_translation_backend()
    if not lazy_startup and backend in {"marian", "hybrid"}:
        if isinstance(translation, str) and translation.startswith("warmup_failed"):
            blockers.append("translation_preload_failed")
        elif isinstance(translation, dict) and not translation.get("ok", False):
            blockers.append("translation_preload_failed")

    voices = check_piper_voices()
    has_piper = bool(voices["present"])
    has_espeak = espeak_available()
    neural_ready = is_neural_tts_ready()
    if not lazy_startup and not _component_ok(preload.get("tts")):
        warnings.append("tts_piper_preload_failed")
    if voices["missing"] and not has_espeak and not neural_ready:
        blockers.append("tts_no_piper_voices_or_espeak")
    elif voices["missing"] and has_espeak:
        warnings.append("tts_using_espeak_fallback_for_missing_piper_voices")
    elif voices["missing"] and neural_ready:
        warnings.append("tts_using_neural_fallback_for_missing_piper_voices")
    if not has_espeak and not neural_ready:
        blockers.append("espeak_missing_ht_tts_unavailable")
    elif not has_espeak and neural_ready:
        warnings.append("espeak_missing_using_neural_ht_tts")

    return {
        "ready": len(blockers) == 0,
        "blockers": blockers,
        "warnings": warnings,
        "stt_provider": stt_mode,
        "translation_backend": backend,
        "piper_voices": voices,
        "espeak_available": has_espeak,
        "has_piper_voice": has_piper,
        "neural_tts_ready": neural_ready,
    }
