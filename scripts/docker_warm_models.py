#!/usr/bin/env python3
"""Prefetch EN↔HT Hugging Face assets into the Docker image without loading torch."""

from __future__ import annotations

import os
import sys

REPO_IDS = (
    "Systran/faster-whisper-tiny",
    "Helsinki-NLP/opus-mt-en-ht",
    "Helsinki-NLP/opus-mt-ht-en",
    "facebook/nllb-200-distilled-600M",
)


def main() -> int:
    os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
    os.environ.setdefault("HF_HUB_DOWNLOAD_TIMEOUT", "300")
    try:
        from huggingface_hub import snapshot_download
    except ImportError:
        print("huggingface_hub not installed", file=sys.stderr)
        return 1

    cache_dir = os.environ.get("HF_HOME") or os.path.expanduser("~/.cache/huggingface")
    for repo_id in REPO_IDS:
        print(f"prefetch {repo_id}")
        snapshot_download(repo_id, cache_dir=cache_dir)
    print("Docker EN↔HT model prefetch complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
