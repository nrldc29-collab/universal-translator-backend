"""Robust audio decoding helpers.

iOS Safari produces non-standard WebM streams (chunks past the first lack a
container header) which makes faster-whisper / torchaudio fail with
``[Errno 1094995529] Invalid data found when processing input``. This module
provides a small ffmpeg-backed fallback that re-muxes any input to clean
mono 16 kHz PCM WAV — a format every downstream component can read.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Iterable

logger = logging.getLogger(__name__)


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def _candidate_input_formats(suffix: str) -> Iterable[str | None]:
    """Yield -f hints for ffmpeg, starting with auto-detection."""
    yield None  # let ffmpeg sniff the container
    suffix = (suffix or "").lower().lstrip(".")
    if suffix in {"webm", "weba", "opus"}:
        # iOS sometimes mislabels mp4 as webm and vice versa.
        for fmt in ("matroska", "webm", "mp4", "ogg", "wav"):
            yield fmt
    elif suffix in {"m4a", "mp4", "aac"}:
        for fmt in ("mp4", "matroska", "wav"):
            yield fmt
    elif suffix in {"ogg", "oga"}:
        for fmt in ("ogg", "matroska", "wav"):
            yield fmt
    else:
        for fmt in ("matroska", "mp4", "ogg", "wav"):
            yield fmt


def transcode_to_wav(input_path: str, output_path: str | None = None) -> str | None:
    """Convert ``input_path`` to mono 16 kHz WAV using ffmpeg.

    Returns the output path on success, ``None`` on failure. Caller owns
    cleanup of the produced file.
    """
    src = Path(input_path)
    if not src.exists() or src.stat().st_size == 0:
        return None

    if not ffmpeg_available():
        logger.warning("ffmpeg not available; cannot transcode %s", input_path)
        return None

    if output_path is None:
        with NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
            output_path = tmp.name

    suffix = src.suffix
    last_error: str | None = None
    for fmt_hint in _candidate_input_formats(suffix):
        cmd: list[str] = [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-fflags",
            "+genpts+igndts",
            "-err_detect",
            "ignore_err",
        ]
        if fmt_hint:
            cmd += ["-f", fmt_hint]
        cmd += [
            "-i",
            str(src),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "16000",
            "-acodec",
            "pcm_s16le",
            output_path,
        ]
        try:
            result = subprocess.run(
                cmd,
                check=False,
                capture_output=True,
                timeout=12,
            )
        except subprocess.TimeoutExpired:
            last_error = "ffmpeg timed out"
            continue
        if result.returncode == 0 and Path(output_path).stat().st_size > 44:
            return output_path
        last_error = (result.stderr or b"").decode("utf-8", errors="replace").strip()

    logger.warning(
        "ffmpeg failed to transcode %s (%s): %s",
        input_path,
        suffix,
        last_error or "unknown error",
    )
    Path(output_path).unlink(missing_ok=True)
    return None


def transcode_bytes_to_wav(audio_bytes: bytes, suffix: str = ".webm") -> str | None:
    """Persist ``audio_bytes`` to a temp file, then transcode it to WAV."""
    if not audio_bytes:
        return None
    with NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(audio_bytes)
        src_path = tmp.name
    try:
        return transcode_to_wav(src_path)
    finally:
        Path(src_path).unlink(missing_ok=True)
