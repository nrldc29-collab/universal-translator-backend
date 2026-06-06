#!/usr/bin/env python3
"""Quick local stack verification after setup_models (no server required)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def check_imports() -> list[str]:
    errors: list[str] = []
    for module in ("fastapi", "faster_whisper", "transformers", "torch", "piper"):
        try:
            __import__(module)
        except ImportError:
            errors.append(f"missing python package: {module}")
    return errors


def check_model_files() -> list[str]:
    errors: list[str] = []
    required = [
        ROOT / "models" / "tts" / "en_US-lessac-medium.onnx",
        ROOT / "models" / "tts" / "en_US-lessac-medium.onnx.json",
    ]
    for path in required:
        if not path.exists():
            errors.append(f"missing file: {path.relative_to(ROOT)}")
    return errors


def check_health(base_url: str) -> list[str]:
    errors: list[str] = []
    url = f"{base_url.rstrip('/')}/health"
    try:
        with urllib.request.urlopen(url, timeout=5) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        errors.append(f"health check failed ({url}): {exc}")
        return errors
    if not payload.get("ready"):
        blockers = payload.get("blockers") or []
        errors.append(f"backend not ready: {blockers or payload.get('status')}")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_imports())
    errors.extend(check_model_files())

    base_url = sys.argv[1] if len(sys.argv) > 1 else ""
    if base_url:
        errors.extend(check_health(base_url))

    if errors:
        print("Local smoke check failed:")
        for err in errors:
            print(f"  - {err}")
        return 1

    print("Local smoke check passed.")
    if not base_url:
        print("Tip: run `python scripts/smoke_local.py http://127.0.0.1:8000` with backend up.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
