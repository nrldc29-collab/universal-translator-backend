#!/usr/bin/env python3
"""Download bundled Piper voices and verify local runtime dependencies."""

from __future__ import annotations

import shutil
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TTS_DIR = ROOT / "models" / "tts"

PIPER_VOICE_URLS = {
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    "es_MX-claude-high.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx",
    "es_MX-claude-high.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json",
}


def download_file(url: str, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip  {dest.name} (already present)")
        return
    print(f"fetch {dest.name}")
    urllib.request.urlretrieve(url, dest)


def main() -> int:
    errors: list[str] = []
    for subdir in ("whisper", "translation", "tts", "uploads"):
        (ROOT / "models" / subdir).mkdir(parents=True, exist_ok=True)

    for filename, url in PIPER_VOICE_URLS.items():
        try:
            download_file(url, TTS_DIR / filename)
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f"failed to download {filename}: {exc}")

    if not shutil.which("espeak-ng"):
        errors.append("espeak-ng not found on PATH (required for non-English TTS fallback)")

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        errors.append("faster-whisper not installed (pip install -r requirements.txt)")

    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        errors.append("transformers/torch not installed (required for Marian translation)")

    if errors:
        print("\nSetup incomplete:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("\nLocal model setup complete.")
    print("Whisper and Marian/NLLB models download automatically on first use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
