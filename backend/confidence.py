import re
from typing import Any, List

from backend.config import get_confidence_warning_threshold, get_high_stakes_confidence_threshold


AMBIGUOUS_SENSES = {
    "bank": ["money", "river edge"],
    "bat": ["animal", "sports equipment"],
    "charge": ["price", "electric power", "accusation"],
    "check": ["verify", "restaurant bill", "bank payment"],
    "fine": ["okay", "penalty fee"],
    "light": ["not heavy", "brightness"],
    "match": ["contest", "similar item", "fire starter"],
    "note": ["message", "musical tone"],
    "right": ["correct", "direction", "legal entitlement"],
    "run": ["move quickly", "operate", "campaign"],
    "case": ["legal matter", "container", "example"],
    "fair": ["just", "festival", "light complexion"],
    "set": ["place", "collection", "prepare"],
    "spring": ["season", "coil", "water source"],
}


class ConfidenceEngine:
    def evaluate(
        self,
        stt_confidence: float,
        translation_confidence: float,
        ambiguity_score: float = 0.0,
        context_match: float = 0.6,
    ) -> float:
        score = (
            float(stt_confidence) * 0.34
            + float(translation_confidence) * 0.36
            + (1.0 - float(ambiguity_score)) * 0.18
            + float(context_match) * 0.12
        )
        return max(0.0, min(1.0, score))


def estimate_stt_confidence(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0
    words = len(t.split())
    if words <= 1:
        return 0.28
    if words <= 3:
        return 0.5
    if words <= 6:
        return 0.68
    return 0.82


def estimate_translation_confidence(source_text: str, translated_text: str) -> float:
    source = (source_text or "").strip()
    translated = (translated_text or "").strip()
    if not translated:
        return 0.0
    if is_placeholder_translation(translated):
        return 0.22
    if source and translated.lower() == source.lower():
        return 0.45
    ratio = len(translated) / max(1, len(source))
    if ratio < 0.25 or ratio > 4.0:
        return 0.48
    return min(0.96, 0.66 + 0.04 * min(6, len(translated.split())))


def is_placeholder_translation(text: str) -> bool:
    return bool(re.match(r"^\[[a-z]{2}->[a-z]{2}\]", (text or "").strip(), flags=re.I))


def detect_ambiguities(text: str) -> List[str]:
    t = (text or "").lower()
    return [word for word in AMBIGUOUS_SENSES if re.search(r"\b" + re.escape(word) + r"\b", t)]


def ambiguity_score(text: str) -> float:
    ambiguities = detect_ambiguities(text)
    punctuation = 0.1 if "?" in (text or "") or "..." in (text or "") else 0.0
    return min(1.0, len(ambiguities) * 0.24 + punctuation)


def clarification_for(text: str, ambiguities: List[str]) -> str:
    if ambiguities:
        word = ambiguities[0]
        senses = AMBIGUOUS_SENSES.get(word, [])[:3]
        if senses:
            return f"When you say '{word}', do you mean {', '.join(senses)}?"
        return f"What meaning of '{word}' did you intend?"
    return "I may have misunderstood. Could you repeat or rephrase that?"


def confidence_warning_message(confidence: float, *, high_stakes: bool = False, domains: list[str] | None = None) -> str:
    domain_label = ""
    if domains:
        domain_label = f" ({domains[0].replace('_', ' ')})"
    pct = int(round(confidence * 100))
    if high_stakes:
        return (
            f"Low confidence ({pct}%){domain_label}. "
            "Verify with a human interpreter before acting on this translation."
        )
    return (
        f"Moderate confidence ({pct}%). "
        "Double-check important details before relying on this translation."
    )


def assess_translation_confidence(
    source_text: str,
    translated_text: str,
    *,
    stt_confidence: float | None = None,
    domains: dict[str, Any] | None = None,
    glossary_coverage: float = 1.0,
) -> dict[str, Any]:
    stt_conf = estimate_stt_confidence(source_text) if stt_confidence is None else max(0.0, min(1.0, float(stt_confidence)))
    tr_conf = estimate_translation_confidence(source_text, translated_text)
    amb = ambiguity_score(source_text)
    engine = ConfidenceEngine()
    score = engine.evaluate(stt_conf, tr_conf, amb)
    if glossary_coverage < 1.0:
        score = max(0.0, score - (1.0 - glossary_coverage) * 0.12)

    high_stakes = list((domains or {}).get("high_stakes") or [])
    risk_level = (domains or {}).get("risk_level") or "normal"
    threshold = get_high_stakes_confidence_threshold() if high_stakes else get_confidence_warning_threshold()
    low_confidence = score < threshold
    needs_confirmation = bool(high_stakes) and score < max(threshold, 0.82)

    return {
        "confidence": round(score, 4),
        "stt_confidence": round(stt_conf, 4),
        "translation_confidence": round(tr_conf, 4),
        "confidence_threshold": round(threshold, 4),
        "low_confidence": low_confidence,
        "needs_confirmation": needs_confirmation,
        "risk_level": risk_level,
        "high_stakes": high_stakes,
        "glossary_coverage": round(glossary_coverage, 4),
        "confidence_message": confidence_warning_message(score, high_stakes=needs_confirmation, domains=high_stakes)
        if low_confidence
        else "",
    }
