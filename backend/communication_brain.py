import re
from typing import Any

from backend.confidence import (
    AMBIGUOUS_SENSES,
    ambiguity_score,
    clarification_for,
    detect_ambiguities,
    estimate_stt_confidence,
    estimate_translation_confidence,
    is_placeholder_translation,
)
from backend.config import get_cip_ambiguity_threshold, get_cip_confidence_threshold


ENGINE_VERSION = "python_ai_brain_v8"
QUESTION_PREFIXES = ("what", "why", "how", "when", "where", "who", "can you", "could you", "would you")
REQUEST_PREFIXES = ("please", "help", "i need", "can i", "could i", "would i")
EMOTIONAL_TERMS = {"sad", "upset", "angry", "scared", "worried", "hurt", "frustrated", "lonely"}
POLITE_TERMS = ("please", "thank", "thanks", "sorry", "appreciate")
URGENT_TERMS = ("urgent", "quickly", "right now", "immediately", "asap")
AGREEMENT_PREFIXES = ("yes", "yeah", "sure", "okay", "ok")
DISAGREEMENT_PREFIXES = ("no", "don't", "do not", "cannot", "can't")
DOMAIN_TERMS = {
    "medical": {"doctor", "hospital", "clinic", "medicine", "medication", "allergy", "pain", "dose", "dosage", "blood", "emergency"},
    "legal": {"lawyer", "attorney", "court", "police", "contract", "rights", "judge", "legal", "arrest", "signature"},
    "financial": {"money", "cash", "card", "bank", "price", "cost", "charge", "invoice", "payment", "refund", "dollars"},
    "travel_safety": {"passport", "address", "airport", "gate", "exit", "danger", "safe", "lost", "emergency", "help"},
}
STRICT_CONFIRM_DOMAINS = {"medical", "legal", "travel_safety"}
PRECISION_FAST_LANE_DOMAINS = {"financial"}
LANGUAGE_HINTS = {
    "en": {"hello", "please", "thank", "thanks", "where", "what", "need", "help", "price", "doctor", "bank", "room"},
    "es": {"hola", "gracias", "donde", "que", "necesito", "ayuda", "precio", "doctor", "banco", "habitacion"},
    "fr": {"bonjour", "merci", "ou", "quoi", "besoin", "aide", "prix", "docteur", "banque", "chambre"},
    "ht": {"bonjou", "mesi", "kote", "kisa", "bezwen", "ede", "pri", "dokte", "bank", "chanm"},
}
STOP_WORDS = {
    "the", "and", "for", "that", "this", "with", "you", "are", "was", "were",
    "have", "from", "your", "about", "what", "when", "where", "there", "here",
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _tokens(text: str) -> list[str]:
    return re.findall(r"[A-Za-z][A-Za-z'-]{2,}", (text or "").lower())


def _detect_current_intent(text: str) -> str:
    lowered = (text or "").lower().strip()
    if not lowered:
        return "empty"
    if "how much" in lowered or "price" in lowered or "cost" in lowered:
        return "price"
    if any(term in lowered for term in EMOTIONAL_TERMS):
        return "emotional_statement"
    if lowered.endswith("?") or lowered.startswith(QUESTION_PREFIXES):
        return "question"
    if lowered.startswith(REQUEST_PREFIXES):
        return "request"
    if lowered.startswith(AGREEMENT_PREFIXES):
        return "agreement"
    if lowered.startswith(DISAGREEMENT_PREFIXES):
        return "disagreement"
    return "statement"


def _detect_current_tone(text: str) -> str:
    lowered = (text or "").lower()
    if any(term in lowered for term in URGENT_TERMS):
        return "urgent"
    if "!" in (text or "") or any(term in lowered for term in ("angry", "upset", "frustrated")):
        return "emphatic"
    if any(term in lowered for term in POLITE_TERMS):
        return "polite"
    return "neutral"


def detect_intent(text: str, semantic_context: dict | None = None) -> str:
    current_intent = _detect_current_intent(text)
    if current_intent not in {"statement", "empty"}:
        return current_intent

    context_intent = (semantic_context or {}).get("last_intent") or (semantic_context or {}).get("intent")
    if context_intent and context_intent not in {"general", "statement"}:
        return str(context_intent)
    return current_intent


def detect_tone(text: str, semantic_context: dict | None = None) -> str:
    detected = _detect_current_tone(text)
    if detected in {"urgent", "emphatic"}:
        return detected

    context_tone = (semantic_context or {}).get("conversation_mood") or (semantic_context or {}).get("tone")
    if context_tone and context_tone not in {"neutral", "stable"}:
        return str(context_tone)
    return detected


def detect_emotion(text: str, tone: str) -> str:
    lowered = (text or "").lower()
    if "angry" in lowered or "frustrated" in lowered or tone == "emphatic":
        return "frustrated"
    if "scared" in lowered or "worried" in lowered:
        return "concerned"
    if "sad" in lowered or "lonely" in lowered or "hurt" in lowered:
        return "sad"
    if tone == "polite":
        return "warm"
    return "neutral"


def detect_entities(text: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for match in re.finditer(r"\b\d+(?:[.,]\d+)?\b", text or ""):
        entities.append({"type": "number", "value": match.group(0)})
    for match in re.finditer(r"[$\u20ac\u00a3]\s?\d+(?:[.,]\d+)?", text or ""):
        entities.append({"type": "money", "value": match.group(0)})
    return entities[:8]


def detect_language_mix(text: str, declared_source: str | None = None) -> dict:
    tokens = set(_tokens(text))
    scores = {
        code: len(tokens & hints)
        for code, hints in LANGUAGE_HINTS.items()
    }
    detected = max(scores, key=scores.get) if scores else declared_source or "unknown"
    detected_score = scores.get(detected, 0)
    active_languages = [code for code, score in scores.items() if score > 0]
    total_hits = sum(scores.values())
    confidence = detected_score / max(1, total_hits)
    declared = (declared_source or "").split("-")[0].lower() or None
    mismatch = bool(declared and detected_score >= 2 and detected != declared)
    code_switching = len(active_languages) >= 2 and total_hits >= 2
    return {
        "declared": declared,
        "detected": detected if detected_score else declared or "unknown",
        "scores": scores,
        "confidence": round(confidence, 4),
        "active_languages": active_languages,
        "code_switching": code_switching,
        "source_language_mismatch": mismatch,
    }


def extract_protected_terms(text: str) -> list[dict[str, str]]:
    protected: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(kind: str, value: str) -> None:
        cleaned = value.strip(" ,.;:!?()[]{}")
        if not cleaned:
            return
        key = (kind, cleaned.lower())
        if key not in seen:
            seen.add(key)
            protected.append({"type": kind, "value": cleaned})

    for match in re.finditer(r"[$\u20ac\u00a3]\s?\d+(?:[.,]\d+)?", text or ""):
        add("money", match.group(0))
    for match in re.finditer(r"\b\d+(?:[.,]\d+)?\b", text or ""):
        add("number", match.group(0))
    for match in re.finditer(r"\b[A-Z][a-z]{2,}\b", text or ""):
        add("name_or_place", match.group(0))
    for match in re.finditer(r"\b[A-Z]{2,}\b", text or ""):
        add("acronym", match.group(0))
    return protected[:12]


def missing_protected_terms(protected_terms: list[dict[str, str]], fallback_translation: str) -> list[dict[str, str]]:
    translated = (fallback_translation or "").lower()
    missing: list[dict[str, str]] = []
    for item in protected_terms:
        value = str(item.get("value") or "")
        if not value:
            continue
        if item.get("type") in {"number", "money"}:
            digits = re.sub(r"\D", "", value)
            if digits and digits not in re.sub(r"\D", "", translated):
                missing.append(item)
        elif value.lower() not in translated:
            missing.append(item)
    return missing


def detect_domains(text: str) -> dict:
    tokens = set(_tokens(text))
    matches = {
        domain: sorted(tokens & terms)
        for domain, terms in DOMAIN_TERMS.items()
        if tokens & terms
    }
    high_stakes = [domain for domain in ("medical", "legal", "financial", "travel_safety") if domain in matches]
    risk_level = "high" if high_stakes else "normal"
    return {
        "matches": matches,
        "high_stakes": high_stakes,
        "risk_level": risk_level,
    }


def context_match_score(text: str, context=None, speaker_context=None) -> float:
    source_tokens = {token for token in _tokens(text) if token not in STOP_WORDS}
    if not source_tokens:
        return 0.55

    recent_text = " ".join(
        f"{item.get('original', '')} {item.get('translated', '')}"
        for item in (context or [])[-8:]
        if isinstance(item, dict)
    )
    speaker_text = " ".join(str(item) for item in (speaker_context or {}).get("history", [])[-8:])
    context_tokens = {token for token in _tokens(f"{recent_text} {speaker_text}") if token not in STOP_WORDS}
    if not context_tokens:
        return 0.62
    overlap = len(source_tokens & context_tokens) / max(1, len(source_tokens))
    return min(1.0, 0.58 + overlap * 0.35)


def speaker_style_profile(context=None, speaker_context=None) -> dict:
    turns = int((speaker_context or {}).get("turns") or 0)
    history = [str(item) for item in (speaker_context or {}).get("history", [])[-8:]]
    recent_context = [item for item in (context or [])[-8:] if isinstance(item, dict)]
    clarification_count = 0
    for item in recent_context:
        cip = (item.get("metadata") or {}).get("cip") or {}
        decision = cip.get("decision") if isinstance(cip, dict) else {}
        if isinstance(decision, dict) and decision.get("type") == "clarification":
            clarification_count += 1
    short_turns = sum(1 for item in history if len(item.split()) <= 2)
    clarity_preference = min(1.0, 0.55 + clarification_count * 0.1 + short_turns * 0.03)
    directness = 0.7 if turns >= 5 else 0.55
    return {
        "turns": turns,
        "clarity_preference": round(clarity_preference, 4),
        "directness": round(directness, 4),
        "suggested_register": "plain",
    }


def analyze_outcomes(context=None) -> dict:
    recent = [item for item in (context or [])[-12:] if isinstance(item, dict)]
    if not recent:
        return {
            "turns": 0,
            "clarification_rate": 0.0,
            "success_rate": 0.0,
            "stability_score": 0.0,
        }

    clarification_count = 0
    success_count = 0
    for item in recent:
        cip = (item.get("metadata") or {}).get("cip") or {}
        decision = cip.get("decision") if isinstance(cip, dict) else {}
        decision_type = decision.get("type") if isinstance(decision, dict) else None
        translated = str(item.get("translated") or "").strip()
        if decision_type == "clarification" or not translated:
            clarification_count += 1
        elif decision_type in {"response", "supportive_response"} or translated:
            success_count += 1

    total = max(1, len(recent))
    clarification_rate = clarification_count / total
    success_rate = success_count / total
    return {
        "turns": len(recent),
        "clarification_rate": round(clarification_rate, 4),
        "success_rate": round(success_rate, 4),
        "stability_score": round(success_rate - clarification_rate, 4),
    }


def derive_adaptive_policy(context=None, speaker_context=None, semantic_context: dict | None = None) -> dict:
    outcomes = analyze_outcomes(context)
    ambiguity_threshold = get_cip_ambiguity_threshold()
    confidence_threshold = get_cip_confidence_threshold()
    force_clarification = False
    response_speed_boost = False

    if outcomes["clarification_rate"] > 0.4 and outcomes["turns"] >= 3:
        ambiguity_threshold = max(0.35, ambiguity_threshold - 0.1)
        confidence_threshold = min(0.68, confidence_threshold + 0.08)
        force_clarification = True
    if outcomes["success_rate"] > 0.8 and outcomes["turns"] >= 5:
        response_speed_boost = True
        confidence_threshold = max(0.32, confidence_threshold - 0.04)
    if (semantic_context or {}).get("conversation_mood") == "urgent":
        response_speed_boost = True
    if int((speaker_context or {}).get("turns") or 0) >= 8 and outcomes["stability_score"] > 0.5:
        response_speed_boost = True

    return {
        "ambiguity_threshold": round(ambiguity_threshold, 4),
        "confidence_threshold": round(confidence_threshold, 4),
        "force_clarification": force_clarification,
        "response_speed_boost": response_speed_boost,
        "outcomes": outcomes,
    }


def analyze_communication(
    text: str,
    *,
    context=None,
    speaker_context=None,
    semantic_context: dict | None = None,
) -> dict:
    source_text = text or ""
    intent = detect_intent(source_text, semantic_context)
    tone = detect_tone(source_text, semantic_context)
    emotion = detect_emotion(source_text, tone)
    words = detect_ambiguities(source_text)
    amb_score = ambiguity_score(source_text)
    domains = detect_domains(source_text)
    ctx_match = context_match_score(source_text, context, speaker_context)
    speaker_style = speaker_style_profile(context, speaker_context)
    urgency = 0.85 if tone == "urgent" else (0.65 if any(term in source_text.lower() for term in ("now", "soon")) else 0.2)
    recent_topics = [
        token for token in _tokens(" ".join(str(item.get("original", "")) for item in (context or [])[-5:] if isinstance(item, dict)))
        if token not in STOP_WORDS
    ][:8]
    communication_state = "stable"
    if domains["risk_level"] == "high":
        communication_state = "high_stakes"
    elif amb_score >= get_cip_ambiguity_threshold():
        communication_state = "ambiguous"
    elif tone == "urgent":
        communication_state = "urgent"
    elif intent == "emotional_statement":
        communication_state = "support_needed"

    return {
        "source": ENGINE_VERSION,
        "intent": intent,
        "tone": tone,
        "emotion": emotion,
        "entities": detect_entities(source_text),
        "domains": domains,
        "urgency": round(urgency, 4),
        "ambiguity_score": round(amb_score, 4),
        "ambiguity": {
            "high": amb_score >= get_cip_ambiguity_threshold(),
            "score": round(amb_score, 4),
            "words": words,
        },
        "context_match": round(ctx_match, 4),
        "memory": {
            "recent_topics": recent_topics,
            "speaker_turns": int((speaker_context or {}).get("turns") or 0),
        },
        "speaker_style": speaker_style,
        "communication_state": communication_state,
    }


def translation_quality_flags(
    text: str,
    fallback_translation: str,
    source_language: str | None,
    target_language: str | None,
    analysis: dict,
) -> list[str]:
    source = (text or "").strip()
    translated = (fallback_translation or "").strip()
    flags: list[str] = []
    if not source:
        flags.append("empty_source")
    if not translated:
        flags.append("empty_translation")
    elif is_placeholder_translation(translated):
        flags.append("placeholder_translation")
    elif source_language and target_language and source_language != target_language and translated.lower() == source.lower():
        flags.append("untranslated_echo")

    source_words = max(1, len(source.split()))
    translated_words = len(translated.split())
    if translated and translated_words <= 1 and source_words >= 5:
        flags.append("translation_too_short")
    if translated and translated_words > source_words * 4 and source_words >= 2:
        flags.append("translation_too_long")
    if analysis.get("ambiguity", {}).get("high"):
        flags.append("high_ambiguity")
    if analysis.get("domains", {}).get("risk_level") == "high":
        flags.append("high_stakes")
    if analysis.get("entities"):
        flags.append("precision_entities")
    language = analysis.get("language", {})
    if language.get("code_switching"):
        flags.append("code_switching")
    if language.get("source_language_mismatch"):
        flags.append("source_language_mismatch")
    if analysis.get("protected_terms", {}).get("missing"):
        flags.append("missing_protected_terms")
    if _safe_float(analysis.get("context_match"), 0.6) < 0.45:
        flags.append("weak_context_match")
    return flags


def clarification_message(text: str, analysis: dict, reason: str) -> str:
    ambiguity = analysis.get("ambiguity", {})
    if ambiguity.get("words"):
        return clarification_for(text, ambiguity.get("words", []))
    domains = analysis.get("domains", {})
    high_stakes = domains.get("high_stakes") or []
    if high_stakes:
        domain = str(high_stakes[0]).replace("_", " ")
        return f"This sounds important for {domain}. Could you repeat the exact words slowly?"
    if analysis.get("entities"):
        return "I heard a number or amount. Could you repeat it once so I translate it exactly?"
    if reason == "source_language_mismatch":
        language = analysis.get("language", {})
        detected = language.get("detected") or "another language"
        return f"This sounds like {detected}, but the selected source language is different. Should I switch languages?"
    if reason == "missing_protected_terms":
        missing = analysis.get("protected_terms", {}).get("missing") or []
        if missing:
            value = missing[0].get("value")
            return f"I may have missed '{value}'. Could you repeat that exact name, number, or code?"
    if reason == "untranslated_echo":
        return "I heard the words, but the translation did not change languages. Could you repeat it a little more clearly?"
    return "I may have misunderstood. Could you repeat or rephrase that?"


def brain_confidence_score(
    *,
    text: str,
    fallback_translation: str,
    stt_confidence: float | None,
    translation_confidence: float | None,
    analysis: dict,
) -> float:
    stt_conf = estimate_stt_confidence(text) if stt_confidence is None else _safe_float(stt_confidence, 0.0)
    tr_conf = (
        estimate_translation_confidence(text, fallback_translation)
        if translation_confidence is None
        else _safe_float(translation_confidence, 0.0)
    )
    amb_score = _safe_float(analysis.get("ambiguity_score"), 0.0)
    ctx_match = _safe_float(analysis.get("context_match"), 0.6)
    score = (stt_conf * 0.28) + (tr_conf * 0.32) + ((1.0 - amb_score) * 0.25) + (ctx_match * 0.15)
    quality_flags = analysis.get("quality_flags") or []
    if "untranslated_echo" in quality_flags:
        score -= 0.2
    if "translation_too_short" in quality_flags or "translation_too_long" in quality_flags:
        score -= 0.12
    if "high_stakes" in quality_flags:
        score -= 0.06
    if "source_language_mismatch" in quality_flags:
        score -= 0.18
    if "missing_protected_terms" in quality_flags:
        score -= 0.16
    return max(0.0, min(1.0, score))


def meaning_risk_score(confidence: float, analysis: dict, quality_flags: list[str]) -> float:
    risk = 1.0 - _safe_float(confidence, 0.0)
    ambiguity = _safe_float(analysis.get("ambiguity_score"), 0.0)
    context_match = _safe_float(analysis.get("context_match"), 0.6)

    risk += min(0.24, ambiguity * 0.22)
    if context_match < 0.5:
        risk += 0.08
    language_repair = analysis.get("language_repair_status") or {}
    if "source_language_mismatch" in quality_flags and language_repair.get("auto_switch"):
        risk += 0.04
    elif "source_language_mismatch" in quality_flags:
        risk += 0.22
    if "missing_protected_terms" in quality_flags:
        risk += 0.2
    if "high_stakes" in quality_flags:
        risk += 0.18
    if "precision_entities" in quality_flags:
        risk += 0.08
    if "placeholder_translation" in quality_flags or "empty_translation" in quality_flags or "untranslated_echo" in quality_flags:
        risk += 0.18
    if "code_switching" in quality_flags:
        risk += 0.04
    if _safe_float(analysis.get("urgency"), 0.0) >= 0.7:
        risk += 0.06
    return round(max(0.0, min(1.0, risk)), 4)


def language_repair_status(confidence: float, fallback_translation: str, analysis: dict, quality_flags: list[str]) -> dict:
    language = analysis.get("language") or {}
    source_text = str(analysis.get("text") or "").strip()
    translated = (fallback_translation or "").strip()
    mismatch = "source_language_mismatch" in quality_flags
    usable_translation = bool(translated) and not is_placeholder_translation(translated) and translated.lower() != source_text.lower()
    strict_domains = set(analysis.get("domains", {}).get("high_stakes") or []) & STRICT_CONFIRM_DOMAINS
    blockers = [
        flag for flag in (
            "empty_translation",
            "placeholder_translation",
            "untranslated_echo",
            "missing_protected_terms",
            "translation_too_short",
            "translation_too_long",
            "high_ambiguity",
        )
        if flag in quality_flags
    ]
    if strict_domains:
        blockers.append("strict_domain")

    auto_switch = (
        mismatch
        and usable_translation
        and not blockers
        and _safe_float(language.get("confidence"), 0.0) >= 0.75
        and _safe_float(confidence, 0.0) >= 0.62
    )
    if auto_switch:
        mode = "auto_switch"
    elif mismatch:
        mode = "confirm_switch"
    else:
        mode = "none"

    return {
        "mode": mode,
        "auto_switch": auto_switch,
        "from": language.get("declared"),
        "to": language.get("detected"),
        "confidence": language.get("confidence"),
        "usable_translation": usable_translation,
        "blockers": blockers,
    }


def precision_status(confidence: float, analysis: dict, quality_flags: list[str]) -> dict:
    domains = set(analysis.get("domains", {}).get("high_stakes") or [])
    language_repair = analysis.get("language_repair_status") or {}
    protected_terms = analysis.get("protected_terms", {})
    all_terms = protected_terms.get("all") or []
    missing_terms = protected_terms.get("missing") or []
    exact_terms_preserved = bool(all_terms) and not missing_terms
    hard_blockers = []
    for flag in (
        "source_language_mismatch",
        "missing_protected_terms",
        "untranslated_echo",
        "placeholder_translation",
        "empty_translation",
        "translation_too_short",
        "translation_too_long",
        "high_ambiguity",
    ):
        if flag == "source_language_mismatch" and language_repair.get("auto_switch"):
            continue
        if flag in quality_flags:
            hard_blockers.append(flag)
    strict_domains = sorted(domains & STRICT_CONFIRM_DOMAINS)
    fast_lane = (
        bool(domains)
        and domains <= PRECISION_FAST_LANE_DOMAINS
        and not hard_blockers
        and _safe_float(confidence) >= 0.78
        and (not all_terms or exact_terms_preserved)
    )

    if fast_lane:
        mode = "fast_lane"
        requires_confirmation = False
    elif hard_blockers or strict_domains or (domains and _safe_float(confidence) < 0.72):
        mode = "confirm"
        requires_confirmation = True
    elif "precision_entities" in quality_flags:
        mode = "guarded"
        requires_confirmation = False
    else:
        mode = "normal"
        requires_confirmation = False

    return {
        "mode": mode,
        "requires_confirmation": requires_confirmation,
        "exact_terms_preserved": exact_terms_preserved,
        "domains": sorted(domains),
        "strict_domains": strict_domains,
        "fast_lane_domains": sorted(domains & PRECISION_FAST_LANE_DOMAINS),
        "blockers": hard_blockers,
    }


def build_repair_options(text: str, analysis: dict, quality_flags: list[str]) -> list[dict]:
    options: list[dict] = []
    language = analysis.get("language", {})
    precision = analysis.get("precision_status") or {}
    language_repair = analysis.get("language_repair_status") or {}

    if "source_language_mismatch" in quality_flags:
        detected = language.get("detected") or "unknown"
        declared = language.get("declared")
        options.append({
            "type": "auto_switch_source_language" if language_repair.get("auto_switch") else "switch_source_language",
            "label": f"Auto-switch source to {detected}" if language_repair.get("auto_switch") else f"Switch source to {detected}",
            "language": detected,
            "from": declared,
            "applied": bool(language_repair.get("auto_switch")),
            "priority": "high",
        })

    missing_terms = analysis.get("protected_terms", {}).get("missing") or []
    if missing_terms:
        options.append({
            "type": "repeat_terms",
            "label": "Repeat exact name, number, or code",
            "terms": [item.get("value") for item in missing_terms if item.get("value")],
            "priority": "high",
        })

    high_stakes = analysis.get("domains", {}).get("high_stakes") or []
    if high_stakes and precision.get("requires_confirmation", True):
        options.append({
            "type": "confirm_exact",
            "label": "Confirm exact wording before speaking",
            "domains": high_stakes,
            "priority": "high",
        })

    for word in (analysis.get("ambiguity", {}).get("words") or [])[:3]:
        senses = AMBIGUOUS_SENSES.get(word, [])[:3]
        if senses:
            options.append({
                "type": "choose_meaning",
                "label": f"Choose meaning for '{word}'",
                "word": word,
                "options": senses,
                "priority": "normal",
            })

    if any(flag in quality_flags for flag in ("empty_source", "empty_translation", "placeholder_translation", "untranslated_echo")):
        options.append({
            "type": "repeat_slowly",
            "label": "Ask speaker to repeat slowly",
            "priority": "normal",
        })

    if "code_switching" in quality_flags and "source_language_mismatch" not in quality_flags:
        options.append({
            "type": "preserve_code_switch",
            "label": "Preserve mixed-language words",
            "languages": language.get("active_languages") or [],
            "priority": "low",
        })

    return options[:8]


def conversation_turn_policy(decision: dict, analysis: dict, quality_flags: list[str]) -> dict:
    semantic_context = analysis.get("semantic_context") or {}
    recent_turns = [item for item in semantic_context.get("recent_turns", []) if isinstance(item, dict)]
    current_speaker = recent_turns[-1].get("speaker") if recent_turns else None
    previous_speaker = recent_turns[-2].get("speaker") if len(recent_turns) >= 2 else None
    speaker_shift = bool(current_speaker and previous_speaker and current_speaker != previous_speaker)
    risk_score = _safe_float(analysis.get("meaning_risk_score"), 0.0)
    high_stakes = "high_stakes" in quality_flags
    precision = analysis.get("precision_status") or {}
    precision_fast_lane = precision.get("mode") == "fast_lane"
    needs_confirmation = decision.get("type") == "clarification"
    urgent = analysis.get("tone") == "urgent" or _safe_float(analysis.get("urgency"), 0.0) >= 0.7

    if needs_confirmation:
        mode = "confirm_then_translate"
        tts = "skip"
        latency_budget_ms = 350
    elif risk_score >= 0.55 or (high_stakes and not precision_fast_lane):
        mode = "guarded_translate"
        tts = "stream_after_guard"
        latency_budget_ms = 1200
    else:
        mode = "instant_translate"
        tts = "stream_now"
        latency_budget_ms = 900

    if urgent and not needs_confirmation:
        latency_budget_ms = min(latency_budget_ms, 700)

    return {
        "mode": mode,
        "tts": tts,
        "latency_budget_ms": latency_budget_ms,
        "listen_after_playback": True,
        "active_speaker": current_speaker,
        "previous_speaker": previous_speaker,
        "speaker_shift": speaker_shift,
        "interruption_policy": "allow_shift" if speaker_shift or urgent else "normal",
        "route": {
            "from_speaker": current_speaker,
            "source_language": analysis.get("sourceLanguage"),
            "target_language": analysis.get("targetLanguage"),
            "speak_to_listener": decision.get("type") != "clarification",
        },
    }


def conversation_contract(decision: dict, analysis: dict, quality_flags: list[str]) -> dict:
    precision = analysis.get("precision_status") or {}
    requires_exact_confirmation = bool(precision.get("requires_confirmation"))
    return {
        "safe_to_speak": decision.get("type") != "clarification",
        "requires_exact_confirmation": requires_exact_confirmation,
        "preserve_names_numbers_codes": bool(analysis.get("protected_terms", {}).get("all")),
        "allow_partial_translation": (
            decision.get("type") != "clarification"
            and (precision.get("mode") == "fast_lane" or "high_stakes" not in quality_flags)
        ),
        "prefer_plain_language": (
            "high_stakes" in quality_flags
            or _safe_float(analysis.get("speaker_style", {}).get("clarity_preference"), 0.5) >= 0.75
        ),
    }


def decide_response(text: str, fallback_translation: str, confidence: float, analysis: dict, policy: dict | None = None) -> dict:
    policy = policy or {}
    confidence_threshold = _safe_float(policy.get("confidence_threshold"), get_cip_confidence_threshold())
    ambiguity_threshold = _safe_float(policy.get("ambiguity_threshold"), get_cip_ambiguity_threshold())
    quality_flags = analysis.get("quality_flags") or []
    if not (text or "").strip():
        return {
            "type": "clarification",
            "message": "I did not hear speech clearly. Could you repeat that?",
            "reason": "empty_source",
        }
    if not (fallback_translation or "").strip() or is_placeholder_translation(fallback_translation):
        ambiguity = analysis.get("ambiguity", {})
        if ambiguity.get("high"):
            return {
                "type": "clarification",
                "message": clarification_for(text, ambiguity.get("words", [])),
                "reason": "placeholder_translation_ambiguous",
            }
        if "source_language_mismatch" in quality_flags:
            return {
                "type": "clarification",
                "message": clarification_message(text, analysis, "source_language_mismatch"),
                "reason": "placeholder_translation_language_mismatch",
            }
        if analysis.get("domains", {}).get("risk_level") == "high":
            return {
                "type": "clarification",
                "message": clarification_message(text, analysis, "placeholder_translation_high_stakes"),
                "reason": "placeholder_translation_high_stakes",
            }
        if analysis.get("entities") or analysis.get("protected_terms", {}).get("all"):
            return {
                "type": "clarification",
                "message": clarification_message(text, analysis, "missing_protected_terms"),
                "reason": "placeholder_translation_precision",
            }
        return {
            "type": "clarification",
            "message": "I could not translate that reliably yet. Could you repeat it another way?",
            "reason": "placeholder_translation",
        }
    if "untranslated_echo" in quality_flags and analysis.get("sourceLanguage") != analysis.get("targetLanguage"):
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "untranslated_echo"),
            "reason": "untranslated_echo",
        }
    language_repair = analysis.get("language_repair_status") or {}
    if "source_language_mismatch" in quality_flags and not language_repair.get("auto_switch"):
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "source_language_mismatch"),
            "reason": "source_language_mismatch",
        }
    if "missing_protected_terms" in quality_flags:
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "missing_protected_terms"),
            "reason": "missing_protected_terms",
        }
    precision = analysis.get("precision_status") or {}
    if "high_stakes" in quality_flags and precision.get("requires_confirmation", True):
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "high_stakes_confirmation"),
            "reason": "high_stakes_confirmation",
        }
    if policy.get("force_clarification") and confidence < confidence_threshold + 0.08:
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "adaptive_quality_gate"),
            "reason": "adaptive_quality_gate",
        }
    if confidence < confidence_threshold:
        return {
            "type": "clarification",
            "message": clarification_message(text, analysis, "low_confidence"),
            "reason": "low_confidence",
        }
    ambiguity = analysis.get("ambiguity", {})
    if _safe_float(ambiguity.get("score"), 0.0) >= ambiguity_threshold:
        return {
            "type": "clarification",
            "message": clarification_for(text, ambiguity.get("words", [])),
            "reason": "ambiguous_language",
        }
    if analysis.get("intent") == "emotional_statement":
        return {
            "type": "supportive_response",
            "message": "I understand how you feel.",
            "mode": "supportive",
            "reason": "emotional_context",
        }
    if _safe_float(analysis.get("urgency"), 0.0) >= 0.7 or policy.get("response_speed_boost"):
        return {"type": "response", "mode": "fast", "reason": "urgent"}
    return {"type": "response", "mode": "fast" if confidence >= 0.72 else "normal"}


def response_plan(decision: dict, analysis: dict, quality_flags: list[str]) -> dict:
    decision_type = decision.get("type")
    if decision_type == "clarification":
        action = "ask_clarification"
    elif decision_type == "supportive_response":
        action = "translate_with_supportive_tone"
    else:
        action = "translate_and_speak"

    domains = analysis.get("domains", {})
    speaker_style = analysis.get("speaker_style", {})
    precision = analysis.get("precision_status") or {}
    high_stakes = domains.get("risk_level") == "high"
    precision_mode = high_stakes or "precision_entities" in quality_flags
    if precision.get("mode") == "fast_lane":
        strategy = "precision_fast_lane"
    elif precision.get("requires_confirmation") or precision_mode:
        strategy = "precision_confirm"
    else:
        strategy = "natural"
    if decision_type == "supportive_response":
        strategy = "supportive_plain_language"
    language_repair = analysis.get("language_repair_status") or {}
    if "source_language_mismatch" in quality_flags:
        strategy = "language_auto_repair" if language_repair.get("auto_switch") else "language_repair"
    elif "missing_protected_terms" in quality_flags:
        strategy = "protected_term_repair"

    risk_score = _safe_float(analysis.get("meaning_risk_score"), 0.0)
    repair_options = build_repair_options(analysis.get("text") or "", analysis, quality_flags)
    preserve_terms = [item.get("value") for item in analysis.get("protected_terms", {}).get("all", [])]
    turn_policy = conversation_turn_policy(decision, analysis, quality_flags)
    contract = conversation_contract(decision, analysis, quality_flags)

    return {
        "action": action,
        "speak": decision_type != "clarification",
        "needs_user_input": decision_type == "clarification",
        "priority": "high" if analysis.get("tone") == "urgent" or high_stakes or risk_score >= 0.65 else "normal",
        "strategy": strategy,
        "confirm_numbers": "precision_entities" in quality_flags,
        "avoid_idioms": high_stakes or _safe_float(speaker_style.get("clarity_preference"), 0.5) >= 0.75,
        "register": speaker_style.get("suggested_register") or "plain",
        "suggested_source_language": analysis.get("language", {}).get("detected"),
        "preserve_terms": preserve_terms,
        "meaning_risk_score": risk_score,
        "repair_options": repair_options,
        "turn_policy": turn_policy,
        "conversation_contract": contract,
        "client_hints": {
            "skip_tts": decision_type == "clarification",
            "tts_mode": turn_policy["tts"],
            "latency_budget_ms": turn_policy["latency_budget_ms"],
            "active_speaker": turn_policy["active_speaker"],
            "speaker_shift": turn_policy["speaker_shift"],
            "auto_switch_source_language": bool(language_repair.get("auto_switch")),
            "suggest_source_language_switch": (
                "source_language_mismatch" in quality_flags
                and not language_repair.get("auto_switch")
                and _safe_float(analysis.get("language", {}).get("confidence"), 0.0) >= 0.75
            ),
            "language_auto_repaired": bool(language_repair.get("auto_switch")),
            "repaired_source_language": language_repair.get("to") if language_repair.get("auto_switch") else None,
            "language_repair": language_repair,
            "highlight_terms": preserve_terms,
            "ask_before_speaking": contract["requires_exact_confirmation"],
        },
        "quality_flags": quality_flags,
    }


def evaluate_translation_brain(
    text: str,
    target_language: str,
    *,
    fallback_translation: str | None = None,
    source_language: str | None = None,
    stt_confidence: float | None = None,
    translation_confidence: float | None = None,
    context=None,
    speaker_context=None,
    semantic_context: dict | None = None,
) -> dict:
    source_text = (text or "").strip()
    fallback = (fallback_translation or "").strip()
    analysis = analyze_communication(
        source_text,
        context=context,
        speaker_context=speaker_context,
        semantic_context=semantic_context,
    )
    analysis["text"] = source_text
    analysis["sourceLanguage"] = source_language
    analysis["targetLanguage"] = target_language
    analysis["semantic_context"] = semantic_context or {}
    analysis["speaker_profile"] = {
        "turns": int((speaker_context or {}).get("turns") or 0),
        "language": (speaker_context or {}).get("language"),
    }
    analysis["language"] = detect_language_mix(source_text, source_language)
    protected_terms = extract_protected_terms(source_text)
    analysis["protected_terms"] = {
        "all": protected_terms,
        "missing": missing_protected_terms(protected_terms, fallback),
    }
    policy = derive_adaptive_policy(context, speaker_context, semantic_context)
    quality_flags = translation_quality_flags(source_text, fallback, source_language, target_language, analysis)
    analysis["quality_flags"] = quality_flags
    analysis["policy"] = policy
    confidence = brain_confidence_score(
        text=source_text,
        fallback_translation=fallback,
        stt_confidence=stt_confidence,
        translation_confidence=translation_confidence,
        analysis=analysis,
    )
    analysis["stt_confidence"] = round(estimate_stt_confidence(source_text) if stt_confidence is None else _safe_float(stt_confidence), 4)
    analysis["translation_confidence"] = round(
        estimate_translation_confidence(source_text, fallback)
        if translation_confidence is None
        else _safe_float(translation_confidence),
        4,
    )
    analysis["language_repair_status"] = language_repair_status(confidence, fallback, analysis, quality_flags)
    analysis["precision_status"] = precision_status(confidence, analysis, quality_flags)
    analysis["meaning_risk_score"] = meaning_risk_score(confidence, analysis, quality_flags)

    decision = decide_response(source_text, fallback, confidence, analysis, policy)
    plan = response_plan(decision, analysis, quality_flags)
    translated = "" if decision["type"] == "clarification" else fallback
    return {
        "text": source_text,
        "translated": translated,
        "targetLanguage": target_language,
        "sourceLanguage": source_language,
        "provider": "local",
        "translation_source": "UT+CIP",
        "confidence": round(confidence, 4),
        "analysis": analysis,
        "decision": decision,
        "response_plan": plan,
    }
