import re


USE_AI_REFINEMENT = False


FILLER_PATTERNS = [
    r"\buh\b",
    r"\bum\b",
    r"\blike\b",
    r"\byou know\b",
]


def _clean_spacing(text: str) -> str:
    text = re.sub(r"\s+", " ", (text or "").strip())
    text = re.sub(r"\s+([,.!?;:])", r"\1", text)
    return text


def _sentence_case(text: str) -> str:
    if not text:
        return text
    return text[0].upper() + text[1:]


def apply_context_memory(text, context, speaker_context=None):
    # Keep this conservative. It avoids changing meaning while still letting CIP
    # attach recent context metadata for downstream decisions.
    return text


def run_llm_refinement(source_text, text, context=None):
    return text


def refine_translation(source_text, translated_text, context=None, speaker_context=None):
    text = _clean_spacing(translated_text)
    if not text:
        return ""
    for pattern in FILLER_PATTERNS:
        text = re.sub(pattern, "", text, flags=re.I)
    text = _clean_spacing(text)
    text = apply_context_memory(text, context, speaker_context)
    if USE_AI_REFINEMENT:
        text = run_llm_refinement(source_text, text, context)
    return _sentence_case(_clean_spacing(text))
