#!/usr/bin/env python3
"""Download bundled Piper voices and verify local runtime dependencies."""

from __future__ import annotations

import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TTS_DIR = ROOT / "models" / "tts"

PIPER_VOICE_URLS = {
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
    "es_MX-claude-high.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx",
    "es_MX-claude-high.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json",
}


def download_file(url: str, dest: Path, *, retries: int = 5) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip  {dest.name} (already present)")
        return
    print(f"fetch {dest.name}")
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            urllib.request.urlretrieve(url, dest)
            return
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in {429, 500, 502, 503, 504} and attempt + 1 < retries:
                delay = min(30, 2 ** attempt)
                print(f"retry {dest.name} in {delay}s ({exc.code})")
                time.sleep(delay)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                delay = min(30, 2 ** attempt)
                print(f"retry {dest.name} in {delay}s ({exc.__class__.__name__})")
                time.sleep(delay)
                continue
            raise
    if last_error is not None:
        raise last_error


def warm_translation() -> None:
    from translation.marian_translator import MarianTranslator

    translator = MarianTranslator()
    result = translator.translate("hello", "en", "es")
    if not result or result.startswith("[en->es]"):
        raise RuntimeError(f"translation warmup failed: {result!r}")
    print(f"warm  translation en->es ({result!r})")
    ht_result = translator.translate("I need help", "en", "ht")
    if not ht_result or ht_result.startswith("[en->ht]"):
        raise RuntimeError(f"en->ht translation warmup failed: {ht_result!r}")
    print(f"warm  translation en->ht ({ht_result!r})")
    ht_en = translator.translate("mwen bezwen èd", "ht", "en")
    if not ht_en or ht_en.startswith("[ht->en]"):
        raise RuntimeError(f"ht->en translation warmup failed: {ht_en!r}")
    print(f"warm  translation ht->en ({ht_en!r})")


def warm_whisper() -> None:
    from backend.config import get_whisper_compute_type, get_whisper_device, get_whisper_model_size
    from speech.whisper_stt import WhisperSpeechToText

    model_size = get_whisper_model_size()
    stt = WhisperSpeechToText(
        model_size=model_size,
        device=get_whisper_device(),
        compute_type=get_whisper_compute_type(),
    )
    if not stt.preload():
        raise RuntimeError("whisper preload returned false")
    print(f"warm  whisper ({model_size})")


def espeak_installed() -> bool:
    return bool(shutil.which("espeak-ng") or shutil.which("espeak"))


def ensure_espeak_ng() -> bool:
    """Install espeak-ng on Debian/Ubuntu when missing (required for HT/fr TTS)."""
    if espeak_installed():
        return True
    if sys.platform != "linux":
        return False
    for cmd in (
        ["apt-get", "install", "-y", "espeak-ng"],
        ["sudo", "apt-get", "install", "-y", "espeak-ng"],
    ):
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
            if result.returncode == 0 and espeak_installed():
                print("install espeak-ng")
                return True
        except (OSError, subprocess.TimeoutExpired):
            continue
    return False


def warm_tts() -> None:
    from tts.piper_tts import PiperTextToSpeech

    tts = PiperTextToSpeech()
    if not tts.preload():
        raise RuntimeError("piper preload returned false")
    out = tts.synthesize("ready", str(ROOT / "models" / "tts" / "setup-warmup.wav"), language="en")
    if not out:
        raise RuntimeError("tts synthesis warmup failed")
    print("warm  tts (en)")


def warm_tts_ht() -> None:
    if not espeak_installed():
        raise RuntimeError("espeak-ng or espeak not found (required for Haitian Creole TTS warmup)")
    from tts.piper_tts import PiperTextToSpeech

    tts = PiperTextToSpeech()
    out = tts.synthesize("bonjou", str(ROOT / "models" / "tts" / "setup-warmup-ht.wav"), language="ht")
    if not out:
        raise RuntimeError("ht tts warmup failed")
    print("warm  tts (ht)")


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []
    for subdir in ("whisper", "translation", "tts", "uploads"):
        (ROOT / "models" / subdir).mkdir(parents=True, exist_ok=True)

    for filename, url in PIPER_VOICE_URLS.items():
        try:
            download_file(url, TTS_DIR / filename)
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f"failed to download {filename}: {exc}")

    if not ensure_espeak_ng() and not espeak_installed():
        errors.append(
            "espeak-ng or espeak not found (required for Haitian Creole TTS). "
            "Linux: apt install espeak-ng · macOS: brew install espeak · Windows: choco install espeak-ng"
        )

    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        errors.append("faster-whisper not installed (pip install -r requirements.txt)")
    else:
        try:
            warm_whisper()
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append(f"whisper warmup failed: {exc}")

    try:
        import transformers  # noqa: F401
        import torch  # noqa: F401
    except ImportError:
        errors.append("transformers/torch not installed (required for Marian translation)")
    else:
        try:
            warm_translation()
        except (RuntimeError, OSError, ValueError) as exc:
            errors.append(f"translation warmup failed: {exc}")

    try:
        warm_tts()
        warm_tts_ht()
    except (RuntimeError, OSError, ValueError, ImportError) as exc:
        errors.append(f"tts warmup failed: {exc}")

    if errors:
        print("\nSetup incomplete:")
        for err in errors:
            print(f"  - {err}")
        return 1

    if warnings:
        print("\nSetup warnings:")
        for warn in warnings:
            print(f"  - {warn}")

    print("\nLocal model setup complete.")
    print("STT, translation, and TTS are pre-warmed for first use.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
