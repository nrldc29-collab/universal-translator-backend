from dataclasses import dataclass
from typing import Optional

from llm import PassthroughContextLayer
from translation import HybridTranslator, LightweightTranslator, MarianTranslator
from tts import PiperTextToSpeech
from backend.config import get_translation_backend
from backend.stt_bridge import STTBridge
from backend.ailang_pipeline import get_ailang_pipeline, AILangContext
from backend.communication_brain import detect_domains
from backend.glossary import (
    finalize_translation,
    prepare_for_translation,
    set_session_glossary,
)


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

    def preload(self) -> dict:
        result = {
            "stt": self.stt.preload(),
            "tts": self.tts.preload(),
        }
        try:
            self.translate_local("hello", "en", "es")
            result["translation"] = "warmed"
        except (RuntimeError, OSError, ValueError) as exc:
            result["translation"] = f"warmup_failed:{exc.__class__.__name__}"
        return result

    def translate_local(
        self,
        text: str,
        source_language: str,
        target_language: str,
        *,
        session_id: str | None = None,
        original_source_text: str | None = None,
        translator: object | None = None,
    ) -> str:
        """Translate through glossary protection and the configured local translator."""
        if not text.strip():
            return ""
        sid = session_id or self.session_id
        original = (original_source_text or text).strip()
        active_translator = translator or self.translator
        domains = detect_domains(original)
        strict_medical = "medical" in (domains.get("high_stakes") or [])
        prepared_text, glossary_meta = prepare_for_translation(text, strict_medical=strict_medical)
        raw = active_translator.translate(prepared_text, source_language, target_language)
        translated, _meta = finalize_translation(
            original,
            raw,
            session_id=sid,
            source_lang=source_language,
            target_lang=target_language,
            strict_medical=strict_medical,
            metadata={**glossary_meta, "domains": domains},
        )
        return translated

    def translate_text(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = "es",
        tone: str | None = None,
        synthesize_audio: bool = False,
        output_audio_path: str = "models/output.wav",
        speaker: str | None = None,
        confidence: float = 0.0,
    ) -> TranslationResult:
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
                working_text = context_result["resolved_text"]
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

        domains = detect_domains(text)
        translated_text = self.translate_local(
            improved_text,
            source_language,
            target_language,
            session_id=self.session_id,
            original_source_text=text,
        )
        if domains.get("high_stakes") or domains.get("matches"):
            ailang_metadata = ailang_metadata or {}
            ailang_metadata["domains"] = domains
            ailang_metadata["glossary"] = {"applied_via": "translate_local"}
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

            # 7. Glossary injection (AILang layer — local glossary already applied above)
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

    def translate_text_with(
        self,
        translator,
        text: str,
        source_language: str = "en",
        target_language: str = "es",
        tone: str | None = None,
        synthesize_audio: bool = False,
        output_audio_path: str = "models/output.wav",
        speaker: str | None = None,
        confidence: float = 0.0,
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
                working_text = context_result["resolved_text"]
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

        domains = detect_domains(text)
        translated_text = self.translate_local(
            improved_text,
            source_language,
            target_language,
            session_id=self.session_id,
            original_source_text=text,
            translator=translator,
        )
        if domains.get("high_stakes") or domains.get("matches"):
            ailang_metadata["domains"] = domains
            ailang_metadata["glossary"] = {"applied_via": "translate_local"}

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

    def translate_audio(
        self,
        audio_path: str,
        source_language: str = "en",
        target_language: str = "es",
        tone: str | None = None,
        synthesize_audio: bool = True,
        output_audio_path: str = "models/output.wav",
        speaker: str | None = None,
        confidence: float = 0.0,
    ) -> TranslationResult:
        source_text = self.stt.transcribe(audio_path, source_language)
        return self.translate_text(
            source_text,
            source_language=source_language,
            target_language=target_language,
            tone=tone,
            synthesize_audio=synthesize_audio,
            output_audio_path=output_audio_path,
            speaker=speaker,
            confidence=confidence,
        )
    
    def set_glossary(self, glossary: list) -> None:
        """Set custom glossary for the current session."""
        set_session_glossary(self.session_id, glossary)
        if self.ailang_pipeline:
            self.ailang_pipeline.set_glossary(self.session_id, glossary)
    
    def set_dialect_preference(self, dialect: str) -> None:
        """Set dialect preference for the current session."""
        if self.ailang_pipeline:
            self.ailang_pipeline.set_dialect_preference(self.session_id, dialect)
    
    def set_speaker(self, speaker: str) -> None:
        """Set current speaker for the current session."""
        if self.ailang_pipeline:
            self.ailang_pipeline.set_speaker(self.session_id, speaker)
    
    def clear_session_context(self) -> None:
        """Clear context for the current session."""
        if self.ailang_pipeline:
            self.ailang_pipeline.clear_context(self.session_id)
    
    def get_ailang_statistics(self) -> dict:
        """Get AILang pipeline statistics."""
        if self.ailang_pipeline:
            return self.ailang_pipeline.get_statistics()
        return {"enabled": False, "active_sessions": 0, "bridge_stats": None}
