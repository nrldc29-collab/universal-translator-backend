from dataclasses import dataclass
from typing import Optional
import json
import re
import os

from llm import PassthroughContextLayer
from translation import HybridTranslator, LightweightTranslator, MarianTranslator
from tts import PiperTextToSpeech
from backend.config import get_translation_backend, _to_int
from backend.stt_bridge import STTBridge
from backend.ailang_pipeline import get_ailang_pipeline, AILangContext

# Advanced optimization modules
try:
    from backend.predictive_cache import PredictiveCache
    PREDICTIVE_CACHE_AVAILABLE = True
except ImportError:
    PREDICTIVE_CACHE_AVAILABLE = False


def _is_structured_fallback(text: str) -> bool:
    """Check if text is a JSON/structured fallback from the AI stub rather than natural language."""
    stripped = text.strip()
    if not stripped:
        return True
    # Starts with JSON object or array markers
    if stripped.startswith(("{", "[")):
        try:
            json.loads(stripped)
            return True
        except (json.JSONDecodeError, ValueError):
            pass
    # Starts with AI stub markers like [AI: or [AI_ERROR:
    if stripped.startswith("[AI:") or stripped.startswith("[AI_ERROR:"):
        return True
    # Very long text that's mostly structured data (prompts echoing back)
    if len(stripped) > 500 and stripped.count(":") > 10:
        return True
    return False


@dataclass
class TranslationResult:
    source_text: str
    improved_text: str
    translated_text: str
    audio_output_path: Optional[str]
    ailang_metadata: Optional[dict] = None


class AnaiTranslatorPipeline:
    def __init__(
        self,
        stt: object | None = None,
        translator: HybridTranslator | MarianTranslator | LightweightTranslator | None = None,
        tts: PiperTextToSpeech | None = None,
        context_layer: PassthroughContextLayer | None = None,
        session_id: str = "default",
        enable_ailang: bool = True,
        enable_predictive_cache: bool = True,
    ):
        if stt is not None:
            self.stt = stt
        else:
            self.stt = STTBridge()
        translation_backend = get_translation_backend()
        if translator:
            self.translator = translator
        elif translation_backend == "lightweight":
            self.translator = LightweightTranslator()
        elif translation_backend == "hybrid":
            self.translator = HybridTranslator()
        else:
            self.translator = MarianTranslator()
        self.tts = tts or PiperTextToSpeech()
        self.context_layer = context_layer or PassthroughContextLayer()
        self.session_id = session_id
        self.enable_ailang = enable_ailang
        self.ailang_pipeline = get_ailang_pipeline() if enable_ailang else None
        
        # Initialize predictive cache if available and enabled
        self.enable_predictive_cache = enable_predictive_cache and PREDICTIVE_CACHE_AVAILABLE
        self.predictive_cache = None
        # Tolerant int parsing: a bad PREDICTIVE_CACHE_* env value falls back to
        # the default instead of crashing pipeline (and thus server) startup.
        if self.enable_predictive_cache:
            self.predictive_cache = PredictiveCache(
                max_size=_to_int("PREDICTIVE_CACHE_SIZE", 1000, minimum=1),
                ttl_seconds=_to_int("PREDICTIVE_CACHE_TTL", 3600, minimum=1),
            )
        # Cache hit/miss counters (initialized here so stats never depend on
        # whether translate_text has run yet).
        self._cache_hits = 0
        self._cache_misses = 0

    def preload(self) -> dict:
        result = {
            "stt": self.stt.preload(),
            "tts": self.tts.preload(),
        }
        
        # Warm predictive cache with common phrases
        if self.enable_predictive_cache and self.predictive_cache:
            cache_stats = self.predictive_cache.get_statistics()
            result["predictive_cache"] = cache_stats
        
        return result
    
    def get_cache_statistics(self) -> dict:
        """Get cache hit/miss statistics."""
        if self.enable_predictive_cache and self.predictive_cache:
            stats = self.predictive_cache.get_statistics()
            stats["hits"] = getattr(self, '_cache_hits', 0)
            stats["misses"] = getattr(self, '_cache_misses', 0)
            total = stats["hits"] + stats["misses"]
            stats["hit_rate"] = stats["hits"] / total if total > 0 else 0.0
            return stats
        return {"enabled": False, "hits": 0, "misses": 0, "hit_rate": 0.0}

    def translate_text(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = "ht",
        tone: str | None = None,
        synthesize_audio: bool = False,
        output_audio_path: str = "models/output.wav",
        output_path: str | None = None,
        speaker: str | None = None,
        confidence: float = 0.0,
        quality: bool = False,
    ) -> TranslationResult:
        if output_path is not None:
            output_audio_path = output_path
        if not text.strip():
            return TranslationResult(
                source_text=text,
                improved_text="",
                translated_text="",
                audio_output_path=None,
                ailang_metadata=None,
            )
        
        ailang_metadata = {}
        working_text = text
        
        # AILang agent pipeline
        if self.ailang_pipeline:
            context = self.ailang_pipeline.get_or_create_context(self.session_id)
            if speaker:
                context.current_speaker = speaker
            
            # 1. Domain/Formality/Urgency analysis
            analysis = self.ailang_pipeline.analyze_text(working_text, source_language, target_language, context)
            ailang_metadata["analysis"] = analysis
            
            # 2. Context memory for pronoun resolution
            context_result = self.ailang_pipeline.process_context_memory(working_text, source_language, context)
            if context_result.get("resolution_applied"):
                resolved = context_result.get("resolved_text", "")
                # Only accept the resolved text if it looks like natural language,
                # not a JSON/structured fallback from the AI stub.
                if resolved and not _is_structured_fallback(resolved):
                    working_text = resolved
                ailang_metadata["context_memory"] = context_result
            
            # 3. Speaker profiling for style adaptation
            profile_result = self.ailang_pipeline.process_speaker_profile(working_text, source_language, target_language, context)
            if profile_result.get("style_guide"):
                ailang_metadata["speaker_profile"] = profile_result
            
            # 4. Ambiguity detection
            ambiguity_result = self.ailang_pipeline.process_ambiguity_resolution(working_text, source_language, target_language, context)
            ailang_metadata["ambiguity"] = ambiguity_result
            
            # Apply context layer improvements
            improved_text = self.context_layer.improve(working_text, source_language, target_language, tone)
        else:
            improved_text = self.context_layer.improve(text, source_language, target_language, tone)
        
        # Base translation with predictive cache
        translated_text = None
        cache_hit = False
        
        if self.enable_predictive_cache and self.predictive_cache:
            # Check cache first
            cached = self.predictive_cache.get_translation(
                improved_text,
                source_language,
                target_language,
                context={"session_id": self.session_id, "speaker": speaker},
            )
            if cached:
                translated_text = cached
                cache_hit = True
                ailang_metadata["cache_hit"] = True
                # Track cache hit
                if hasattr(self, '_cache_hits'):
                    self._cache_hits += 1
                else:
                    self._cache_hits = 1
            else:
                # Track cache miss
                if hasattr(self, '_cache_misses'):
                    self._cache_misses += 1
                else:
                    self._cache_misses = 1
        
        if not translated_text:
            # Perform translation if not cached
            translated_text = self.translator.translate(
                improved_text, source_language, target_language, quality=quality,
            )
            
            # Cache the result
            if self.enable_predictive_cache and self.predictive_cache:
                self.predictive_cache.set_translation(
                    improved_text,
                    translated_text,
                    source_language,
                    target_language,
                    context={"session_id": self.session_id, "speaker": speaker},
                    priority=2 if len(improved_text.split()) <= 5 else 1,  # Higher priority for short common phrases
                )
        
        # AILang post-translation pipeline
        if self.ailang_pipeline:
            context = self.ailang_pipeline.get_or_create_context(self.session_id)
            
            # 5. Confidence-based fallback
            if confidence > 0:
                confidence_result = self.ailang_pipeline.process_confidence_fallback(
                    improved_text, translated_text, confidence, source_language, target_language, 
                    context, analysis.get("instructions", [])
                )
                if confidence_result.get("escalated"):
                    translated_text = confidence_result["final_translation"]
                    ailang_metadata["confidence_fallback"] = confidence_result
            
            # 6. Dialect adaptation
            dialect_result = self.ailang_pipeline.process_dialect_adaptation(
                improved_text, translated_text, source_language, target_language, context
            )
            if dialect_result.get("adaptation_applied"):
                translated_text = dialect_result["final_translation"]
                ailang_metadata["dialect_adaptation"] = dialect_result
            
            # 7. Glossary injection
            glossary_result = self.ailang_pipeline.process_glossary_injection(
                improved_text, translated_text, source_language, target_language, 
                context, analysis.get("instructions", [])
            )
            if glossary_result.get("glossary_applied"):
                translated_text = glossary_result["final_translation"]
                ailang_metadata["glossary_injection"] = glossary_result
            
            # 8. Back-translation verification
            back_translation_result = self.ailang_pipeline.process_back_translation(
                improved_text, translated_text, source_language, target_language, context
            )
            if back_translation_result.get("improved"):
                translated_text = back_translation_result["final_translation"]
                ailang_metadata["back_translation"] = back_translation_result
            
            # Add conversation turn to history
            self.ailang_pipeline.add_conversation_turn(
                self.session_id, speaker or "unknown", text, translated_text
            )
        
        audio_output_path = None
        if synthesize_audio:
            # Apply emotion-aware TTS configuration if AILang is enabled
            emotion_config = None
            if self.ailang_pipeline:
                context = self.ailang_pipeline.get_or_create_context(self.session_id)
                emotion_result = self.ailang_pipeline.process_emotion_tts(translated_text, target_language, context)
                emotion_config = emotion_result.get("tts_config")
                ailang_metadata["emotion_tts"] = emotion_result
            
            # Emotion-aware TTS: speaking rate / pitch / volume carried into synthesis.
            audio_output_path = self.tts.synthesize(
                translated_text, output_audio_path, language=target_language, emotion_config=emotion_config
            )

        return TranslationResult(
            source_text=text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=audio_output_path,
            ailang_metadata=ailang_metadata if ailang_metadata else None,
        )

    def translate_text_with(
        self,
        translator,
        text: str,
        source_language: str = "en",
        target_language: str = "ht",
        tone: str | None = None,
        synthesize_audio: bool = False,
        output_audio_path: str = "models/output.wav",
        speaker: str | None = None,
        confidence: float = 0.0,
        quality: bool = False,
    ) -> TranslationResult:
        """Run translate_text using a caller-supplied translator instead of self.translator."""
        if not text.strip():
            return TranslationResult(
                source_text=text,
                improved_text="",
                translated_text="",
                audio_output_path=None,
                ailang_metadata=None,
            )
        
        ailang_metadata = {}
        working_text = text
        
        # AILang agent pipeline
        if self.ailang_pipeline:
            context = self.ailang_pipeline.get_or_create_context(self.session_id)
            if speaker:
                context.current_speaker = speaker
            
            # 1. Domain/Formality/Urgency analysis
            analysis = self.ailang_pipeline.analyze_text(working_text, source_language, target_language, context)
            ailang_metadata["analysis"] = analysis
            
            # 2. Context memory for pronoun resolution
            context_result = self.ailang_pipeline.process_context_memory(working_text, source_language, context)
            if context_result.get("resolution_applied"):
                resolved = context_result.get("resolved_text", "")
                # Only accept the resolved text if it looks like natural language,
                # not a JSON/structured fallback from the AI stub.
                if resolved and not _is_structured_fallback(resolved):
                    working_text = resolved
                ailang_metadata["context_memory"] = context_result
            
            # 3. Speaker profiling for style adaptation
            profile_result = self.ailang_pipeline.process_speaker_profile(working_text, source_language, target_language, context)
            if profile_result.get("style_guide"):
                ailang_metadata["speaker_profile"] = profile_result
            
            # 4. Ambiguity detection
            ambiguity_result = self.ailang_pipeline.process_ambiguity_resolution(working_text, source_language, target_language, context)
            ailang_metadata["ambiguity"] = ambiguity_result
            
            improved_text = self.context_layer.improve(working_text, source_language, target_language, tone)
        else:
            improved_text = self.context_layer.improve(text, source_language, target_language, tone)
        
        from translation.hybrid_translator import HybridTranslator
        from translation.marian_translator import MarianTranslator

        if quality and isinstance(translator, (MarianTranslator, HybridTranslator)):
            translated_text = translator.translate(
                improved_text, source_language, target_language, quality=True,
            )
        else:
            translated_text = translator.translate(improved_text, source_language, target_language)
        
        # AILang post-translation pipeline
        if self.ailang_pipeline:
            context = self.ailang_pipeline.get_or_create_context(self.session_id)
            
            # 5. Confidence-based fallback
            if confidence > 0:
                confidence_result = self.ailang_pipeline.process_confidence_fallback(
                    improved_text, translated_text, confidence, source_language, target_language, 
                    context, analysis.get("instructions", []),
                )
                if confidence_result.get("escalated"):
                    translated_text = confidence_result["final_translation"]
                    ailang_metadata["confidence_fallback"] = confidence_result
            
            # 6. Dialect adaptation
            dialect_result = self.ailang_pipeline.process_dialect_adaptation(
                improved_text, translated_text, source_language, target_language, context
            )
            if dialect_result.get("adaptation_applied"):
                translated_text = dialect_result["final_translation"]
                ailang_metadata["dialect_adaptation"] = dialect_result
            
            # 7. Glossary injection
            glossary_result = self.ailang_pipeline.process_glossary_injection(
                improved_text, translated_text, source_language, target_language, 
                context, analysis.get("instructions", [])
            )
            if glossary_result.get("glossary_applied"):
                translated_text = glossary_result["final_translation"]
                ailang_metadata["glossary_injection"] = glossary_result
            
            back_translation_result = self.ailang_pipeline.process_back_translation(
                improved_text, translated_text, source_language, target_language, context
            )
            if back_translation_result.get("improved"):
                translated_text = back_translation_result["final_translation"]
                ailang_metadata["back_translation"] = back_translation_result
            
            self.ailang_pipeline.add_conversation_turn(
                self.session_id, speaker or "unknown", text, translated_text
            )
        
        audio_output_path = None
        if synthesize_audio:
            emotion_config = None
            if self.ailang_pipeline:
                context = self.ailang_pipeline.get_or_create_context(self.session_id)
                emotion_result = self.ailang_pipeline.process_emotion_tts(translated_text, target_language, context)
                emotion_config = emotion_result.get("tts_config")
                ailang_metadata["emotion_tts"] = emotion_result
            audio_output_path = self.tts.synthesize(
                translated_text, output_audio_path, language=target_language, emotion_config=emotion_config
            )
        return TranslationResult(
            source_text=text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=audio_output_path,
            ailang_metadata=ailang_metadata if ailang_metadata else None,
        )

    def translate_local(
        self,
        text: str,
        source_language: str,
        target_language: str,
        *,
        original_source_text: str | None = None,
        strict_medical: bool = True,
    ) -> str:
        from backend.glossary import finalize_translation, prepare_for_translation

        source_text = original_source_text or text
        prepared, metadata = prepare_for_translation(text, strict_medical=strict_medical)
        translated = self.translator.translate(prepared, source_language, target_language)
        final, _ = finalize_translation(
            source_text,
            translated,
            session_id=self.session_id,
            source_lang=source_language,
            target_lang=target_language,
            strict_medical=strict_medical,
            metadata=metadata,
        )
        return final

    def translate_audio(self, audio_path, source_language="en", target_language="ht", tone=None, synthesize_audio=True, output_audio_path="models/output.wav", speaker=None, confidence=0.0):
        source_text = self.stt.transcribe(audio_path, source_language)
        return self.translate_text(source_text, source_language=source_language, target_language=target_language, tone=tone, synthesize_audio=synthesize_audio, output_audio_path=output_audio_path, speaker=speaker, confidence=confidence)
    
    def set_glossary(self, glossary):
        if self.ailang_pipeline:
            self.ailang_pipeline.set_glossary(self.session_id, glossary)
    
    def set_dialect_preference(self, dialect):
        if self.ailang_pipeline:
            self.ailang_pipeline.set_dialect_preference(self.session_id, dialect)
    
    def set_speaker(self, speaker):
        if self.ailang_pipeline:
            self.ailang_pipeline.set_speaker(self.session_id, speaker)
    
    def clear_session_context(self):
        if self.ailang_pipeline:
            self.ailang_pipeline.clear_context(self.session_id)
    
    def get_ailang_statistics(self):
        if self.ailang_pipeline:
            return self.ailang_pipeline.get_statistics()
        return {"enabled": False, "active_sessions": 0, "bridge_stats": None}
