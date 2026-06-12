import re


USE_AI_REFINEMENT = False


UNIVERSAL_FILLER_PATTERNS = [
    r"\buh\b",
    r"\bum\b",
]
SOURCE_MIRROR_FILLER_PATTERNS = [
    r"\blike\b",
    r"\byou know\b",
]


def _strip_fillers(source_text: str, translated_text: str) -> str:
    text = translated_text or ""
    for pattern in UNIVERSAL_FILLER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.I)
    source_lower = (source_text or "").lower()
    for pattern in SOURCE_MIRROR_FILLER_PATTERNS:
        if re.search(pattern, source_lower, flags=re.I):
            text = re.sub(pattern, "", text, flags=re.I)
    return text


def _clean_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def _source_proper_nouns(source_text: str) -> list[str]:
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


def _context_named_terms(context, speaker_context=None) -> list[str]:
    items: list = []
    if isinstance(context, list):
        items.extend(context)
    elif isinstance(context, dict):
        items.extend(context.get("history") or [])
    speaker_history = (speaker_context or {}).get("history") or []
    for entry in speaker_history:
        if isinstance(entry, str):
            items.append({"source_text": entry})
        elif isinstance(entry, dict):
            items.append(entry)
    terms: list[str] = []
    for item in items[-8:]:
        if isinstance(item, dict):
            source = item.get("source_text") or item.get("source") or ""
        else:
            source = str(item)
        terms.extend(_source_proper_nouns(source))
    seen: list[str] = []
    for term in terms:
        if term not in seen:
            seen.append(term)
    return seen


def apply_context_memory(text, context, speaker_context=None):
    working = text or ""
    for term in _context_named_terms(context, speaker_context):
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if pattern.search(working):
            working = pattern.sub(term, working, count=1)
    return working


def _restore_proper_noun_casing(source_text: str, translated_text: str) -> str:
    working = translated_text or ""
    for term in _source_proper_nouns(source_text):
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", term):
            if term in working:
                continue
            continue
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if pattern.search(working):
            working = pattern.sub(term, working, count=1)
    return working


def _inject_missing_proper_nouns(source_text: str, translated_text: str) -> str:
    working = (translated_text or "").strip()
    for term in _source_proper_nouns(source_text):
        if re.search(r"[\u4e00-\u9fff\u3040-\u30ff\uac00-\ud7af]", term):
            if term not in working:
                working = f"{working} ({term})".strip() if working else term
            continue
        pattern = re.compile(r"\b" + re.escape(term) + r"\b", re.IGNORECASE)
        if not pattern.search(working):
            working = f"{working} {term}".strip() if working else term
    return working


def run_llm_refinement(source_text, text, context=None):
    return text


def refine_translation(source_text, translated_text, context=None, speaker_context=None):
    text = _clean_spacing(translated_text)
    if not text:
        return ""
    text = _strip_fillers(source_text, text)
    text = _clean_spacing(text)
    text = apply_context_memory(text, context, speaker_context)
    text = _inject_missing_proper_nouns(source_text, text)
    text = _restore_proper_noun_casing(source_text, text)
    if USE_AI_REFINEMENT:
        text = run_llm_refinement(source_text, text, context)
    return _sentence_case(_clean_spacing(text))
