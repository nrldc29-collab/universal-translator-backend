"""AILang Pipeline Manager - orchestrates AILang agents for advanced translation features."""

import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class AILangContext:
    """Context shared across AILang agents during translation."""
    session_id: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    speaker_registry: Dict[str, Any] = field(default_factory=dict)
    current_speaker: Optional[str] = None
    domain: str = "general"
    formality: str = "neutral"
    urgency: str = "normal"
    dialect_preference: str = ""
    glossary: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0


class AILangPipelineManager:
    """Manages AILang agent execution for advanced translation features."""
    
    def __init__(self):
        self._bridge = None
        self._enabled = True
        self._context_cache: Dict[str, AILangContext] = {}
        
    def _get_bridge(self):
        """Lazy load AILang bridge."""
        if self._bridge is None:
            try:
                from ailang_integration.runtime.bridge import get_bridge
                self._bridge = get_bridge()
                logger.info("AILang bridge loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load AILang bridge: {e}")
                self._enabled = False
        return self._bridge
    
    def get_or_create_context(self, session_id: str) -> AILangContext:
        """Get or create context for a session."""
        if session_id not in self._context_cache:
            self._context_cache[session_id] = AILangContext(session_id=session_id)
        return self._context_cache[session_id]
    
    def clear_context(self, session_id: str) -> None:
        """Clear context for a session."""
        if session_id in self._context_cache:
            del self._context_cache[session_id]
    
    def analyze_text(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run TranslationBrain analysis for domain, formality, urgency, model selection."""
        if not self._enabled:
            return {"domain": "general", "formality": "neutral", "urgency": "normal", "model": "fast", "instructions": [], "require_confirmation": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("TranslationBrain")
            if agent:
                result = agent.call("analyze", text, source_lang, target_lang, {"urgency": context.urgency, "speaker": context.current_speaker, "turn_count": len(context.conversation_history)})
                # Update context with analysis results
                context.domain = result.get("domain", "general")
                context.formality = result.get("formality", "neutral")
                context.urgency = result.get("urgency", "normal")
                return result
        except Exception as e:
            logger.error(f"TranslationBrain analysis failed: {e}", exc_info=True)
        
        return {"domain": "general", "formality": "neutral", "urgency": "normal", "model": "fast", "instructions": [], "require_confirmation": False}
    
    def process_context_memory(self, text: str, source_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run ContextMemoryAgent for pronoun resolution and entity tracking."""
        if not self._enabled:
            return {"resolved_text": text, "original_text": text, "resolution_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("ContextMemoryAgent")
            if agent:
                result = agent.call("process", text, context.current_speaker or "unknown", source_lang, context.conversation_history, context.speaker_registry)
                # Update context with new registry
                context.speaker_registry = result.get("speaker_registry", context.speaker_registry)
                return result
        except Exception as e:
            logger.error(f"ContextMemoryAgent failed: {e}", exc_info=True)
        
        return {"resolved_text": text, "original_text": text, "resolution_applied": False}
    
    def process_speaker_profile(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run SpeakerProfilerAgent for voice profiling and style adaptation."""
        if not self._enabled or not context.current_speaker:
            return {"style_guide": [], "profile": {}}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("SpeakerProfilerAgent")
            if agent:
                result = agent.call("get_style_instructions", context.current_speaker, text, source_lang, target_lang, context.speaker_registry)
                # Update context with new registry
                context.speaker_registry = result.get("updated_registry", context.speaker_registry)
                return result
        except Exception as e:
            logger.error(f"SpeakerProfilerAgent failed: {e}", exc_info=True)
        
        return {"style_guide": [], "profile": {}}
    
    def process_dialect_adaptation(self, source_text: str, base_translation: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run DialectAdapterAgent for regional dialect adaptation."""
        if not self._enabled or not context.dialect_preference:
            return {"final_translation": base_translation, "adaptation_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("DialectAdapterAgent")
            if agent:
                result = agent.call("process", source_text, base_translation, source_lang, target_lang, context.dialect_preference)
                return result
        except Exception as e:
            logger.error(f"DialectAdapterAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "adaptation_applied": False}
    
    def process_glossary_injection(self, text: str, base_translation: str, source_lang: str, target_lang: str, context: AILangContext, instructions: List[str]) -> Dict[str, Any]:
        """Run GlossaryInjectorAgent for custom terminology injection."""
        if not self._enabled or not context.glossary:
            return {"final_translation": base_translation, "glossary_applied": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("GlossaryInjectorAgent")
            if agent:
                result = agent.call("process", text, base_translation, source_lang, target_lang, context.domain, context.glossary, instructions)
                return result
        except Exception as e:
            logger.error(f"GlossaryInjectorAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "glossary_applied": False}
    
    def process_ambiguity_resolution(self, text: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run AmbiguityResolverAgent for phrase ambiguity detection."""
        if not self._enabled:
            return {"has_ambiguities": False, "resolved_text": text, "needs_human_review": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("AmbiguityResolverAgent")
            if agent:
                history_summary = "\n".join([f"{t.get('speaker', 'unknown')}: {t.get('text', '')}" for t in context.conversation_history[-6:]])
                result = agent.call("process", text, source_lang, target_lang, context.domain, history_summary or "")
                # Check if result is valid (not a JSON stub)
                if isinstance(result, dict) and "has_ambiguities" in result:
                    return result
        except Exception as e:
            logger.error(f"AmbiguityResolverAgent failed: {e}", exc_info=True)
        
        return {"has_ambiguities": False, "resolved_text": text, "needs_human_review": False}
    
    def process_confidence_fallback(self, text: str, base_translation: str, confidence: float, source_lang: str, target_lang: str, context: AILangContext, instructions: List[str]) -> Dict[str, Any]:
        """Run ConfidenceFallbackAgent for low-confidence translation escalation."""
        if not self._enabled or confidence >= 0.65:
            return {"final_translation": base_translation, "escalated": False, "tier": "high"}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("ConfidenceFallbackAgent")
            if agent:
                result = agent.call("process", text, base_translation, confidence, source_lang, target_lang, context.domain, instructions)
                return result
        except Exception as e:
            logger.error(f"ConfidenceFallbackAgent failed: {e}", exc_info=True)
        
        return {"final_translation": base_translation, "escalated": False, "tier": "high"}
    
    def process_back_translation(self, original: str, translated: str, source_lang: str, target_lang: str, context: AILangContext) -> Dict[str, Any]:
        """Run BackTranslatorAgent for translation verification."""
        if not self._enabled:
            return {"verified": True, "final_translation": translated, "improved": False}
        
        try:
            bridge = self._get_bridge()
            agent = bridge.get_agent("BackTranslatorAgent")
            if agent:
                result = agent.call("verify", original, translated, source_lang, target_lang, context.domain)
                # Check if result is valid (not a JSON stub)
                if isinstance(result, dict) and "verified" in result:
                    return result
        except Exception as e:
            logger.error(f"BackTranslatorAgent failed: {e}", exc_info=True)
        
        return {"verified": True, "final_translation": translated, "improved": False}
    
    def add_conversation_turn(self, session_id: str, speaker: str, text: str, translated: str) -> None:
        """Add a conversation turn to the history."""
        context = self.get_or_create_context(session_id)
        context.current_speaker = speaker
        context.conversation_history.append({
            "speaker": speaker,
            "text": text,
            "translated": translated
        })
        # Keep only last 20 turns
        if len(context.conversation_history) > 20:
            context.conversation_history = context.conversation_history[-20:]
    
    def set_glossary(self, session_id: str, glossary: List[Dict[str, Any]]) -> None:
        """Set custom glossary for a session."""
        context = self.get_or_create_context(session_id)
        context.glossary = glossary
    
    def set_dialect_preference(self, session_id: str, dialect: str) -> None:
        """Set dialect preference for a session."""
        context = self.get_or_create_context(session_id)
        context.dialect_preference = dialect
    
    def set_speaker(self, session_id: str, speaker: str) -> None:
        """Set current speaker for a session."""
        context = self.get_or_create_context(session_id)
        context.current_speaker = speaker
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get pipeline statistics."""
        bridge = self._get_bridge()
        if bridge:
            return {
                "enabled": self._enabled,
                "active_sessions": len(self._context_cache),
                "bridge_stats": bridge.get_stats()
            }
        return {
            "enabled": self._enabled,
            "active_sessions": len(self._context_cache),
            "bridge_stats": None
        }


# Global pipeline manager instance
_ailang_pipeline: Optional[AILangPipelineManager] = None


def get_ailang_pipeline() -> AILangPipelineManager:
    """Get the global AILang pipeline manager instance."""
    global _ailang_pipeline
    if _ailang_pipeline is None:
        _ailang_pipeline = AILangPipelineManager()
    return _ailang_pipeline
