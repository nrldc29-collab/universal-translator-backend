"""Local glossary and domain-term protection for the main translation pipeline.

Works without AILang or cloud APIs — deterministic term handling for
medical, legal, and user-defined glossary entries.
"""

from __future__ import annotations

import re
from threading import Lock
from typing import Any

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
]

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


def find_glossary_matches(text: str, glossary: list[dict[str, Any]], source_lang: str, target_lang: str) -> list[dict[str, Any]]:
    lowered = text.lower()
    matches = []
    for entry in _matching_entries(glossary, source_lang, target_lang):
        source = str(entry["source"]).lower()
        if source and source in lowered:
            matches.append(entry)
    return matches


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
