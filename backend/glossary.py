"""Local glossary and domain-term protection for the main translation pipeline.

Works without AILang or cloud APIs — deterministic term handling for
medical, legal, and user-defined glossary entries.
"""

from __future__ import annotations

import re
from threading import Lock
from typing import Any

from backend.ht_high_stakes_glossary import HT_HIGH_STAKES_GLOSSARY

KEEP_OPEN = "[KEEP]"
KEEP_CLOSE = "[/KEEP]"

# Latin-script drug names and acronyms that should survive translation unchanged.
MEDICAL_DO_NOT_TRANSLATE = (
    "ibuprofen",
    "acetaminophen",
    "amoxicillin",
    "metformin",
    "lisinopril",
    "atorvastatin",
    "omeprazole",
    "COVID-19",
    "MRI",
    "CT scan",
    "ECG",
    "EKG",
    "IV",
    "mg",
    "ml",
)

# Built-in high-stakes term pairs (merged with session glossary at runtime).
DEFAULT_GLOSSARY: list[dict[str, str]] = [
    {"source": "blood pressure", "target": "presión arterial", "lang_pair": "en-es", "context": "medical"},
    {"source": "blood pressure", "target": "tansyon", "lang_pair": "en-ht", "context": "medical"},
    {"source": "heart rate", "target": "frecuencia cardíaca", "lang_pair": "en-es", "context": "medical"},
    {"source": "heart rate", "target": "batman kè", "lang_pair": "en-ht", "context": "medical"},
    {"source": "emergency room", "target": "sala de emergencias", "lang_pair": "en-es", "context": "medical"},
    {"source": "emergency room", "target": "sal ijans", "lang_pair": "en-ht", "context": "medical"},
    {"source": "attorney", "target": "abogado", "lang_pair": "en-es", "context": "legal"},
    {"source": "attorney", "target": "avoka", "lang_pair": "en-ht", "context": "legal"},
    {"source": "passport", "target": "pasaporte", "lang_pair": "en-es", "context": "travel"},
    {"source": "passport", "target": "paspò", "lang_pair": "en-ht", "context": "travel"},
    {"source": "I need help", "target": "Necesito ayuda", "lang_pair": "en-es", "context": "general"},
    {"source": "I need help", "target": "Mwen bezwen èd", "lang_pair": "en-ht", "context": "general"},
    {"source": "Mwen bezwen èd", "target": "I need help", "lang_pair": "ht-en", "context": "general"},
    {"source": "M ap byen", "target": "I'm fine", "lang_pair": "ht-en", "context": "general"},
] + HT_HIGH_STAKES_GLOSSARY

_NEGATION_SOURCE = frozenset({"not", "no", "never", "cannot", "can't", "dont", "don't", "doesnt", "doesn't", "without"})
_NEGATION_TARGET_HT = frozenset({"pa", "non", "san", "poko", "okenn"})
_NEGATION_TARGET_EN = frozenset({"not", "no", "never", "cannot", "can't", "without", "don't", "dont"})
_DOSAGE_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\s*(?:mg|ml|mcg|g|iu|unit|units|%)\b", re.IGNORECASE)

_session_glossaries: dict[str, list[dict[str, Any]]] = {}
_glossary_lock = Lock()


def set_session_glossary(session_id: str, glossary: list[dict[str, Any]]) -> None:
    with _glossary_lock:
        _session_glossaries[session_id] = list(glossary or [])


def get_session_glossary(session_id: str) -> list[dict[str, Any]]:
    with _glossary_lock:
        custom = list(_session_glossaries.get(session_id, []))
    return custom + DEFAULT_GLOSSARY


def _lang_pair(source_lang: str, target_lang: str) -> str:
    return f"{source_lang}-{target_lang}"


def _matching_entries(glossary: list[dict[str, Any]], source_lang: str, target_lang: str) -> list[dict[str, Any]]:
    pair = _lang_pair(source_lang, target_lang)
    return [
        entry
        for entry in glossary
        if entry.get("lang_pair") in {pair, "*"}
        and entry.get("source") and entry.get("target")
    ]


def protect_medical_terms(text: str) -> tuple[str, bool]:
    """Wrap medical acronyms/drug names so Marian/NLLB leaves them unchanged."""
    if not text.strip():
        return text, False
    result = text
    applied = False
    for term in sorted(MEDICAL_DO_NOT_TRANSLATE, key=len, reverse=True):
        pattern = re.compile(re.escape(term), flags=re.IGNORECASE)
        if pattern.search(result):
            result = pattern.sub(lambda m: f"{KEEP_OPEN}{m.group(0)}{KEEP_CLOSE}", result)
            applied = True
    return result, applied


def restore_protected_terms(text: str) -> str:
    if KEEP_OPEN not in text:
        return text
    return text.replace(KEEP_OPEN, "").replace(KEEP_CLOSE, "")


def _normalize_phrase(text: str) -> str:
    return " ".join((text or "").lower().split())


def _word_boundary_pattern(source: str) -> re.Pattern[str]:
    escaped = re.escape(source.strip())
    if not escaped:
        return re.compile(r"a^")
    if " " in source.strip():
        return re.compile(rf"(?<!\w){escaped}(?!\w)", flags=re.IGNORECASE)
    return re.compile(rf"\b{escaped}\b", flags=re.IGNORECASE)


def _text_has_negation(text: str, *, language: str | None = None) -> bool:
    tokens = set(re.findall(r"[a-zA-Zà-ÿ']+", (text or "").lower()))
    lang = str(language or "").lower().split("-")[0]
    if lang == "ht":
        return bool(tokens & _NEGATION_TARGET_HT)
    if lang == "en" or not lang:
        return bool(tokens & _NEGATION_TARGET_EN)
    return bool(tokens & (_NEGATION_SOURCE | _NEGATION_TARGET_HT | _NEGATION_TARGET_EN))


def map_environment_for_stt(environment: str | None) -> str:
    """Normalize client/adaptive VAD environment labels for Whisper tuning."""
    env = str(environment or "unknown").strip().lower()
    aliases = {
        "unknown": "quiet",
        "auto": "quiet",
        "noisy": "crowded",
        "outdoor": "street",
        "outdoors": "street",
    }
    env = aliases.get(env, env)
    if env in {"quiet", "office", "restaurant", "street", "crowded", "noisy"}:
        return env
    return "quiet"


def promote_glossary_correction(
    session_id: str,
    *,
    source: str,
    target: str,
    source_lang: str,
    target_lang: str,
    context: str = "general",
) -> dict[str, Any]:
    """Persist a human-verified correction for the rest of the session."""
    source_clean = (source or "").strip()
    target_clean = (target or "").strip()
    if not source_clean or not target_clean:
        return {"ok": False, "reason": "empty"}
    entry = {
        "source": source_clean,
        "target": target_clean,
        "lang_pair": _lang_pair(source_lang, target_lang),
        "context": context or "general",
        "verified": True,
    }
    with _glossary_lock:
        bucket = _session_glossaries.setdefault(session_id, [])
        for existing in bucket:
            if (
                _normalize_phrase(existing.get("source", "")) == _normalize_phrase(source_clean)
                and existing.get("lang_pair") == entry["lang_pair"]
            ):
                existing.update(entry)
                return {"ok": True, "updated": True, "entry": entry}
        bucket.append(entry)
    return {"ok": True, "updated": False, "entry": entry}


def find_glossary_matches(text: str, glossary: list[dict[str, Any]], source_lang: str, target_lang: str) -> list[dict[str, Any]]:
    lowered = _normalize_phrase(text)
    matches = []
    for entry in _matching_entries(glossary, source_lang, target_lang):
        source = str(entry["source"]).strip()
        if not source:
            continue
        source_norm = _normalize_phrase(source)
        if len(source_norm) <= 2:
            if source_norm == lowered or source_norm in lowered.split():
                matches.append(entry)
            continue
        if _word_boundary_pattern(source).search(text):
            matches.append(entry)
        elif source_norm == lowered:
            matches.append(entry)
    return matches


def try_direct_glossary_translation(
    text: str,
    glossary: list[dict[str, Any]],
    source_lang: str,
    target_lang: str,
) -> str | None:
    """Return a verified target when the full utterance matches glossary/phrase intent."""
    normalized = _normalize_phrase(text)
    if not normalized:
        return None
    entries = _matching_entries(glossary, source_lang, target_lang)
    exact = [
        entry for entry in entries
        if _normalize_phrase(str(entry.get("source", ""))) == normalized
    ]
    if exact:
        return str(exact[0]["target"]).strip()
    # Longest substring match for short emergency phrases embedded in longer text.
    partial = sorted(
        [entry for entry in entries if _word_boundary_pattern(str(entry["source"])).search(text)],
        key=lambda item: len(str(item.get("source", ""))),
        reverse=True,
    )
    if partial and len(_normalize_phrase(str(partial[0]["source"]))) >= max(8, len(normalized) // 2):
        return str(partial[0]["target"]).strip()
    return None


def check_translation_safety(
    source_text: str,
    translated_text: str,
    *,
    source_lang: str | None = None,
    target_lang: str | None = None,
    strict_medical: bool = False,
) -> dict[str, Any]:
    """Block obviously unsafe high-stakes translations (negation/dosage loss)."""
    issues: list[str] = []
    source_neg = _text_has_negation(source_text, language=source_lang)
    target_neg = _text_has_negation(translated_text, language=target_lang)
    if source_neg and not target_neg:
        issues.append("negation_lost")
    if not source_neg and target_neg:
        issues.append("negation_added")
    dosages = _DOSAGE_PATTERN.findall(source_text or "")
    for dose in dosages:
        dose_val = re.search(r"\d+(?:\.\d+)?", dose)
        if dose_val and dose_val.group() not in (translated_text or ""):
            issues.append(f"dosage_missing:{dose.strip()}")
    critical = bool(issues) and (strict_medical or bool(dosages) or source_neg)
    return {
        "safe": not issues,
        "issues": issues,
        "critical": critical,
        "block_tts": critical,
        "needs_clarification": bool(issues),
    }


def apply_glossary_substitutions(
    source_text: str,
    translated_text: str,
    glossary: list[dict[str, Any]],
    source_lang: str,
    target_lang: str,
) -> tuple[str, bool]:
    """Ensure mandatory glossary targets appear in the final translation."""
    matches = find_glossary_matches(source_text, glossary, source_lang, target_lang)
    if not matches:
        return translated_text, False

    result = translated_text
    applied = False
    for entry in sorted(matches, key=lambda item: len(str(item.get("source", ""))), reverse=True):
        source = str(entry["source"])
        target = str(entry["target"])
        if target.lower() in result.lower():
            continue
        pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
        if pattern.search(source_text):
            # Prefer replacing a literal source carry-over; otherwise append a corrected clause.
            if pattern.search(result):
                result = pattern.sub(target, result)
            else:
                result = f"{result} ({target})"
            applied = True
    return result.strip(), applied


def prepare_for_translation(
    text: str,
    *,
    strict_medical: bool = False,
) -> tuple[str, dict[str, Any]]:
    metadata: dict[str, Any] = {"protected_terms": False, "strict_medical": strict_medical}
    working = text
    if strict_medical:
        working, protected = protect_medical_terms(working)
        metadata["protected_terms"] = protected
    return working, metadata


def finalize_translation(
    source_text: str,
    translated_text: str,
    *,
    session_id: str,
    source_lang: str,
    target_lang: str,
    strict_medical: bool = False,
    metadata: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    meta = dict(metadata or {})
    glossary = get_session_glossary(session_id)
    result = restore_protected_terms(translated_text)
    result, glossary_applied = apply_glossary_substitutions(
        source_text, result, glossary, source_lang, target_lang
    )
    meta["glossary_applied"] = glossary_applied
    meta["glossary_entries"] = len(find_glossary_matches(source_text, glossary, source_lang, target_lang))
    if strict_medical:
        meta["strict_medical"] = True
    return result, meta


def glossary_coverage_score(source_text: str, translated_text: str, glossary: list[dict[str, Any]], source_lang: str, target_lang: str) -> float:
    matches = find_glossary_matches(source_text, glossary, source_lang, target_lang)
    if not matches:
        return 1.0
    hits = sum(1 for entry in matches if str(entry["target"]).lower() in translated_text.lower())
    return hits / len(matches)


def glossary_blocks_clarification(
    source_text: str,
    translated_text: str,
    glossary: list[dict[str, Any]],
    source_lang: str,
    target_lang: str,
) -> bool:
    """Built-in/session glossary hits should still translate under high-stakes CIP rules."""
    if not find_glossary_matches(source_text, glossary, source_lang, target_lang):
        return False
    return glossary_coverage_score(source_text, translated_text, glossary, source_lang, target_lang) >= 1.0
