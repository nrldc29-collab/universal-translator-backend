"""Verify barrier routing picks the correct language and direction."""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.pipeline import AnaiTranslatorPipeline, TranslationResult
from backend.speakers import detect_language_heuristic, resolve_barrier_route

TARGET_SAMPLES = {
    "es": "Hola, buenos días",
    "ht": "Bonjou",
    "fr": "Bonjour",
    "de": "Guten Tag",
    "it": "Ciao",
    "pt": "Olá",
    "nl": "Hallo, dank je wel",
    "ru": "Привет",
    "zh": "你好",
    "ja": "こんにちは",
    "ko": "안녕하세요",
    "ar": "مرحبا",
    "hi": "नमस्ते",
}

WS_BARRIER_CASES = [
    ("Bonjour", "en", "fr", "fr", "en"),
    ("Hello there", "en", "fr", "en", "fr"),
    ("hallo", "en", "nl", "nl", "en"),
    ("Olá", "en", "pt", "pt", "en"),
]


def _verify_websocket_barrier_routing() -> list[str]:
    failures: list[str] = []
    api = importlib.import_module("backend.api")
    api.runtime_state["ready"] = True
    api.session_registry.cleanup()

    original_translate = api.pipeline.translate_text

    def fast_translate(text, source_language, target_language, **kwargs):
        return TranslationResult(
            source_text=text,
            improved_text=text,
            translated_text=f"[{source_language}->{target_language}] {text}",
            audio_output_path=None,
        )

    api.pipeline.translate_text = fast_translate

    import backend.api_health as api_health
    import backend.config as config

    original_provider = config.get_stt_provider
    original_api_provider = api.get_stt_provider
    original_warmup = api_health.voice_warmup_blocks_ready
    streaming_provider = lambda: "streaming"
    config.get_stt_provider = streaming_provider
    api.get_stt_provider = streaming_provider
    api_health.voice_warmup_blocks_ready = lambda: False

    from fastapi.testclient import TestClient

    client = TestClient(api.app)
    try:
        print("=== WEBSOCKET BARRIER ROUTING (/ws/audio) ===")
        for text, src, tgt, exp_src, exp_tgt in WS_BARRIER_CASES:
            try:
                with client.websocket_connect("/ws/audio") as ws:
                    ready = ws.receive_json()
                    if ready.get("type") != "ready":
                        failures.append(f"ws ready en->{tgt}: {ready}")
                        print(f"FAIL ws en->{tgt}: socket not ready")
                        continue

                    ws.send_json(
                        {
                            "type": "config",
                            "source_language": src,
                            "target_language": tgt,
                            "barrier_mode": True,
                            "speaker_mode": "manual",
                        }
                    )
                    translation = None
                    for _ in range(20):
                        message = ws.receive_json()
                        if message.get("type") == "config_ack":
                            ws.send_json({"type": "translate", "text": text})
                        elif message.get("type") == "translation":
                            translation = message
                            break

                    if translation is None:
                        failures.append(f"ws barrier en->{tgt}: no translation for {text!r}")
                        print(f"FAIL ws en->{tgt}: no translation for {text!r}")
                        continue

                    got_src = translation.get("source_language")
                    got_tgt = translation.get("target_language")
                    ok = got_src == exp_src and got_tgt == exp_tgt
                    print(
                        f"{'PASS' if ok else 'FAIL'} ws en->{tgt}: {text!r} => "
                        f"{got_src}->{got_tgt} speaker={translation.get('speaker')}"
                    )
                    if not ok:
                        failures.append(
                            f"ws barrier en->{tgt}: {text!r} routed {got_src}->{got_tgt}, "
                            f"expected {exp_src}->{exp_tgt}"
                        )
            except Exception as exc:
                failures.append(f"ws barrier en->{tgt}: {text!r} raised {exc}")
                print(f"FAIL ws en->{tgt}: {text!r} raised {exc}")
    finally:
        api.pipeline.translate_text = original_translate
        config.get_stt_provider = original_provider
        api.get_stt_provider = original_api_provider
        api_health.voice_warmup_blocks_ready = original_warmup
        api.session_registry.cleanup()

    return failures


def main() -> int:
    failures: list[str] = []
    pipeline = AnaiTranslatorPipeline()

    print("=== BARRIER ROUTING (en -> each target) ===")
    for tgt, phrase in TARGET_SAMPLES.items():
        route = resolve_barrier_route(phrase, "en", tgt, enabled=True)
        ok = (
            route["source_language"] == tgt
            and route["target_language"] == "en"
            and route["speaker"] == "person-2"
        )
        det = detect_language_heuristic(phrase)
        status = "PASS" if ok else "FAIL"
        print(
            f"{status} en->{tgt}: detect={det} "
            f"route={route['source_language']}->{route['target_language']} "
            f"speaker={route['speaker']}"
        )
        if not ok:
            failures.append(f"barrier flip en->{tgt}: {phrase!r}")

    route = resolve_barrier_route("hallo", "en", "nl", enabled=True)
    ok = route["source_language"] == "nl" and route["target_language"] == "en"
    print(f"{'PASS' if ok else 'FAIL'} en->nl hallo: {route['source_language']}->{route['target_language']}")
    if not ok:
        failures.append("hallo nl routing")

    print()
    print("=== BARRIER KEEP (English speaker) ===")
    phrase = "Hello, how are you?"
    keep_failures = 0
    for tgt in TARGET_SAMPLES:
        route = resolve_barrier_route(phrase, "en", tgt, enabled=True)
        ok = (
            route["source_language"] == "en"
            and route["target_language"] == tgt
            and route["speaker"] == "person-1"
        )
        if not ok:
            keep_failures += 1
            failures.append(f"barrier keep en->{tgt}")
            print(f"FAIL keep en->{tgt}: {route}")
    if keep_failures == 0:
        print(f"PASS all {len(TARGET_SAMPLES)} en->* keep routes")

    print()
    print("=== REFINE LEAK CHECK (target->en) ===")
    leak_cases = [
        ("nl", "Waar is het toilet?", "Where is the bathroom?"),
        ("de", "Guten Tag", "Good day"),
        ("fr", "Bonjour", "Hello"),
    ]
    for src, text, expect_sub in leak_cases:
        result = pipeline.translate_text(text, source_language=src, target_language="en")
        out = result.translated_text
        src_words = [
            word
            for word in text.replace("?", "").replace(",", "").split()
            if len(word) > 3 and word[0].isupper()
        ]
        leaked = [
            word
            for word in src_words
            if word.lower() in out.lower() and word.lower() not in expect_sub.lower()
        ]
        ok = not leaked and expect_sub.lower() in out.lower()
        print(f"{'PASS' if ok else 'FAIL'} {src}->en: {out!r} leaked={leaked}")
        if not ok:
            failures.append(f"refine leak {src}->en: {out}")

    failures.extend(_verify_websocket_barrier_routing())

    print()
    print("=== SUMMARY ===")
    print(f"Total failures: {len(failures)}")
    for item in failures:
        print(f" - {item}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
