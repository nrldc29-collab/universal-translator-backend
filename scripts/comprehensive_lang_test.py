#!/usr/bin/env python3
"""Exhaustive translation verification across all 14 configured languages.

Phases:
  1. Native phrase pivot  - each language's common phrases -> every other language (lightweight)
  2. English travel/emergency - full en->* phrase battery (lightweight)
  3. Hybrid free-form     - one sentence per source language -> every target (neural/remote path)
  4. Live API (optional)  - POST /translate/text for every direction pair

Exit 0 only when every phase passes.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import LANGUAGES
from translation.hybrid_translator import HybridTranslator
from translation.lightweight_translator import LightweightTranslator

LANGS = tuple(LANGUAGES.keys())

# Native common phrases (source text) used for pivot testing.
NATIVE_PHRASES: dict[str, list[str]] = {
    "en": ["hello", "thank you", "help", "where is the bathroom", "i need a doctor"],
    "es": ["hola", "gracias", "ayuda", "donde esta el bano"],
    "ht": ["bonjou", "mesi", "ed", "kote twalet la"],
    "fr": ["bonjour", "merci", "aide", "ou sont les toilettes"],
    "de": ["hallo", "danke", "hilfe", "wo ist die toilette"],
    "it": ["ciao", "grazie", "aiuto", "dov e il bagno"],
    "pt": ["ola", "obrigado", "ajuda", "onde fica o banheiro"],
    "nl": ["hallo", "dank je", "help", "waar is het toilet"],
    "ru": ["\u043f\u0440\u0438\u0432\u0435\u0442", "\u0441\u043f\u0430\u0441\u0438\u0431\u043e", "\u043f\u043e\u043c\u043e\u0433\u0438\u0442\u0435"],
    "zh": ["\u4f60\u597d", "\u8c22\u8c22", "\u6551\u547d", "\u6d17\u624b\u95f4\u5728\u54ea\u91cc"],
    "ja": ["\u3053\u3093\u306b\u3061\u306f", "\u3042\u308a\u304c\u3068\u3046", "\u52a9\u3051\u3066"],
    "ko": ["\uc548\ub155\ud558\uc138\uc694", "\uac10\uc0ac\ud569\ub2c8\ub2e4", "\ub3c4\uc640\uc918\uc694"],
    "ar": ["\u0645\u0631\u062d\u0628\u0627", "\u0634\u0643\u0631\u0627", "\u0627\u0644\u0646\u062c\u062f\u0629"],
    "hi": ["\u0928\u092e\u0938\u094d\u0924\u0947", "\u0927\u0928\u094d\u092f\u0935\u093e\u0926", "\u092e\u0926\u0926"],
}

EN_TRAVEL = (
    "do you speak english", "where is the pharmacy", "turn left", "i need a taxi",
    "i am hungry", "the check please", "i feel sick", "call an ambulance",
    "today", "i have a reservation", "how much is this", "see you later",
    "five", "ten", "i understand", "i lost my passport", "speak slowly",
    "good evening", "i am sorry", "it hurts here", "where is the embassy",
    "i am tired", "my wife", "do you have wifi", "where is the atm",
)

FREE_FORM: dict[str, str] = {
    "en": "I would like a glass of water, please.",
    "es": "Me gustaria un vaso de agua, por favor.",
    "ht": "Mwen ta renmen yon vè dlo, tanpri.",
    "fr": "Je voudrais un verre d'eau, s'il vous plait.",
    "de": "Ich mochte bitte ein Glas Wasser.",
    "it": "Vorrei un bicchiere d'acqua, per favore.",
    "pt": "Eu gostaria de um copo de agua, por favor.",
    "nl": "Ik wil graag een glas water.",
    "ru": "\u042f \u0445\u043e\u0442\u0435\u043b \u0431\u044b \u0441\u0442\u0430\u043a\u0430\u043d \u0432\u043e\u0434\u044b, \u043f\u043e\u0436\u0430\u043b\u0443\u0439\u0441\u0442\u0430.",
    "zh": "\u8bf7\u7ed9\u6211\u4e00\u676f\u6c34\u3002",
    "ja": "\u304a\u6c34\u3092\u3044\u305f\u3060\u3051\u307e\u3059\u304b\u3002",
    "ko": "\ubb3c \ud55c \uc794 \uc8fc\uc138\uc694.",
    "ar": "\u0623\u0631\u064a\u062f \u0643\u0623\u0633 \u0645\u0646 \u0627\u0644\u0645\u0627\u0621\u060c \u0645\u0646 \u0641\u0636\u0644\u0643.",
    "hi": "\u0915\u0943\u092a\u092f\u093e \u092e\u0941\u091d\u0947 \u092a\u093e\u0928\u0940 \u0915\u093e \u090f\u0915 \u0917\u093f\u0932\u093e\u0938 \u0926\u0940\u091c\u093f\u090f\u0964",
}


def is_miss(result: str, source: str, target: str) -> bool:
    text = str(result or "").strip()
    if not text:
        return True
    if text.startswith(f"[{source}->{target}]"):
        return True
    if text.startswith("[AI:") and len(text) < 20:
        return True
    if text.startswith("[AI_ERROR:"):
        return True
    return False


def phase_native_pivot(lw: LightweightTranslator) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    for source in LANGS:
        for phrase in NATIVE_PHRASES.get(source, []):
            for target in LANGS:
                if source == target:
                    continue
                try:
                    result = lw.translate(phrase, source, target)
                except Exception as exc:
                    result = f"[{source}->{target}] {exc}"
                if is_miss(result, source, target):
                    failed += 1
                    misses.append(f"native {source}->{target} ({phrase[:20]!r})")
                else:
                    passed += 1
    print(f"  Native phrase pivot: {passed} pass, {failed} fail")
    return passed, failed, misses


def phase_en_travel(lw: LightweightTranslator) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    for target in LANGS:
        if target == "en":
            continue
        for phrase in EN_TRAVEL:
            try:
                result = lw.translate(phrase, "en", target)
            except Exception as exc:
                result = f"[en->{target}] {exc}"
            if is_miss(result, "en", target):
                failed += 1
                misses.append(f"en->{target}:{phrase}")
            else:
                passed += 1
    print(f"  English travel/emergency: {passed} pass, {failed} fail")
    return passed, failed, misses


def phase_hybrid_freeform(hybrid: HybridTranslator) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    pairs = [(s, t) for s in LANGS for t in LANGS if s != t]
    total = len(pairs)
    t0 = time.time()
    for idx, (source, target) in enumerate(pairs, 1):
        phrase = FREE_FORM[source]
        try:
            result = hybrid.translate(phrase, source, target, quality=False)
        except Exception as exc:
            result = f"[{source}->{target}] {exc}"
        if is_miss(result, source, target):
            failed += 1
            misses.append(f"hybrid {source}->{target}")
        else:
            passed += 1
        if idx % 26 == 0 or idx == total:
            print(f"  hybrid progress {idx}/{total}")
    elapsed = time.time() - t0
    print(f"  Hybrid free-form: {passed} pass, {failed} fail ({elapsed:.1f}s)")
    return passed, failed, misses


def phase_live_api(api_url: str, delay: float) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    pairs = [(s, t) for s in LANGS for t in LANGS if s != t]
    endpoint = api_url.rstrip("/") + "/translate/text"
    call_idx = 0

    def call(text: str, src: str, tgt: str) -> dict:
        nonlocal call_idx
        call_idx += 1
        body = json.dumps({
            "text": text,
            "source_language": src,
            "target_language": tgt,
            # Fast lightweight path — avoids loading Marian/NLLB per request.
            "translation_mode": "fast",
            "translation_provider": "lightweight",
            "session_id": f"lang-verify-{call_idx}",
        }).encode("utf-8")
        req = urllib.request.Request(
            endpoint,
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode("utf-8"))

    for idx, (source, target) in enumerate(pairs, 1):
        for label, phrase in (
            ("greet", NATIVE_PHRASES[source][0]),
            ("thanks", NATIVE_PHRASES[source][1]),
            ("free", FREE_FORM[source]),
        ):
            try:
                res = call(phrase, source, target)
                out = str(res.get("translated_text") or "").strip()
                if not out or (out.startswith("[") and "->" in out[:16]):
                    failed += 1
                    misses.append(f"api {label} {source}->{target}: {out!r}")
                else:
                    passed += 1
            except Exception as exc:
                failed += 1
                misses.append(f"api {label} {source}->{target}: EXC {exc}")
            if delay:
                time.sleep(delay)
        if idx % 13 == 0:
            print(f"  api progress {idx}/{len(pairs)} ok={passed} fail={failed}")

    print(f"  Live API: {passed} pass, {failed} fail")
    return passed, failed, misses


def phase_quality_checks() -> tuple[int, int, list[str]]:
    """Validate name preservation, phonetic normalize, and confidence wiring."""
    from backend.confidence import assess_translation_confidence, estimate_translation_confidence
    from backend.refine import refine_translation
    from speech.whisper_stt import normalize_transcript

    passed = failed = 0
    misses: list[str] = []

    def check(label: str, ok: bool) -> None:
        nonlocal passed, failed
        if ok:
            passed += 1
        else:
            failed += 1
            misses.append(label)

    ht_norm = normalize_transcript("Mu en bezwen yondokte.", "ht")
    check("normalize_ht_phonetic", "mwen" in ht_norm.lower() and "dokte" in ht_norm.lower())

    refined = refine_translation('Meet "Marie" at CVS.', "Rencontrez marie à cvs.")
    check("refine_named_terms", "Marie" in refined and "CVS" in refined)

    named_conf = estimate_translation_confidence(
        "Dr. Chen went to Port-au-Prince.",
        "El doctor fue a la ciudad.",
    )
    good_conf = estimate_translation_confidence(
        "Dr. Chen went to Port-au-Prince.",
        "El Dr. Chen fue a Port-au-Prince.",
    )
    check("confidence_named_terms", good_conf > named_conf)

    assessed = assess_translation_confidence("I went to the bank.", "[en->es] placeholder")
    check("assess_blocks_placeholder", assessed.get("low_confidence") is True)

    from backend.communication_brain import analyze_communication, detect_register
    from backend.streaming import _translation_kwargs_from_analysis

    check("detect_informal_register", detect_register("yeah nah mate") == "informal")
    informal = analyze_communication("yeah I'm gonna head out")
    informal_hints = _translation_kwargs_from_analysis(informal).get("hints") or []
    check("informal_translation_hints", any("informal" in str(h).lower() for h in informal_hints))

    from backend.confidence import detect_ambiguities as detect_amb

    check("spanish_ambiguity_banco", "banco" in detect_amb("fui al banco", "es"))
    check("french_ambiguity_banque", "banque" in detect_amb("je vais à la banque", "fr"))

    from backend.confidence import assess_translation_confidence, subjective_accent_tone_signals

    informal = subjective_accent_tone_signals(register="informal", tone="neutral", emotion="neutral")
    check("informal_register_subjective", informal.get("subjective") is True)
    certified = assess_translation_confidence(
        "yeah nah mate I'm heading out",
        "sí, me voy",
        source_language="en",
        register="informal",
        tone="neutral",
        stt_confidence=0.95,
    )
    check("native_listen_informal", certified.get("native_speaker_listen_recommended") is True)
    check("high_conf_informal_no_block", certified.get("needs_native_certification") is False)

    print(f"  Quality checks: {passed} pass, {failed} fail")
    return passed, failed, misses


def wait_for_api(api_url: str, timeout: float = 120.0) -> bool:
    health = api_url.rstrip("/") + "/health"
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(health, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("status") == "ok":
                    return True
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
            pass
        time.sleep(2)
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Comprehensive all-language translation test")
    parser.add_argument("--skip-api", action="store_true", help="Skip live API phase")
    parser.add_argument("--api-only", action="store_true", help="Run only live API phase")
    parser.add_argument("--include-hybrid", action="store_true", help="Run the slow network/model-backed hybrid matrix")
    parser.add_argument("--api-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--api-delay", type=float, default=0.02, help="Seconds between API calls")
    args = parser.parse_args()

    lw = LightweightTranslator()
    hybrid = HybridTranslator()

    print(f"=== Comprehensive Language Test ({len(LANGS)} languages) ===")
    print(f"Languages: {', '.join(LANGS)}")

    all_misses: list[str] = []
    total_pass = total_fail = 0

    if not args.api_only:
        print("\n--- Phase 1: Native phrase pivot (lightweight) ---")
        p, f, m = phase_native_pivot(lw)
        total_pass += p
        total_fail += f
        all_misses.extend(m)

        print("\n--- Phase 2: English travel/emergency (lightweight) ---")
        p, f, m = phase_en_travel(lw)
        total_pass += p
        total_fail += f
        all_misses.extend(m)

        print("\n--- Phase 2b: Quality (names, normalize, confidence) ---")
        p, f, m = phase_quality_checks()
        total_pass += p
        total_fail += f
        all_misses.extend(m)

        if args.include_hybrid:
            print("\n--- Phase 3: Hybrid free-form (all pairs) ---")
            p, f, m = phase_hybrid_freeform(hybrid)
            total_pass += p
            total_fail += f
            all_misses.extend(m)

    if not args.skip_api:
        print(f"\n--- Phase 4: Live API ({args.api_url}) ---")
        if wait_for_api(args.api_url):
            print("  Backend ready")
            p, f, m = phase_live_api(args.api_url, args.api_delay)
            total_pass += p
            total_fail += f
            all_misses.extend(m)
        else:
            print("  Backend not reachable - SKIPPED (counts as fail)")
            total_fail += 1
            all_misses.append("api:backend_unreachable")

    print(f"\n=== FINAL SUMMARY ===")
    print(f"Total checks: {total_pass + total_fail}")
    print(f"Passed: {total_pass}")
    print(f"Failed: {total_fail}")
    if all_misses:
        print(f"First failures ({min(30, len(all_misses))}):")
        for miss in all_misses[:30]:
            print(f"  - {miss}")
        if len(all_misses) > 30:
            print(f"  ... and {len(all_misses) - 30} more")

    report = REPO_ROOT / "logs" / "comprehensive_lang_report.txt"
    report.write_text(
        "\n".join([
            f"Languages: {len(LANGS)}",
            f"TOTAL PASS: {total_pass}",
            f"TOTAL FAIL: {total_fail}",
            "FAILURES: " + (", ".join(all_misses[:50]) if all_misses else "none"),
        ]),
        encoding="utf-8",
    )
    print(f"Report: {report}")
    ok = total_fail == 0
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
