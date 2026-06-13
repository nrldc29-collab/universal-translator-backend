#!/usr/bin/env python3
"""Download bundled Piper voices and verify local runtime dependencies."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TTS_DIR = ROOT / "models" / "tts"

# Required for the default EN↔HT path (English Piper + Haitian Creole via eSpeak).
REQUIRED_PIPER_VOICE_URLS = {
    "en_US-lessac-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx",
    "en_US-lessac-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json",
}

# Bundled Piper voices for all DEFAULT_VOICES languages in tts/piper_tts.py.
# Missing files fall back to neural TTS; downloading them removes readiness warnings.
OPTIONAL_PIPER_VOICE_URLS = {
    "es_ES-carlfm-x_low.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx",
    "es_ES-carlfm-x_low.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx.json",
    "fr_FR-siwis-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx",
    "fr_FR-siwis-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/fr/fr_FR/siwis/medium/fr_FR-siwis-medium.onnx.json",
    "de_DE-thorsten-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx",
    "de_DE-thorsten-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/de/de_DE/thorsten/medium/de_DE-thorsten-medium.onnx.json",
    "it_IT-riccardo-x_low.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/riccardo/x_low/it_IT-riccardo-x_low.onnx",
    "it_IT-riccardo-x_low.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/it/it_IT/riccardo/x_low/it_IT-riccardo-x_low.onnx.json",
    "pt_BR-faber-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx",
    "pt_BR-faber-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/pt/pt_BR/faber/medium/pt_BR-faber-medium.onnx.json",
    "nl_NL-ronnie-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/ronnie/medium/nl_NL-ronnie-medium.onnx",
    "nl_NL-ronnie-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/ronnie/medium/nl_NL-ronnie-medium.onnx.json",
    "ru_RU-dmitri-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx",
    "ru_RU-dmitri-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/dmitri/medium/ru_RU-dmitri-medium.onnx.json",
    "zh_CN-huayan-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx",
    "zh_CN-huayan-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/zh/zh_CN/huayan/medium/zh_CN-huayan-medium.onnx.json",
    "ar_JO-kareem-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx",
    "ar_JO-kareem-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/ar/ar_JO/kareem/medium/ar_JO-kareem-medium.onnx.json",
    "hi_IN-pratham-medium.onnx": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx",
    "hi_IN-pratham-medium.onnx.json": "https://huggingface.co/rhasspy/piper-voices/resolve/main/hi/hi_IN/pratham/medium/hi_IN-pratham-medium.onnx.json",
}

PIPER_VOICE_URLS = {**REQUIRED_PIPER_VOICE_URLS, **OPTIONAL_PIPER_VOICE_URLS}

DOWNLOAD_RETRIES = 10
DOWNLOAD_RETRYABLE_CODES = {429, 500, 502, 503, 504}
WARM_RETRIES = 10


def _configure_hf_hub() -> None:
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
    os.environ.setdefault("HF_HUB_ETAG_TIMEOUT", "60")


def download_file(url: str, dest: Path, *, retries: int = DOWNLOAD_RETRIES) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"skip  {dest.name} (already present)")
        return
    print(f"fetch {dest.name}")
    last_error: Exception | None = None
    request = urllib.request.Request(url, headers={"User-Agent": "anai-translator-setup/1.0"})
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=120) as response:
                dest.write_bytes(response.read())
            return
        except urllib.error.HTTPError as exc:
            last_error = exc
            if exc.code in DOWNLOAD_RETRYABLE_CODES and attempt + 1 < retries:
                delay = min(60, 2 ** attempt * 2)
                print(f"retry {dest.name} in {delay}s ({exc.code})")
                time.sleep(delay)
                continue
            raise
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < retries:
                delay = min(60, 2 ** attempt * 2)
                print(f"retry {dest.name} in {delay}s ({exc.__class__.__name__})")
                time.sleep(delay)
                continue
            raise
    if last_error is not None:
        raise last_error


def retry_warm(label: str, fn: Callable[[], None], *, retries: int = WARM_RETRIES) -> None:
    last_error: Exception | None = None
    for attempt in range(retries):
        try:
            fn()
            return
        except (RuntimeError, OSError, ValueError) as exc:
            last_error = exc
            message = str(exc).lower()
            retryable = any(token in message for token in ("429", "too many requests", "timed out", "connection"))
            if retryable and attempt + 1 < retries:
                delay = min(60, 2 ** attempt * 3)
                print(f"retry {label} in {delay}s ({exc.__class__.__name__})")
                time.sleep(delay)
                continue
            raise
    if last_error is not None:
        raise last_error


def warm_translation() -> None:
    from translation.marian_translator import MarianTranslator

    translator = MarianTranslator()

    def _warm_en_ht() -> None:
        ht_result = translator.translate("I need help", "en", "ht")
        if not ht_result or ht_result.startswith("[en->ht]"):
            raise RuntimeError(f"en->ht translation warmup failed: {ht_result!r}")
        print(f"warm  translation en->ht ({ht_result!r})")

    def _warm_ht_en() -> None:
        ht_en = translator.translate("mwen bezwen èd", "ht", "en")
        if not ht_en or ht_en.startswith("[ht->en]"):
            raise RuntimeError(f"ht->en translation warmup failed: {ht_en!r}")
        print(f"warm  translation ht->en ({ht_en!r})")

    retry_warm("translation en->ht", _warm_en_ht)
    retry_warm("translation ht->en", _warm_ht_en)

    try:
        result = translator.translate("hello", "en", "es")
        if not result or result.startswith("[en->es]"):
            raise RuntimeError(f"translation warmup failed: {result!r}")
        print(f"warm  translation en->es ({result!r})")
    except (RuntimeError, OSError, ValueError) as exc:
        print(f"warn  optional en->es translation warmup skipped: {exc}")


def warm_whisper() -> None:
    from backend.config import get_whisper_compute_type, get_whisper_device, get_whisper_model_size
    from speech.whisper_stt import WhisperSpeechToText

    model_size = get_whisper_model_size()

    def _warm() -> None:
        stt = WhisperSpeechToText(
            model_size=model_size,
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        if not stt.preload():
            raise RuntimeError("whisper preload returned false")
        print(f"warm  whisper ({model_size})")

    retry_warm("whisper", _warm)


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
    _configure_hf_hub()
    errors: list[str] = []
    warnings: list[str] = []
    for subdir in ("whisper", "translation", "tts", "uploads"):
        (ROOT / "models" / subdir).mkdir(parents=True, exist_ok=True)

    for filename, url in REQUIRED_PIPER_VOICE_URLS.items():
        try:
            download_file(url, TTS_DIR / filename)
        except (OSError, urllib.error.URLError) as exc:
            errors.append(f"failed to download {filename}: {exc}")
        time.sleep(0.5)

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

    for filename, url in OPTIONAL_PIPER_VOICE_URLS.items():
        try:
            download_file(url, TTS_DIR / filename)
        except (OSError, urllib.error.URLError) as exc:
            warnings.append(f"optional voice not downloaded ({filename}): {exc}")
        time.sleep(0.5)

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
