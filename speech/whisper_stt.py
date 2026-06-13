import logging
import math
import re
from dataclasses import dataclass
from pathlib import Path
from threading import BoundedSemaphore, Lock
from time import time
from typing import Optional

from backend.config import (
    get_stt_max_concurrency,
    get_stt_queue_max_depth,
    get_whisper_beam_size,
    get_whisper_cpu_threads,
    get_whisper_num_workers,
)
from speech.audio_decode import transcode_to_wav

logger = logging.getLogger(__name__)


_HAITIAN_PHONETIC_REPLACEMENTS = (
    (r"\bmu\s+en\b", "mwen"),
    (r"\bmoen\b", "mwen"),
    (r"\bmoin\b", "mwen"),
    (r"\bmouin\b", "mwen"),
    (r"\bbesuane\b", "bezwen"),
    (r"\bbezuane\b", "bezwen"),
    (r"\bbesoin\b", "bezwen"),
    (r"\byondokte\b", "yon dokte"),
    (r"\byandokte\b", "yon dokte"),
    (r"\bdok\s+te\b", "dokte"),
    (r"\bempil\b", "anpil"),
    (r"\bpwedu\b", "pou ed ou"),
    (r"\bpoedu\b", "pou ed ou"),
    (r"\bpu(?:e|\u00e9)du\b", "pou ed ou"),
    (r"\bpwe\s+dhu\b", "pou ed ou"),
    (r"\bpia\b", "pa"),
    (r"\bcompran\b", "konprann"),
    (r"\bkontran\b", "konprann"),
    (r"\bpa\s+konprann\b", "pa konprann"),
    (r"\bsal\s+ijan\b", "sal ijans"),
    (r"\bbezwen\s+ede\b", "bezwen èd"),
    (r"\bmap\s+byen\b", "m ap byen"),
    (r"\bmwen\s+pa\s+konprann\b", "mwen pa konprann"),
    (r"\bkijan\s+ou\s+ye\b", "kijan ou ye"),
    (r"\bmesi\s+anpil\b", "mèsi anpil"),
    (r"\bmesianpil\b", "mèsi anpil"),
    (r"\bbezwen\s+ed\b", "bezwen èd"),
    (r"\bgen\s+doulè\b", "gen doulè"),
    (r"\bgendoule\b", "gen doulè"),
    (r"\blafiev\b", "lafyèv"),
    (r"\bla\s+fiev\b", "lafyèv"),
    (r"\byon\s+dokte\b", "yon dokte"),
    (r"\byondokte\b", "yon dokte"),
    (r"\brele\s+anbilans\b", "rele yon anbilans"),
    (r"\breleanbilans\b", "rele yon anbilans"),
    (r"\btanpri\s+pale\b", "tanpri pale"),
    (r"\beske\s+ou\b", "èske ou"),
    (r"\beskeou\b", "èske ou"),
    (r"\bsal\s+ijans\b", "sal ijans"),
    (r"\bsalijans\b", "sal ijans"),
    (r"\bkote\s+lopital\b", "kote lopital"),
    (r"\bkotelopital\b", "kote lopital"),
)


@dataclass
class TranscriptionResult:
    text: str
    confidence: float | None = None


def build_initial_prompt(language: str | None, live_text: str | None = None) -> str | None:
    """Merge language vocabulary seed with live partial text for better decoding."""
    return build_conversation_prompt(language, live_text=live_text)


def build_conversation_prompt(
    language: str | None,
    live_text: str | None = None,
    recent_turns: list[str] | None = None,
) -> str | None:
    """Merge vocabulary seed, recent conversation, and live partial text for STT."""
    lang = str(language or "").lower().split("-")[0]
    seed = _LANGUAGE_INITIAL_PROMPTS.get(lang, "")[:120]
    turns = " ".join((t or "").strip() for t in (recent_turns or [])[-3:] if (t or "").strip())[:120]
    live = (live_text or "").strip()[:120]
    merged = " ".join(part for part in (seed, turns, live) if part).strip()
    return merged[:240] or None


def _vad_options_for_environment(environment: str | None) -> dict:
    env = str(environment or "").lower()
    if env in {"restaurant", "street", "crowded", "noisy"}:
        return {"min_silence_duration_ms": 450, "speech_pad_ms": 100, "no_speech_threshold": 0.62}
    if env in {"quiet", "office"}:
        return {"min_silence_duration_ms": 250, "speech_pad_ms": 150, "no_speech_threshold": 0.50}
    return {"min_silence_duration_ms": 300, "speech_pad_ms": 120, "no_speech_threshold": 0.55}


def _segment_confidence(segment) -> float:
    logprob = getattr(segment, "avg_logprob", None)
    no_speech = float(getattr(segment, "no_speech_prob", 0.0) or 0.0)
    if logprob is not None:
        acoustic = min(1.0, max(0.05, math.exp(float(logprob))))
    else:
        acoustic = 0.55
    return max(0.0, min(1.0, acoustic * (1.0 - min(0.85, no_speech))))


_LANGUAGE_INITIAL_PROMPTS = {
    "ht": "Bonjou, mwen bezwen èd. Mèsi anpil. Kote dokte a? Mwen pa konprann.",
    "es": "Hola, gracias. ¿Dónde está el baño? Necesito ayuda, por favor.",
    "fr": "Bonjour, merci. Où sont les toilettes? J'ai besoin d'aide, s'il vous plaît.",
    "pt": "Olá, obrigado. Onde fica o banheiro? Preciso de ajuda, por favor.",
    "en": "Hello, thank you. Where is the bathroom? I need help, please.",
    "de": "Hallo, danke. Wo ist die Toilette? Ich brauche Hilfe, bitte.",
    "it": "Ciao, grazie. Dov'è il bagno? Ho bisogno di aiuto, per favore.",
    "nl": "Hallo, dank je. Waar is het toilet? Ik heb hulp nodig, alsjeblieft.",
    "ru": "Привет, спасибо. Где туалет? Мне нужна помощь, пожалуйста.",
    "zh": "你好，谢谢。洗手间在哪里？我需要帮助。",
    "ja": "こんにちは、ありがとう。トイレはどこですか？助けが必要です。",
    "ko": "안녕하세요, 감사합니다. 화장실이 어디에 있나요? 도움이 필요합니다.",
    "ar": "مرحبا، شكرا. أين الحمام؟ أحتاج مساعدة من فضلك.",
    "hi": "नमस्ते, धन्यवाद। शौचालय कहाँ है? मुझे मदद चाहिए।",
}

_SPANISH_PHONETIC_REPLACEMENTS = (
    (r"\bgrasyas\b", "gracias"),
    (r"\bpor\s+fabor\b", "por favor"),
    (r"\bnecesito\s+ayuda\b", "necesito ayuda"),
    (r"\bdonde\s+esta\b", "dónde está"),
    (r"\bel\s+bano\b", "el baño"),
)

_FRENCH_PHONETIC_REPLACEMENTS = (
    (r"\bbonjour\b", "bonjour"),
    (r"\bmerci\s+beaucoup\b", "merci beaucoup"),
    (r"\bou\s+est\b", "où est"),
    (r"\bj'ai\s+besoin\b", "j'ai besoin"),
    (r"\bsil\s+vous\s+plait\b", "s'il vous plaît"),
)

_PORTUGUESE_PHONETIC_REPLACEMENTS = (
    (r"\bobrigado\b", "obrigado"),
    (r"\bobrigada\b", "obrigada"),
    (r"\bpor\s+favor\b", "por favor"),
    (r"\bonde\s+fica\b", "onde fica"),
    (r"\bpreciso\s+de\s+ajuda\b", "preciso de ajuda"),
)

_GERMAN_PHONETIC_REPLACEMENTS = (
    (r"\bdanke\s+schon\b", "danke schön"),
    (r"\bwo\s+ist\b", "wo ist"),
    (r"\bich\s+brauche\s+hilfe\b", "ich brauche hilfe"),
    (r"\bbitte\b", "bitte"),
)

_ITALIAN_PHONETIC_REPLACEMENTS = (
    (r"\bgrazie\s+mille\b", "grazie mille"),
    (r"\bper\s+favore\b", "per favore"),
    (r"\bdov\s+e\b", "dov'è"),
    (r"\bho\s+bisogno\b", "ho bisogno"),
)

_DUTCH_PHONETIC_REPLACEMENTS = (
    (r"\bdank\s+je\b", "dank je"),
    (r"\bwaar\s+is\b", "waar is"),
    (r"\bik\s+heb\s+hulp\s+nodig\b", "ik heb hulp nodig"),
    (r"\balsjeblieft\b", "alsjeblieft"),
)

_RUSSIAN_PHONETIC_REPLACEMENTS = (
    (r"пожалуста", "пожалуйста"),
    (r"извени\b", "извините"),
    (r"спасибо", "спасибо"),
    (r"где\s+туалет", "где туалет"),
)

_ARABIC_PHONETIC_REPLACEMENTS = (
    (r"شكرا\b", "شكراً"),
    (r"\bاين\b", "أين"),
    (r"من\s+فضلك", "من فضلك"),
    (r"أحتاج\s+مساعدة", "أحتاج مساعدة"),
)

_HINDI_PHONETIC_REPLACEMENTS = (
    (r"धन्यवाद", "धन्यवाद"),
    (r"शौचालय", "शौचालय"),
    (r"मदद\s+चाहिए", "मदद चाहिए"),
)

_CHINESE_PHONETIC_REPLACEMENTS = (
    (r"在那里", "在哪里"),
    (r"洗手间", "洗手间"),
    (r"需要帮助", "需要帮助"),
)

_JAPANESE_PHONETIC_REPLACEMENTS = (
    (r"ありがと\b", "ありがとう"),
    (r"トイレ", "トイレ"),
    (r"助けて", "助けて"),
)

_KOREAN_PHONETIC_REPLACEMENTS = (
    (r"감사해\b", "감사합니다"),
    (r"화장실", "화장실"),
    (r"도움이\s+필요", "도움이 필요"),
)


def normalize_transcript(text: str, source_language=None) -> str:
    """Correct recurring phonetic decoding errors for supported languages."""
    result = (text or "").strip()
    language = str(source_language or "").lower().split("-")[0]
    if not result:
        return ""

    if language == "ht":
        for pattern, replacement in _HAITIAN_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "es":
        for pattern, replacement in _SPANISH_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "fr":
        for pattern, replacement in _FRENCH_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "pt":
        for pattern, replacement in _PORTUGUESE_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "de":
        for pattern, replacement in _GERMAN_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "it":
        for pattern, replacement in _ITALIAN_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "nl":
        for pattern, replacement in _DUTCH_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "ru":
        for pattern, replacement in _RUSSIAN_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "ar":
        for pattern, replacement in _ARABIC_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "hi":
        for pattern, replacement in _HINDI_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "zh":
        for pattern, replacement in _CHINESE_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "ja":
        for pattern, replacement in _JAPANESE_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    elif language == "ko":
        for pattern, replacement in _KOREAN_PHONETIC_REPLACEMENTS:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
    result = " ".join(result.split())
    if language == "ht" and text:
        original = text.strip()
        if original and original[0].isupper() and result and result[0].islower():
            result = result[0].upper() + result[1:]
    return result


class WhisperSpeechToText:
    def __init__(self, model_size: str = "base", device: str = "cpu", compute_type: str = "int8"):
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None
        self._model_lock = Lock()
        self._semaphore = BoundedSemaphore(get_stt_max_concurrency())
        self._lock = Lock()
        self._queue_depth = 0
        self._active = 0
        self._rejected = 0
        self._wait_times = []

    def _load_model(self):
        if self._model is not None:
            return self._model

        # Double-checked locking: serialize the first load so concurrent
        # requests share one WhisperModel instead of each building their own
        # (which would double the model's memory footprint on GPU/CPU).
        with self._model_lock:
            if self._model is not None:
                return self._model

            try:
                from faster_whisper import WhisperModel
            except ImportError as exc:
                raise RuntimeError(
                    "faster-whisper is not installed. Install requirements or use text input mode."
                ) from exc

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=self.compute_type,
                cpu_threads=get_whisper_cpu_threads(),
                num_workers=get_whisper_num_workers(),
            )
            return self._model

    def preload(self) -> bool:
        self._load_model()
        return True

    def _run_transcribe(
        self,
        model,
        audio_path: str,
        source_language,
        *,
        condition_on_previous_text: bool | None = None,
        initial_prompt: str | None = None,
        environment: str | None = None,
    ):
        language = None
        if source_language and str(source_language).lower() not in {"auto", "detect", "none"}:
            language = str(source_language).lower().split("-")[0]
        vad_tuning = _vad_options_for_environment(environment)
        options = {
            "language": language,
            "beam_size": get_whisper_beam_size(),
            "best_of": 1,
            "temperature": 0,
            "condition_on_previous_text": False if condition_on_previous_text is None else bool(condition_on_previous_text),
            "vad_filter": True,
            "vad_parameters": {
                "min_silence_duration_ms": vad_tuning["min_silence_duration_ms"],
                "speech_pad_ms": vad_tuning["speech_pad_ms"],
            },
            "without_timestamps": True,
            "word_timestamps": False,
            "compression_ratio_threshold": 2.4,
            "log_prob_threshold": -1.0,
            "no_speech_threshold": vad_tuning["no_speech_threshold"],
        }
        if condition_on_previous_text or language == "ht":
            options["beam_size"] = max(2, get_whisper_beam_size())
        prompt = (initial_prompt or "").strip() or build_initial_prompt(language)
        if prompt:
            options["initial_prompt"] = prompt[:240]
        segments, _ = model.transcribe(
            audio_path,
            **options,
        )
        segment_list = list(segments)
        transcript = " ".join(segment.text.strip() for segment in segment_list).strip()
        normalized = normalize_transcript(transcript, language)
        if not segment_list:
            return TranscriptionResult(text=normalized, confidence=None)
        confidences = [_segment_confidence(segment) for segment in segment_list if segment.text.strip()]
        confidence = sum(confidences) / len(confidences) if confidences else None
        return TranscriptionResult(text=normalized, confidence=confidence)

    def transcribe(self, audio_path: str, source_language=None):
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError("Audio file not found: " + str(audio_path))

        model = self._load_model()
        queued_at = time()
        with self._lock:
            if self._queue_depth >= get_stt_queue_max_depth():
                self._rejected += 1
                raise RuntimeError("STT queue is full. Please retry shortly.")
            self._queue_depth += 1
        with self._semaphore:
            wait_seconds = time() - queued_at
            with self._lock:
                self._queue_depth = max(0, self._queue_depth - 1)
                self._active += 1
                self._wait_times.append(wait_seconds)
                self._wait_times = self._wait_times[-200:]
            transcoded_path = None
            try:
                try:
                    result = self._run_transcribe(model, str(path), source_language)
                    return result.text
                except (RuntimeError, ValueError, OSError) as exc:
                    logger.warning(
                        "Whisper failed to read %s (%s); attempting ffmpeg transcode fallback",
                        audio_path,
                        exc,
                    )
                    transcoded_path = transcode_to_wav(str(path))
                    if not transcoded_path:
                        raise
                    result = self._run_transcribe(model, transcoded_path, source_language)
                    return result.text
            finally:
                with self._lock:
                    self._active = max(0, self._active - 1)
                if transcoded_path:
                    Path(transcoded_path).unlink(missing_ok=True)

    def transcribe_result(
        self,
        audio_path: str,
        source_language=None,
        *,
        condition_on_previous_text: bool | None = None,
        initial_prompt: str | None = None,
        environment: str | None = None,
    ) -> TranscriptionResult:
        path = Path(audio_path)
        if not path.exists():
            raise FileNotFoundError("Audio file not found: " + str(audio_path))

        model = self._load_model()
        queued_at = time()
        with self._lock:
            if self._queue_depth >= get_stt_queue_max_depth():
                self._rejected += 1
                raise RuntimeError("STT queue is full. Please retry shortly.")
            self._queue_depth += 1
        with self._semaphore:
            wait_seconds = time() - queued_at
            with self._lock:
                self._queue_depth = max(0, self._queue_depth - 1)
                self._active += 1
                self._wait_times.append(wait_seconds)
                self._wait_times = self._wait_times[-200:]
            transcoded_path = None
            try:
                try:
                    return self._run_transcribe(
                        model, str(path), source_language,
                        condition_on_previous_text=condition_on_previous_text,
                        initial_prompt=initial_prompt,
                        environment=environment,
                    )
                except (RuntimeError, ValueError, OSError) as exc:
                    logger.warning(
                        "Whisper failed to read %s (%s); attempting ffmpeg transcode fallback",
                        audio_path,
                        exc,
                    )
                    transcoded_path = transcode_to_wav(str(path))
                    if not transcoded_path:
                        raise
                    return self._run_transcribe(
                        model, transcoded_path, source_language,
                        condition_on_previous_text=condition_on_previous_text,
                        initial_prompt=initial_prompt,
                        environment=environment,
                    )
            finally:
                with self._lock:
                    self._active = max(0, self._active - 1)
                if transcoded_path:
                    Path(transcoded_path).unlink(missing_ok=True)

    def queue_snapshot(self):
        with self._lock:
            avg_wait = sum(self._wait_times) / len(self._wait_times) if self._wait_times else 0
            return {
                "queued": self._queue_depth,
                "active": self._active,
                "max_depth": get_stt_queue_max_depth(),
                "rejected": self._rejected,
                "avg_wait_seconds": round(avg_wait, 4),
                "max_wait_seconds": round(max(self._wait_times), 4) if self._wait_times else 0,
            }
