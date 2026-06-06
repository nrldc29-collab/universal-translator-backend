#!/usr/bin/env python3
"""Quick local stack verification after setup_models (no server required)."""

from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _post_json(url: str, payload: dict, headers: dict | None = None) -> tuple[int, dict | str]:
    body = json.dumps(payload).encode("utf-8")
    req_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=req_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return resp.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            return exc.code, json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            return exc.code, raw


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


def check_translate(base_url: str, auth: dict[str, str]) -> list[str]:
    errors: list[str] = []
    root = base_url.rstrip("/")

    status, payload = _post_json(
        f"{root}/translate/text",
        {
            "text": "hello",
            "source_language": "en",
            "target_language": "es",
            "session_id": "smoke-es",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate en->es failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "")
        if "hola" not in translated.lower():
            errors.append(f"translate en->es unexpected result: {translated!r}")

    status, payload = _post_json(
        f"{root}/translate/text",
        {
            "text": "I need help",
            "source_language": "en",
            "target_language": "ht",
            "session_id": "smoke-ht",
        },
        auth,
    )
    if status != 200 or not isinstance(payload, dict):
        errors.append(f"translate en->ht failed ({status}): {payload}")
    else:
        translated = str(payload.get("translated_text") or "")
        if "èd" not in translated.lower() and "ed" not in translated.lower():
            errors.append(f"translate en->ht glossary miss: {translated!r}")

    return errors


def check_tts(base_url: str, auth: dict[str, str]) -> list[str]:
    errors: list[str] = []
    root = base_url.rstrip("/")
    for language, text, label in (
        ("en", "hello", "en"),
        ("ht", "Mwen bezwen èd", "ht"),
    ):
        status, payload = _post_json(
            f"{root}/tts",
            {"text": text, "language": language},
            auth,
        )
        if status != 200 or not isinstance(payload, dict):
            errors.append(f"tts {label} failed ({status}): {payload}")
            continue
        if not (payload.get("audio_base64") or payload.get("audio_url")):
            errors.append(f"tts {label} returned no audio")
    return errors


def main() -> int:
    errors: list[str] = []
    errors.extend(check_imports())
    errors.extend(check_model_files())

    base_url = sys.argv[1] if len(sys.argv) > 1 else ""
    if base_url:
        errors.extend(check_health(base_url))
        login_status, login_payload = _post_json(
            f"{base_url.rstrip('/')}/auth/login",
            {"username": "demo", "password": "demo"},
        )
        if login_status != 200 or not isinstance(login_payload, dict) or not login_payload.get("access_token"):
            errors.append(f"auth login failed ({login_status}): {login_payload}")
        else:
            auth = {"Authorization": f"Bearer {login_payload['access_token']}"}
            errors.extend(check_translate(base_url, auth))
            errors.extend(check_tts(base_url, auth))

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
