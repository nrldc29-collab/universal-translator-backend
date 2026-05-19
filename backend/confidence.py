import re
from typing import List


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
