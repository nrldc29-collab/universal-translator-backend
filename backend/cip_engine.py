from backend.communication_brain import detect_intent, detect_tone, evaluate_translation_brain


def evaluate_local_cip(
    text: str,
    target_language: str,
    fallback_translation: str | None = None,
    source_language: str | None = None,
    stt_confidence: float | None = None,
    translation_confidence: float | None = None,
    context=None,
    speaker_context=None,
    semantic_context: dict | None = None,
) -> dict | None:
    return evaluate_translation_brain(
        text,
        target_language,
        fallback_translation=fallback_translation,
        source_language=source_language,
        stt_confidence=stt_confidence,
        translation_confidence=translation_confidence,
        context=context,
        speaker_context=speaker_context,
        semantic_context=semantic_context,
    )
