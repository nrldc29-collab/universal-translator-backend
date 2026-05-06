from dataclasses import dataclass
from typing import Optional

from llm import PassthroughContextLayer
from speech import WhisperSpeechToText
from translation import MarianTranslator
from tts import PiperTextToSpeech
from backend.config import get_whisper_compute_type, get_whisper_device, get_whisper_model_size


@dataclass
class TranslationResult:
    source_text: str
    improved_text: str
    translated_text: str
    audio_output_path: Optional[str]


class UniversalTranslatorPipeline:
    def __init__(
        self,
        stt: WhisperSpeechToText | None = None,
        translator: MarianTranslator | None = None,
        tts: PiperTextToSpeech | None = None,
        context_layer: PassthroughContextLayer | None = None,
    ):
        self.stt = stt or WhisperSpeechToText(
            model_size=get_whisper_model_size(),
            device=get_whisper_device(),
            compute_type=get_whisper_compute_type(),
        )
        self.translator = translator or MarianTranslator()
        self.tts = tts or PiperTextToSpeech()
        self.context_layer = context_layer or PassthroughContextLayer()

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
            audio_output_path = self.tts.synthesize(translated_text, output_audio_path)

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
