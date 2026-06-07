"""Neural TTS dependency checks — robotic fallbacks happen when these are missing."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys

logger = logging.getLogger(__name__)

EDGE_TTS_PACKAGE = "edge-tts==7.2.8"


def is_edge_tts_importable() -> bool:
    try:
        import edge_tts  # noqa: F401
        return True
    except ImportError:
        return False


def is_ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def is_neural_tts_ready() -> bool:
    return is_edge_tts_importable() and is_ffmpeg_available()


def neural_tts_status() -> dict:
    edge = is_edge_tts_importable()
    ffmpeg = is_ffmpeg_available()
    ready = edge and ffmpeg
    issues = []
    if not edge:
        issues.append("edge-tts package not installed (pip install edge-tts)")
    if not ffmpeg:
        issues.append("ffmpeg not on PATH (required to convert neural audio to WAV)")
    return {
        "neural_ready": ready,
        "edge_tts": edge,
        "ffmpeg": ffmpeg,
        "recommended_engine": "edge_neural" if ready else "piper_or_espeak_fallback",
        "issues": issues,
        "fix": "pip install -r requirements.txt" if issues else None,
    }


def ensure_neural_tts_deps(*, auto_install: bool = True) -> dict:
    """Install edge-tts when missing so voice does not fall back to robotic engines."""
    status = neural_tts_status()
    if status["neural_ready"] or not auto_install or status["edge_tts"]:
        return status
    logger.warning("edge-tts missing — installing %s for lifelike neural voice...", EDGE_TTS_PACKAGE)
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", EDGE_TTS_PACKAGE, "-q"],
            check=False,
            timeout=180,
            capture_output=True,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.warning("edge-tts auto-install failed: %s", exc)
    status = neural_tts_status()
    if status["neural_ready"]:
        logger.info("Neural TTS installed and ready (Edge + ffmpeg).")
    return status


def log_neural_tts_startup_warning() -> None:
    status = ensure_neural_tts_deps()
    if status["neural_ready"]:
        logger.info("Neural TTS ready (Edge + ffmpeg) — lifelike voice enabled.")
        return
    logger.warning(
        "Neural TTS NOT ready — translated voice will sound robotic until fixed: %s",
        "; ".join(status["issues"]),
    )
