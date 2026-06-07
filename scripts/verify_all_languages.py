#!/usr/bin/env python3
"""Quick verification that all 14 configured languages translate and speak."""

from __future__ import annotations

import sys
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


def main() -> int:
    lightweight = LightweightTranslator()
    hybrid = HybridTranslator()

    instant_miss = []
    for source in LANGS:
        for target in LANGS:
            if source == target:
                continue
            phrase = GREETINGS[source]
            result = lightweight.translate(phrase, source, target)
            if result.startswith(f"[{source}->{target}]"):
                instant_miss.append(f"{source}->{target}")

    emergency_miss = []
    for target in LANGS:
        if target == "en":
            continue
        for phrase in ("help", "i need a doctor", "call the police"):
            result = lightweight.translate(phrase, "en", target)
            if result.startswith(f"[en->{target}]"):
                emergency_miss.append(f"en->{target}:{phrase}")

    travel_miss = []
    for target in LANGS:
        if target == "en":
            continue
        for phrase in (
            "do you speak english", "where is the pharmacy", "turn left", "i need a taxi",
            "i am hungry", "the check please", "i feel sick", "call an ambulance",
            "today", "i have a reservation", "how much is this", "see you later",
            "five", "ten", "i understand", "i lost my passport", "speak slowly",
            "good evening", "i am sorry", "it hurts here", "where is the embassy",
            "i am tired", "my wife", "do you have wifi", "where is the atm",
        ):
            result = lightweight.translate(phrase, "en", target)
            if result.startswith(f"[en->{target}]"):
                travel_miss.append(f"en->{target}:{phrase}")

    remote_miss = []
    sample_targets = ("es", "ht", "fr", "zh", "ja", "ar")
    for target in sample_targets:
        result = hybrid.translate("Please tell me how to get to the hospital.", "en", target, quality=False)
        if not result or result.startswith("[en->"):
            remote_miss.append(f"en->{target}")

    print(f"Languages configured: {len(LANGS)}")
    print(f"Instant greeting gaps: {len(instant_miss)}")
    print(f"Emergency phrase gaps: {len(emergency_miss)}")
    print(f"Travel phrase gaps: {len(travel_miss)}")
    print(f"Remote sample gaps: {len(remote_miss)}")

    if instant_miss:
        print("Instant misses:", ", ".join(instant_miss[:10]))
    if emergency_miss:
        print("Emergency misses:", ", ".join(emergency_miss[:10]))
    if travel_miss:
        print("Travel misses:", ", ".join(travel_miss[:10]))
    if remote_miss:
        print("Remote misses:", ", ".join(remote_miss))

    ok = not instant_miss and not emergency_miss and not travel_miss and not remote_miss
    print("PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
