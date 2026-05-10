import subprocess
import sys
import wave
from pathlib import Path
from threading import Lock


# Map language codes to Piper voice file names. The Dockerfile downloads the
# .onnx + .onnx.json pair for each entry into models/tts/. If a language is
# requested but no voice is configured, we fall back to the default English voice.
DEFAULT_VOICES = {
    "en": "models/tts/en_US-lessac-medium.onnx",
    "es": "models/tts/es_ES-davefx-medium.onnx",
}


def _normalize_language(code):
    if not code:
        return "en"
    return str(code).strip().lower().split("-")[0].split("_")[0] or "en"


class PiperTextToSpeech:
    def __init__(self, model_path=None, voices=None):
        # Backward-compat: if a single model_path is passed, use it for English.
        merged = dict(DEFAULT_VOICES)
        if voices:
            for lang, path in voices.items():
                merged[_normalize_language(lang)] = str(path)
        if model_path:
            merged["en"] = str(model_path)
        self.voices = merged
        self.model_path = self.voices["en"]  # legacy attribute
        self._loaded = {}  # language -> PiperVoice instance
        self._lock = Lock()

    def _voice_path(self, language):
        return self.voices.get(_normalize_language(language)) or self.voices["en"]

    def preload(self):
        any_ok = False
        for lang in self.voices:
            try:
                if self._load_voice(lang) is not None:
                    any_ok = True
            except Exception:
                continue
        return any_ok

    def _load_voice(self, language):
        lang = _normalize_language(language)
        cached = self._loaded.get(lang)
        if cached is not None:
            return cached
        path = self._voice_path(lang)
        if not Path(path).exists():
            return None
        try:
            from piper import PiperVoice
        except ImportError:
            return None
        voice = PiperVoice.load(path)
        self._loaded[lang] = voice
        return voice

    def synthesize(self, text, output_path="models/tts/output.wav", language=None):
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        lang = _normalize_language(language)
        model_path = Path(self._voice_path(lang))
        if not model_path.exists():
            # Fall back to English if requested language voice is missing
            fallback = Path(self.voices["en"])
            if not fallback.exists():
                raise FileNotFoundError(
                    "Piper voice model not found for language %s (%s) or fallback %s"
                    % (lang, model_path, fallback)
                )
            model_path = fallback
            lang = "en"

        out_path = Path(output_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        voice = self._load_voice(lang)
        if voice is not None:
            with self._lock:
                audio_chunks = list(voice.synthesize(text))
            if not audio_chunks:
                raise RuntimeError("Piper returned no audio.")
            first_chunk = audio_chunks[0]
            with wave.open(str(out_path), "wb") as wav_file:
                wav_file.setnchannels(first_chunk.sample_channels)
                wav_file.setsampwidth(first_chunk.sample_width)
                wav_file.setframerate(first_chunk.sample_rate)
                for chunk in audio_chunks:
                    wav_file.writeframes(chunk.audio_int16_bytes)
            return str(out_path)

        subprocess.run(
            [
                sys.executable,
                "-m",
                "piper",
                "--model",
                str(model_path),
                "--output-file",
                str(out_path),
            ],
            input=text,
            text=True,
            check=True,
        )
        return str(out_path)
