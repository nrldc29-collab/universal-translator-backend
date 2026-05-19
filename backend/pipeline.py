from dataclasses import dataclass
from typing import Optional

from llm import PassthroughContextLayer
from translation import HybridTranslator, LightweightTranslator, MarianTranslator
from tts import PiperTextToSpeech
from backend.config import get_translation_backend
from backend.stt_bridge import STTBridge


@dataclass
class TranslationResult:
    source_text: str
    improved_text: str
    translated_text: str
    audio_output_path: Optional[str]


class AnaiTranslatorPipeline:
    def __init__(
        self,
        stt: object | None = None,
        translator: HybridTranslator | MarianTranslator | LightweightTranslator | None = None,
        tts: PiperTextToSpeech | None = None,
        context_layer: PassthroughContextLayer | None = None,
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

    def preload(self) -> dict:
        return {
            "stt": self.stt.preload(),
            "tts": self.tts.preload(),
        }

    def translate_text(
        self,
        text: str,
        source_language: str = "en",
        target_language: str = "es",
        tone: str | None = None,
        synthesize_audio: bool = False,
        output_audio_path: str = "models/output.wav",
    ) -> TranslationResult:
        if not text.strip():
            return TranslationResult(
                source_text=text,
                improved_text="",
                translated_text="",
                audio_output_path=None,
            )

        improved_text = self.context_layer.improve(text, source_language, target_language, tone)
        translated_text = self.translator.translate(improved_text, source_language, target_language)
        audio_output_path = None

        if synthesize_audio:
            audio_output_path = self.tts.synthesize(translated_text, output_audio_path, language=target_language)

        return TranslationResult(
            source_text=text,
            improved_text=improved_text,
            translated_text=translated_text,
            audio_output_path=audio_output_path,
        )

    def translate_audio(
        self,
        audio_path: str,
        source_language: str = "en",
        target_language: str = "es",
        tone: str | None = None,
        synthesize_audio: bool = True,
        output_audio_path: str = "models/output.wav",
    ) -> TranslationResult:
        source_text = self.stt.transcribe(audio_path, source_language)
        return self.translate_text(
            source_text,
            source_language=source_language,
            target_language=target_language,
            tone=tone,
            synthesize_audio=synthesize_audio,
            output_audio_path=output_audio_path,
        )
