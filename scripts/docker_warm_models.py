#!/usr/bin/env python3
"""Bake EN↔HT model weights into the Railway Docker image at build time."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts import setup_models


def main() -> int:
    setup_models._configure_hf_hub()
    for subdir in ("whisper", "translation", "tts", "uploads"):
        (ROOT / "models" / subdir).mkdir(parents=True, exist_ok=True)

    setup_models.ensure_espeak_ng()
    setup_models.warm_whisper()
    setup_models.warm_translation()
    setup_models.warm_tts()
    setup_models.warm_tts_ht()
    print("Docker EN↔HT model warmup complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
