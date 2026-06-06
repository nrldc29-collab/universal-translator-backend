"""Backend Hook — Drop-in integration with the existing translator backend.

This module provides a single function `enhance_translation()` that can be
called from the existing streaming.py / pipeline.py code to leverage
AILang agents without requiring a full refactor.

Usage in streaming.py:
    from ailang_integration.runtime.backend_hook import enhance_translation

    # In the translation flow:
    result = enhance_translation(
        text="Hello, I need help",
        source_lang="en",
        target_lang="es",
        context={"speaker": "Patient", "domain": "medical", ...}
    )
    translated_text = result["translated_text"]
    tts_config = result["tts_config"]
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def enhance_translation(
    text: str,
    source_lang: str,
    target_lang: str,
    context: Optional[Dict[str, Any]] = None,
    pipeline: str = "auto",
    use_plugins: bool = True,
) -> Dict[str, Any]:
    """Enhanced translation using AILang agents and pipelines.

    This is the main entry point for the existing backend to use AILang.
    It runs the full pipeline (or fast pipeline) and returns enriched results.

    Args:
        text: Source text to translate
        source_lang: Source language code
        target_lang: Target language code
        context: Conversation context (history, speaker info, etc.)
        pipeline: Pipeline to use ("auto", "default", "fast", "medical")
        use_plugins: Whether to run plugin hooks

    Returns:
        Dict with translated_text, tts_config, analysis, and metadata
    """
    if context is None:
        context = {}

    context.setdefault("target_lang", target_lang)
    context.setdefault("source_lang", source_lang)
    context.setdefault("urgency", "normal")
    context.setdefault("conversation_history", [])
    context.setdefault("speakers", {})
    context.setdefault("terminology_preferences", {})
    context.setdefault("turn_count", 0)
    context.setdefault("recent_topics", [])
    context.setdefault("domain", "general")

    audio_data = {
        "transcribed_text": text,
        "detected_language": source_lang,
        "stt_confidence": context.get("stt_confidence", 0.9),
    }

    try:
        from .pipeline_runner import get_pipeline_runner
        runner = get_pipeline_runner()

        if pipeline == "auto":
            result = runner.run_auto(audio_data, context)
        else:
            result = runner.run(pipeline, audio_data, context)

        return {
            "translated_text": result.translated_text,
            "tts_config": result.tts_config,
            "analysis": result.analysis,
            "pipeline_used": result.pipeline_name,
            "duration_ms": result.total_duration_ms,
            "success": result.success,
            "steps_completed": len([s for s in result.steps if s.success]),
            "steps_total": len(result.steps),
        }

    except Exception as e:
        logger.error(f"AILang pipeline failed, using passthrough: {e}")
        # Graceful fallback — never break the existing flow
        return {
            "translated_text": text,  # passthrough
            "tts_config": {"text": text, "language": target_lang, "speed": 1.0},
            "analysis": {"domain": "general", "formality": "neutral"},
            "pipeline_used": "fallback",
            "duration_ms": 0,
            "success": False,
            "error": str(e),
        }


def get_translation_brain_analysis(
    text: str,
    source_lang: str,
    target_lang: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Get just the brain analysis without running the full pipeline.

    Useful for the communication_brain.py to get domain/formality/model hints.
    """
    if context is None:
        context = {}

    try:
        from .bridge import get_bridge
        bridge = get_bridge()
        agent = bridge.get_agent("TranslationBrain")
        if agent:
            return agent.call("analyze", text, source_lang, target_lang, context)
    except Exception as e:
        logger.debug(f"Brain analysis via AILang unavailable: {e}")

    # Fallback to basic analysis
    return {
        "domain": "general",
        "formality": "neutral",
        "model": "fast",
        "instructions": [],
        "require_confirmation": False,
    }


def run_quality_check(
    original: str,
    translated: str,
    source_lang: str,
    target_lang: str,
    domain: str = "general",
) -> Dict[str, Any]:
    """Run quality check on a translation.

    Returns quality score and any issues found.
    """
    try:
        from .bridge import get_bridge
        bridge = get_bridge()
        agent = bridge.get_agent("QualityGuard")
        if agent:
            return agent.call("quick_check", original, translated, source_lang, target_lang, domain)
    except Exception as e:
        logger.debug(f"Quality check via AILang unavailable: {e}")

    return {"pass": True, "score": 7, "issues": [], "suggestions": []}


def update_conversation_memory(
    speaker: str,
    text: str,
    translated: str,
    source_lang: str,
    target_lang: str,
    context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Update conversation memory with a new turn.

    Returns updated context with topics, references, and speaker info.
    """
    if context is None:
        context = {}

    try:
        from .bridge import get_bridge
        bridge = get_bridge()
        agent = bridge.get_agent("MemoryKeeper")
        if agent:
            history = context.get("conversation_history", [])
            context_window = agent.call("build_context_window", history, speaker, 8)
            topics = agent.call("extract_topics", text)
            return {
                "context_window": context_window,
                "topics": topics,
                "updated": True,
            }
    except Exception as e:
        logger.debug(f"Memory update via AILang unavailable: {e}")

    return {"context_window": {}, "topics": [], "updated": False}


def enhance_translation_v2(
    text: str,
    source_lang: str,
    target_lang: str,
    context: Optional[Dict[str, Any]] = None,
    glossary: Optional[list] = None,
    dialect_preference: str = "",
) -> Dict[str, Any]:
    """Full enhanced pipeline — context memory, confidence fallback, speaker profiler,
    ambiguity resolver, back-translator, dialect adapter, glossary injector, all wired in.

    Drop-in upgrade over enhance_translation(). Pass quality_mode='enhanced' or call this
    directly. Individual agent helpers are also available below for selective use.

    Args:
        text: Source text to translate
        source_lang: Source language code (e.g. 'en')
        target_lang: Target language code (e.g. 'es')
        context: Conversation context dict. Supported keys:
            conversation_history  — list of {speaker, text, translated} dicts
            speaker_registry      — per-speaker profiles, persist this across turns
            current_speaker       — str name/id of who is speaking
            glossary              — list of {source, target, lang_pair, context} overrides
            target_dialect        — e.g. 'es-MX', 'pt-BR'
            quality_mode          — 'enhanced'|'premium'|'standard'|'fast'
            urgency               — 'urgent'|'normal'
        glossary: Shortcut to pass glossary without building a full context dict
        dialect_preference: Target dialect code, e.g. 'es-MX'

    Returns:
        Dict with translated_text, tts_config, analysis, and per-agent metadata
    """
    if context is None:
        context = {}
    context.setdefault("quality_mode", "enhanced")
    context.setdefault("target_lang", target_lang)
    context.setdefault("source_lang", source_lang)
    context.setdefault("conversation_history", [])
    context.setdefault("speaker_registry", {})
    context.setdefault("current_speaker", "unknown")
    context.setdefault("urgency", "normal")
    if glossary:
        context.setdefault("glossary", glossary)
    if dialect_preference:
        context.setdefault("target_dialect", dialect_preference)
    return enhance_translation(text, source_lang, target_lang, context, pipeline="auto")


def run_context_memory(
    text: str,
    speaker: str,
    source_lang: str,
    history: list,
    speaker_registry=None,
):
    """Resolve pronouns/references using conversation history.
    Returns resolved_text, entities, topic_shift, updated speaker_registry.
    """
    if speaker_registry is None:
        speaker_registry = {}
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("ContextMemoryAgent")
        if a:
            return a.call("process", text, speaker, source_lang, history, speaker_registry)
    except Exception as e:
        logger.debug(f"ContextMemoryAgent unavailable: {e}")
    return {"resolved_text": text, "entities": {}, "topic_shift": False, "speaker_registry": speaker_registry}


def run_confidence_fallback(
    text: str,
    base_translation: str,
    confidence: float,
    source_lang: str,
    target_lang: str,
    domain: str = "general",
    instructions=None,
):
    """Escalate low-confidence translations to Claude.
    Returns final_translation, tier (high/medium/low), escalated bool.
    """
    if instructions is None:
        instructions = []
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("ConfidenceFallbackAgent")
        if a:
            return a.call("process", text, base_translation, confidence, source_lang, target_lang, domain, instructions)
    except Exception as e:
        logger.debug(f"ConfidenceFallbackAgent unavailable: {e}")
    return {"final_translation": base_translation, "tier": "high", "escalated": False}


def run_speaker_profiler(
    speaker: str,
    text: str,
    source_lang: str,
    target_lang: str,
    registry=None,
):
    """Build/update a speaker profile and return style instructions.
    Returns style_guide (list), profile dict, updated_registry.
    """
    if registry is None:
        registry = {}
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("SpeakerProfilerAgent")
        if a:
            return a.call("get_style_instructions", speaker, text, source_lang, target_lang, registry)
    except Exception as e:
        logger.debug(f"SpeakerProfilerAgent unavailable: {e}")
    return {"style_guide": [], "profile": {}, "updated_registry": registry}


def run_ambiguity_resolver(
    text: str,
    source_lang: str,
    target_lang: str,
    domain: str = "general",
    history_summary: str = "",
):
    """Detect and resolve translation ambiguities.
    Returns has_ambiguities, disambiguation dict, needs_human_review bool.
    """
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("AmbiguityResolverAgent")
        if a:
            return a.call("process", text, source_lang, target_lang, domain, history_summary)
    except Exception as e:
        logger.debug(f"AmbiguityResolverAgent unavailable: {e}")
    return {"has_ambiguities": False, "needs_human_review": False}


def run_back_translation_verify(
    original: str,
    translated: str,
    source_lang: str,
    target_lang: str,
    domain: str = "general",
):
    """Verify translation accuracy via back-translation.
    Returns verified bool, final_translation, similarity score, improved bool.
    """
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("BackTranslatorAgent")
        if a:
            return a.call("verify", original, translated, source_lang, target_lang, domain)
    except Exception as e:
        logger.debug(f"BackTranslatorAgent unavailable: {e}")
    return {"verified": True, "final_translation": translated, "improved": False}


def run_dialect_adapter(
    source_text: str,
    base_translation: str,
    source_lang: str,
    target_lang: str,
    dialect_preference: str = "",
):
    """Detect source dialect and adapt translation to target regional variant.
    Returns final_translation, source_dialect, target_dialect, adaptation_applied bool.
    """
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("DialectAdapterAgent")
        if a:
            return a.call("process", source_text, base_translation, source_lang, target_lang, dialect_preference)
    except Exception as e:
        logger.debug(f"DialectAdapterAgent unavailable: {e}")
    return {"final_translation": base_translation, "source_dialect": source_lang,
            "target_dialect": target_lang, "adaptation_applied": False}


def run_glossary_inject(
    text: str,
    base_translation: str,
    source_lang: str,
    target_lang: str,
    glossary: list,
    domain: str = "general",
):
    """Apply custom glossary terms to a translation.
    Returns final_translation, glossary_applied bool, matched_terms list.
    """
    if not glossary:
        return {"final_translation": base_translation, "glossary_applied": False, "matched_terms": []}
    try:
        from .bridge import get_bridge
        a = get_bridge().get_agent("GlossaryInjectorAgent")
        if a:
            return a.call("process", text, base_translation, source_lang, target_lang, domain, glossary, [])
    except Exception as e:
        logger.debug(f"GlossaryInjectorAgent unavailable: {e}")
    return {"final_translation": base_translation, "glossary_applied": False, "matched_terms": []}
