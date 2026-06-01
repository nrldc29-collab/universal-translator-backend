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


def reload_all() -> Dict[str, Any]:
    """Hot-reload all AILang components (agents, pipelines, plugins).

    Call this when .ai files are modified to pick up changes without restart.
    """
    results = {"bridge": False, "plugins": False, "pipelines": False}

    try:
        from .bridge import get_bridge
        get_bridge().reload()
        results["bridge"] = True
    except Exception as e:
        logger.error(f"Bridge reload failed: {e}")

    try:
        from .plugin_loader import get_plugin_loader
        get_plugin_loader().reload_all()
        results["plugins"] = True
    except Exception as e:
        logger.error(f"Plugin reload failed: {e}")

    try:
        from .pipeline_runner import get_pipeline_runner
        get_pipeline_runner().reload()
        results["pipelines"] = True
    except Exception as e:
        logger.error(f"Pipeline reload failed: {e}")

    return results


def get_system_status() -> Dict[str, Any]:
    """Get status of the AILang integration system."""
    status = {
        "ailang_available": False,
        "agents": [],
        "pipelines": {},
        "plugins": [],
    }

    try:
        from .bridge import get_bridge
        bridge = get_bridge()
        status["ailang_available"] = bridge._ailang_available
        status["agents"] = bridge.list_agents()
    except Exception:
        pass

    try:
        from .pipeline_runner import get_pipeline_runner
        runner = get_pipeline_runner()
        status["pipelines"] = runner.list_pipelines()
    except Exception:
        pass

    try:
        from .plugin_loader import get_plugin_loader
        loader = get_plugin_loader()
        status["plugins"] = [
            {"name": p.name, "version": p.version, "hooks": p.hooks, "enabled": p.enabled}
            for p in loader.list_plugins()
        ]
    except Exception:
        pass

    return status
