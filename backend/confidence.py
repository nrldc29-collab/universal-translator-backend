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

LOCALIZED_AMBIGUOUS_SENSES: dict[str, dict[str, list[str]]] = {
    "es": {
        "banco": ["financial institution", "bench"],
        "derecho": ["correct direction", "law"],
        "curso": ["class", "current flow"],
        "papa": ["father", "potato", "pope"],
        "once": ["eleven", "formerly"],
    },
    "fr": {
        "banque": ["financial institution", "bench"],
        "droit": ["correct direction", "law"],
        "tour": ["turn", "tower"],
        "livre": ["book", "pound weight"],
        "match": ["sports match", "fire starter"],
    },
    "de": {
        "bank": ["financial institution", "bench"],
        "recht": ["correct", "law"],
        "gift": ["poison", "present"],
        "maß": ["measure", "beer mug"],
    },
    "it": {
        "banca": ["financial institution", "bench"],
        "destra": ["right direction", "right hand"],
        "camera": ["room", "legislative chamber"],
        "fattura": ["invoice", "feature"],
    },
    "pt": {
        "banco": ["financial institution", "bench"],
        "direito": ["correct direction", "law"],
        "curso": ["class", "current flow"],
    },
    "nl": {
        "bank": ["financial institution", "bench", "sofa"],
        "recht": ["correct", "law"],
        "slag": ["hit", "type"],
    },
    "ht": {
        "bank": ["financial institution", "bench"],
        "dwa": ["correct", "law or right"],
        "kous": ["course", "current"],
    },
    "ru": {
        "мир": ["peace", "world"],
        "право": ["law", "right direction"],
        "ключ": ["key", "spring water"],
    },
    "ar": {
        "عين": ["eye", "water spring"],
        "حسن": ["goodness", "proper name"],
    },
    "hi": {
        "बैंक": ["financial institution", "bench"],
        "दायां": ["right direction", "right hand"],
    },
    "zh": {
        "银行": ["financial institution", "bench (archaic)"],
        "权利": ["legal right", "power"],
        "花": ["flower", "spend money"],
    },
    "ja": {
        "銀行": ["financial institution", "bench (archaic)"],
        "花": ["flower", "spend money"],
        "切手": ["postage stamp", "cheque"],
    },
    "ko": {
        "은행": ["financial institution", "bench (archaic)"],
        "권리": ["legal right", "power"],
        "배": ["ship", "pear", "stomach"],
    },
}


def _merged_ambiguous_senses(source_lang: str | None = None) -> dict[str, list[str]]:
    merged = dict(AMBIGUOUS_SENSES)
    lang = str(source_lang or "").lower().split("-")[0]
    if lang and lang in LOCALIZED_AMBIGUOUS_SENSES:
        merged.update(LOCALIZED_AMBIGUOUS_SENSES[lang])
    elif not lang:
        for localized in LOCALIZED_AMBIGUOUS_SENSES.values():
            for word, senses in localized.items():
                merged.setdefault(word, senses)
    return merged


def _word_in_text(word: str, text: str) -> bool:
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0600-\u06ff\u0900-\u097f]", word):
        return word in text
    return bool(re.search(r"(?<!\w)" + re.escape(word) + r"(?!\w)", text, flags=re.I))


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


def _uses_character_units(text: str) -> bool:
    value = (text or "").strip()
    if not value:
        return False
    cjk_chars = len(re.findall(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af\u0600-\u06ff\u0900-\u097f]", value))
    return cjk_chars >= max(2, int(len(value) * 0.25))


def _length_units(text: str) -> int:
    value = (text or "").strip()
    if not value:
        return 0
    if _uses_character_units(value):
        return max(1, len(value))
    return max(1, len(value.split()))


def _heuristic_stt_confidence(text: str) -> float:
    t = (text or "").strip()
    if not t:
        return 0.0
    units = _length_units(t)
    if units <= 1:
        return 0.42
    if units <= 3:
        return 0.58
    if units <= 6:
        return 0.72
    return 0.84


def estimate_stt_confidence(text: str, acoustic_confidence: float | None = None) -> float:
    heuristic = _heuristic_stt_confidence(text)
    if acoustic_confidence is None:
        return heuristic
    acoustic = max(0.0, min(1.0, float(acoustic_confidence)))
    units = _length_units((text or "").strip())
    if units <= 3:
        return max(heuristic, acoustic * 0.82 + heuristic * 0.18)
    return acoustic * 0.62 + heuristic * 0.38


def _source_named_terms(source_text: str) -> list[str]:
    text = source_text or ""
    common_sentence_words = {
        "a", "an", "are", "bonjour", "bonjou", "can", "ciao", "could", "danke",
        "do", "does", "good", "grazie", "gracias", "hallo", "hello", "hey", "hi",
        "hola", "how", "i", "is", "merci", "mesi", "no", "ola", "olá", "please",
        "thanks", "thank", "that", "the", "they", "this", "we", "what", "when",
        "where", "why", "would", "yes", "you",
    }
    titled = [
        match.group(0)
        for match in re.finditer(r"\b[A-Z][a-z]{2,}(?:'[A-Za-z]+)?\b", text)
        if match.group(0).lower() not in common_sentence_words
    ]
    hyphenated = re.findall(r"\b[A-Z][a-z]+(?:-[A-Z][a-z]+)+\b", text)
    acronyms = re.findall(r"\b[A-Z]{2,}\b", text)
    quoted = [match[0] or match[1] for match in re.findall(r'"([^"]{2,})"|\'([^\']{2,})\'', text)]
    seen: list[str] = []
    for term in titled + hyphenated + acronyms + quoted:
        if term and term not in seen:
            seen.append(term)
    return seen


def _term_present_in_translation(term: str, translated: str) -> bool:
    if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", term):
        return term in (translated or "")
    return bool(re.search(r"\b" + re.escape(term) + r"\b", translated or "", flags=re.I))


def _missing_named_terms_penalty(source_text: str, translated_text: str) -> float:
    terms = _source_named_terms(source_text)
    if not terms:
        return 0.0
    translated = translated_text or ""
    missing = sum(1 for term in terms if not _term_present_in_translation(term, translated))
    return min(0.22, missing * 0.09)


def estimate_translation_confidence(source_text: str, translated_text: str) -> float:
    source = (source_text or "").strip()
    translated = (translated_text or "").strip()
    if not translated:
        return 0.0
    if is_placeholder_translation(translated):
        return 0.22
    if source and translated.lower() == source.lower():
        return 0.45
    source_units = _length_units(source)
    translated_units = _length_units(translated)
    ratio = translated_units / max(1, source_units)
    comparable_units = _uses_character_units(source) == _uses_character_units(translated)
    if comparable_units and (ratio < 0.25 or ratio > 4.0):
        return 0.48
    base = min(0.96, 0.66 + 0.04 * min(6, len(translated.split())))
    return max(0.0, base - _missing_named_terms_penalty(source, translated))


def is_placeholder_translation(text: str) -> bool:
    return bool(re.match(r"^\[[a-z]{2,}(?:-[a-z0-9]+)?->[a-z]{2,}(?:-[a-z0-9]+)?\]", (text or "").strip(), flags=re.I))


def detect_ambiguities(text: str, source_lang: str | None = None) -> List[str]:
    t = (text or "").strip()
    if not t:
        return []
    senses = _merged_ambiguous_senses(source_lang)
    found: list[str] = []
    for word in senses:
        if _word_in_text(word, t) and word not in found:
            found.append(word)
    return found


def ambiguity_score(text: str, source_lang: str | None = None) -> float:
    ambiguities = detect_ambiguities(text, source_lang)
    punctuation = 0.1 if "?" in (text or "") or "..." in (text or "") else 0.0
    return min(1.0, len(ambiguities) * 0.24 + punctuation)


def clarification_for(text: str, ambiguities: List[str], source_lang: str | None = None) -> str:
    if ambiguities:
        word = ambiguities[0]
        senses = _merged_ambiguous_senses(source_lang).get(word, [])[:3]
        if senses:
            return f"When you say '{word}', do you mean {', '.join(senses)}?"
        return f"What meaning of '{word}' did you intend?"
    return "I may have misunderstood. Could you repeat or rephrase that?"


def subjective_accent_tone_signals(
    *,
    register: str | None = None,
    tone: str | None = None,
    emotion: str | None = None,
    intent: str | None = None,
    stt_confidence: float | None = None,
    acoustic_confidence: float | None = None,
    code_switching: bool = False,
) -> dict[str, Any]:
    """Signals where automated checks cannot certify accent delivery or cultural tone."""
    signals: list[str] = []
    reg = str(register or "neutral").lower()
    ton = str(tone or "neutral").lower()
    emo = str(emotion or "neutral").lower()
    if reg in {"informal", "slang"}:
        signals.append("informal_register")
    if emo not in {"", "neutral"} and emo != "warm":
        signals.append("emotional_tone")
    if ton in {"emphatic", "urgent"}:
        signals.append("emphatic_delivery")
    if str(intent or "").lower() == "emotional_statement":
        signals.append("emotional_content")
    if code_switching:
        signals.append("accent_code_switch")
    if stt_confidence is not None and float(stt_confidence) < 0.62:
        signals.append("uncertain_transcription")
    if acoustic_confidence is not None and float(acoustic_confidence) < 0.55:
        signals.append("accent_or_noise")
    return {"subjective": bool(signals), "signals": signals}


def native_speaker_certification_message(signals: list[str]) -> str:
    if "accent_or_noise" in signals or "uncertain_transcription" in signals:
        return (
            "Accent and delivery are hard to verify automatically — "
            "have a fluent native speaker listen before you rely on the spoken translation."
        )
    if "informal_register" in signals:
        return (
            "Slang and casual tone vary by region — "
            "a native speaker should listen to confirm it sounds natural."
        )
    if "emotional_tone" in signals or "emotional_content" in signals:
        return (
            "Emotional tone is subjective — "
            "have a native speaker listen to confirm the feeling comes across."
        )
    if "accent_code_switch" in signals:
        return (
            "Mixed-language speech often carries accent and cultural nuance — "
            "have a native speaker listen before acting on this translation."
        )
    return (
        "Cultural tone benefits from a native speaker's ear — "
        "listen together before relying on the spoken translation."
    )


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
    context_match: float | None = None,
    domains: dict[str, Any] | None = None,
    glossary_coverage: float = 1.0,
    source_language: str | None = None,
    register: str | None = None,
    tone: str | None = None,
    emotion: str | None = None,
    intent: str | None = None,
    acoustic_confidence: float | None = None,
    code_switching: bool = False,
    glossary_trusted: bool = False,
) -> dict[str, Any]:
    measured_stt_confidence = stt_confidence is not None or acoustic_confidence is not None
    stt_conf = estimate_stt_confidence(source_text) if stt_confidence is None else max(0.0, min(1.0, float(stt_confidence)))
    scoring_stt_conf = stt_conf if measured_stt_confidence else max(stt_conf, 0.75)
    tr_conf = estimate_translation_confidence(source_text, translated_text)
    amb = ambiguity_score(source_text, source_language)
    ctx_match = 0.6 if context_match is None else max(0.0, min(1.0, float(context_match)))
    engine = ConfidenceEngine()
    score = engine.evaluate(scoring_stt_conf, tr_conf, amb, ctx_match)
    if glossary_coverage < 1.0:
        score = max(0.0, score - (1.0 - glossary_coverage) * 0.12)

    high_stakes = list((domains or {}).get("high_stakes") or [])
    risk_level = (domains or {}).get("risk_level") or "normal"
    threshold = get_high_stakes_confidence_threshold() if high_stakes else get_confidence_warning_threshold()
    low_confidence = score < threshold
    needs_confirmation = bool(high_stakes) and score < max(threshold, 0.82)

    subj = subjective_accent_tone_signals(
        register=register,
        tone=tone,
        emotion=emotion,
        intent=intent,
        stt_confidence=stt_conf if measured_stt_confidence else None,
        acoustic_confidence=acoustic_confidence,
        code_switching=code_switching,
    )
    native_listen = bool(subj["subjective"]) and not glossary_trusted
    certification_message = native_speaker_certification_message(subj["signals"]) if native_listen else ""
    weak_acoustic = acoustic_confidence is not None and float(acoustic_confidence) < 0.55
    weak_stt = measured_stt_confidence and stt_conf < 0.58
    high_stakes_medical = any(domain in {"medical", "emergency", "legal"} for domain in high_stakes)
    needs_native_certification = native_listen and (low_confidence or weak_acoustic or weak_stt)
    if high_stakes_medical and (low_confidence or weak_acoustic or weak_stt or score < max(threshold, 0.82)):
        needs_native_certification = True
    elif high_stakes_medical and score < max(threshold + 0.05, 0.88):
        native_listen = True
    if needs_native_certification:
        human_certification_step = "required"
    elif native_listen or (high_stakes_medical and score < 0.9):
        human_certification_step = "advisory"
    else:
        human_certification_step = "none"
    confidence_message = (
        confidence_warning_message(score, high_stakes=needs_confirmation, domains=high_stakes)
        if low_confidence
        else (certification_message if needs_native_certification else "")
    )

    return {
        "confidence": round(score, 4),
        "stt_confidence": round(stt_conf, 4),
        "translation_confidence": round(tr_conf, 4),
        "confidence_threshold": round(threshold, 4),
        "low_confidence": low_confidence,
        "needs_confirmation": needs_confirmation,
        "native_speaker_listen_recommended": native_listen,
        "needs_native_certification": needs_native_certification,
        "certification_signals": subj["signals"],
        "certification_message": certification_message,
        "human_certification_step": human_certification_step,
        "risk_level": risk_level,
        "high_stakes": high_stakes,
        "glossary_coverage": round(glossary_coverage, 4),
        "confidence_message": confidence_message,
    }
