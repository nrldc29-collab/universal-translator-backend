#!/usr/bin/env python3
"""Verify lifelike neural TTS is working (not robotic Piper/eSpeak fallback)."""

from __future__ import annotations

import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tts.piper_tts import PiperTextToSpeech
from tts.tts_readiness import ensure_neural_tts_deps, neural_tts_status


def main() -> int:
    status = ensure_neural_tts_deps()
    print("Neural TTS status:", status)
    if not status["neural_ready"]:
        print("FAIL: Neural TTS not ready — voice will sound robotic.")
        return 1

    engine = PiperTextToSpeech()
    samples = [
        ("en", "Hello, this is a lifelike neural voice test."),
        ("ht", "Bonjou, koman ou ye jodi a?"),
    ]
    for lang, text in samples:
        out = Path(tempfile.gettempdir()) / f"verify_neural_{lang}.wav"
        started = time.time()
        path = engine.synthesize(text, str(out), language=lang)
        size = Path(path).stat().st_size
        elapsed = round(time.time() - started, 1)
        if size < 50_000:
            print(f"FAIL {lang}: audio too small ({size} bytes) — likely robotic fallback")
            return 1
        print(f"OK {lang}: {size:,} bytes in {elapsed}s -> {path}")

    print("PASS: Neural Edge TTS is producing lifelike audio.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
