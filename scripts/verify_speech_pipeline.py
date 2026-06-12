#!/usr/bin/env python3
"""Verify translate + TTS endpoints for all configured languages."""
from __future__ import annotations

import base64
import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
TIMEOUT = 45

LANGS = [
    "en", "es", "fr", "de", "it", "pt", "nl", "ru", "zh", "ja", "ko", "ar", "hi", "ht",
]
SAMPLES = {
    "en": "Hello, how are you?",
    "es": "Hola, como estas?",
    "fr": "Bonjour, comment allez-vous?",
    "de": "Guten Tag, wie geht es Ihnen?",
    "it": "Ciao, come stai?",
    "pt": "Ola, como voce esta?",
    "nl": "Hallo, hoe gaat het?",
    "ru": "Privet, kak dela?",
    "zh": "Ni hao",
    "ja": "Konnichiwa",
    "ko": "Annyeonghaseyo",
    "ar": "Marhaba",
    "hi": "Namaste",
    "ht": "Bonjou, kijan ou ye?",
}


def post_json(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}{path}",
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        return json.loads(resp.read().decode("utf-8"))


def post_tts(text: str, language: str) -> bytes:
    req = urllib.request.Request(
        f"{BASE.rstrip('/')}/tts",
        data=json.dumps({"text": text, "language": language, "response_format": "base64"}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    audio_b64 = payload.get("audio_base64") or payload.get("audio") or ""
    if not audio_b64:
        return b""
    return base64.b64decode(audio_b64)


def main() -> int:
    print(f"Speech pipeline verify @ {BASE}\n")
    failures: list[str] = []

    # Health
    try:
        with urllib.request.urlopen(f"{BASE.rstrip('/')}/health", timeout=10) as r:
            health = json.loads(r.read().decode())
        print(f"health: ok={health.get('ok')} tts={health.get('tts', {}).get('available')}")
    except Exception as exc:
        print(f"FAIL health: {exc}")
        return 1

    # Translate all pairs en->X
    print("\n--- translate en -> each language ---")
    for tgt in LANGS:
        if tgt == "en":
            continue
        try:
            out = post_json(
                "/translate/text",
                {"text": SAMPLES["en"], "source_language": "en", "target_language": tgt},
            )
            tr = (out.get("translated_text") or "").strip()
            if not tr:
                failures.append(f"translate en->{tgt}: empty")
                print(f"  FAIL en->{tgt}: empty")
            else:
                preview = tr[:50].encode("ascii", errors="replace").decode("ascii")
                print(f"  OK en->{tgt}: {preview}...")
        except Exception as exc:
            failures.append(f"translate en->{tgt}: {exc}")
            print(f"  FAIL en->{tgt}: {exc}")

    # TTS each language
    print("\n--- TTS each language ---")
    for lang in LANGS:
        sample = SAMPLES.get(lang, "Hello")
        try:
            audio = post_tts(sample, lang)
            if len(audio) < 100:
                failures.append(f"tts {lang}: too small ({len(audio)} bytes)")
                print(f"  FAIL {lang}: {len(audio)} bytes")
            else:
                print(f"  OK {lang}: {len(audio)} bytes")
        except Exception as exc:
            failures.append(f"tts {lang}: {exc}")
            print(f"  FAIL {lang}: {exc}")

    # HT high-stakes glossary route
    print("\n--- HT glossary direct ---")
    try:
        out = post_json(
            "/translate/text",
            {"text": "I need a doctor", "source_language": "en", "target_language": "ht"},
        )
        tr = out.get("translated_text") or ""
        if "dokte" in tr.lower() or "mwen bezwen" in tr.lower():
            print(f"  OK glossary: {tr}")
        else:
            print(f"  WARN glossary: {tr}")
    except Exception as exc:
        failures.append(f"glossary: {exc}")
        print(f"  FAIL: {exc}")

    print(f"\n{'=' * 40}")
    if failures:
        print(f"FAILED ({len(failures)}):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("ALL SPEECH PIPELINE CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
