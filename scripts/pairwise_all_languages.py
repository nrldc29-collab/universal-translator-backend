#!/usr/bin/env python3
"""Verify every configured language pair translates (14 x 13 = 182 directions)."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from backend.config import LANGUAGES
from translation.hybrid_translator import HybridTranslator
from translation.lightweight_translator import LightweightTranslator

LANGS = tuple(LANGUAGES.keys())
GREETINGS = {
    "en": "hello",
    "es": "hola",
    "ht": "bonjou",
    "fr": "bonjour",
    "de": "hallo",
    "it": "ciao",
    "pt": "ola",
    "nl": "hallo",
    "ru": "\u043f\u0440\u0438\u0432\u0435\u0442",
    "zh": "\u4f60\u597d",
    "ja": "\u3053\u3093\u306b\u3061\u306f",
    "ko": "\uc548\ub155\ud558\uc138\uc694",
    "ar": "\u0645\u0631\u062d\u0628\u0627",
    "hi": "\u0928\u092e\u0938\u094d\u0924\u0947",
}

SECOND_PHRASE = {
    "en": "thank you",
    "es": "gracias",
    "ht": "mèsi",
    "fr": "merci",
    "de": "danke",
    "it": "grazie",
    "pt": "obrigado",
    "nl": "dank je",
    "ru": "\u0441\u043f\u0430\u0441\u0438\u0431\u043e",
    "zh": "\u8c22\u8c22",
    "ja": "\u3042\u308a\u304c\u3068\u3046",
    "ko": "\uac10\uc0ac\ud569\ub2c8\ub2e4",
    "ar": "\u0634\u0643\u0631\u0627",
    "hi": "\u0927\u0928\u094d\u092f\u0935\u093e\u0926",
}


def is_miss(result: str, source: str, target: str) -> bool:
    text = str(result or "").strip()
    if not text:
        return True
    if text.startswith(f"[{source}->{target}]"):
        return True
    if text.startswith("[AI:") and len(text) < 20:
        return True
    return False


def run_matrix(name: str, translate_fn) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    pairs = [(s, t) for s in LANGS for t in LANGS if s != t]
    total = len(pairs)
    print(f"\n=== {name}: {total} direction pairs ===")
    t0 = time.time()
    for idx, (source, target) in enumerate(pairs, 1):
        phrase = GREETINGS[source]
        try:
            result = translate_fn(phrase, source, target)
        except Exception as exc:
            result = f"[{source}->{target}] {exc}"
        if is_miss(result, source, target):
            failed += 1
            misses.append(f"{source}->{target}")
            mark = "FAIL"
        else:
            passed += 1
            mark = "ok"
        if idx % 26 == 0 or idx == total:
            print(f"  progress {idx}/{total} ({mark} latest {source}->{target})")
    elapsed = time.time() - t0
    print(f"  {name}: {passed} pass, {failed} fail ({elapsed:.1f}s)")
    return passed, failed, misses


def run_second_phrase_matrix(translate_fn) -> tuple[int, int, list[str]]:
    passed = failed = 0
    misses: list[str] = []
    pairs = [(s, t) for s in LANGS for t in LANGS if s != t]
    for source, target in pairs:
        phrase = SECOND_PHRASE[source]
        try:
            result = translate_fn(phrase, source, target)
        except Exception as exc:
            result = f"[{source}->{target}] {exc}"
        if is_miss(result, source, target):
            failed += 1
            misses.append(f"{source}->{target}")
        else:
            passed += 1
    return passed, failed, misses


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify all configured language directions")
    parser.add_argument(
        "--include-hybrid",
        action="store_true",
        help="Also run the network/model-backed hybrid matrix (potentially slow)",
    )
    args = parser.parse_args()
    lightweight = LightweightTranslator()

    print(f"Languages: {len(LANGS)} -> {', '.join(LANGS)}")
    print(f"Total direction pairs per matrix: {len(LANGS) * (len(LANGS) - 1)}")

    lw_pass, lw_fail, lw_miss = run_matrix(
        "Lightweight greetings",
        lambda p, s, t: lightweight.translate(p, s, t),
    )
    lw2_pass, lw2_fail, lw2_miss = run_second_phrase_matrix(
        lambda p, s, t: lightweight.translate(p, s, t),
    )
    print(f"  Lightweight thank-you: {lw2_pass} pass, {lw2_fail} fail")

    hy_pass = hy_fail = 0
    hy_miss: list[str] = []
    if args.include_hybrid:
        hybrid = HybridTranslator()
        hy_pass, hy_fail, hy_miss = run_matrix(
            "Hybrid neural greetings",
            lambda p, s, t: hybrid.translate(p, s, t, quality=False),
        )

    total_pass = lw_pass + lw2_pass + hy_pass
    total_fail = lw_fail + lw2_fail + hy_fail
    all_misses = sorted(set(lw_miss + lw2_miss + hy_miss))

    print(f"\n=== SUMMARY ===")
    print(f"Total checks: {total_pass + total_fail}")
    print(f"Passed: {total_pass}")
    print(f"Failed: {total_fail}")
    if all_misses:
        print(f"Failed pairs ({len(all_misses)}): {', '.join(all_misses[:20])}")
        if len(all_misses) > 20:
            print(f"  ... and {len(all_misses) - 20} more")

    report = REPO_ROOT / "logs" / "pairwise_lang_report.txt"
    report.write_text(
        "\n".join([
            f"Languages: {len(LANGS)}",
            f"Lightweight greetings: {lw_pass}/{lw_pass + lw_fail}",
            f"Lightweight thank-you: {lw2_pass}/{lw2_pass + lw2_fail}",
            f"Hybrid greetings: {hy_pass}/{hy_pass + hy_fail}" if args.include_hybrid else "Hybrid greetings: SKIPPED",
            f"TOTAL PASS: {total_pass}",
            f"TOTAL FAIL: {total_fail}",
            "FAILURES: " + (", ".join(all_misses) if all_misses else "none"),
        ]),
        encoding="utf-8",
    )
    print(f"Report: {report}")
    print("PASS" if total_fail == 0 else "FAIL")
    return 0 if total_fail == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
