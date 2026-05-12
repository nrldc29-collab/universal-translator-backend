import base64
import os
import subprocess
import sys
import wave
from pathlib import Path
from threading import Lock

import requests


# Map language codes to Piper voice file names. The Dockerfile downloads the
# .onnx + .onnx.json pair for each entry into models/tts/. If a language is
# requested but no voice is configured, we fall back to the default English voice.
DEFAULT_VOICES = {
    "en": "models/tts/en_US-lessac-medium.onnx",
    # Upgraded from es_ES-davefx-medium (sounded robotic/muffled) to the only
    # -high quality Spanish voice in piper-voices: es_MX-claude-high.
    # Note: this is a Mexican Spanish accent. To revert to Castilian Spanish,
    # swap to es_ES-sharvard-medium (also good quality, but still -medium tier).
    "es": "models/tts/es_MX-claude-high.onnx",
}

# Languages with no Piper voice — synthesized via eSpeak NG fallback by default.
# eSpeak NG 1.50+ supports Haitian Creole (`ht`) but sounds robotic.
# If GOOGLE_TTS_API_KEY is set, Haitian Creole uses Google Cloud neural TTS
# (language code ht-HT) instead of eSpeak for natural-sounding audio.
ESPEAK_LANGUAGES = {"ht"}

# Google Cloud Text-to-Speech is faster than local Piper on the Railway CPU
# instance. Production uses it by default when GOOGLE_TTS_API_KEY is configured,
# and falls back to Piper/eSpeak if the request fails.
GOOGLE_TTS_LANGUAGE_CODES = {
    "en": "en-US",
    "es": "es-MX",
    "ht": "ht-HT",
    "fr": "fr-FR",
    "de": "de-DE",
    "it": "it-IT",
    "pt": "pt-BR",
    "nl": "nl-NL",
    "ru": "ru-RU",
    "zh": "cmn-CN",
    "ja": "ja-JP",
    "ko": "ko-KR",
    "ar": "ar-XA",
    "hi": "hi-IN",
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

    def _use_cloud_tts(self, lang):
        normalized = _normalize_language(lang)
        if not os.getenv("GOOGLE_TTS_API_KEY"):
            return False
        if normalized not in GOOGLE_TTS_LANGUAGE_CODES:
            return False
        return os.getenv("PREFER_CLOUD_TTS", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def _synthesize_google(self, text, out_path, lang):
        """Render audio via Google Cloud Text-to-Speech neural voice.

        Produces a 22050 Hz mono 16-bit PCM WAV — same format Piper outputs.
        Requires GOOGLE_TTS_API_KEY environment variable.
        """
        api_key = os.getenv("GOOGLE_TTS_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_TTS_API_KEY is not set")

        url = (
            "https://texttospeech.googleapis.com/v1/text:synthesize"
            f"?key={api_key}"
        )
        language_code = GOOGLE_TTS_LANGUAGE_CODES.get(_normalize_language(lang))
        if not language_code:
            raise RuntimeError("Google Cloud TTS language is not configured: %s" % lang)

        payload = {
            "input": {"text": text},
            "voice": {"languageCode": language_code},
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": 22050,
            },
        }
        try:
            resp = requests.post(url, json=payload, timeout=30)
            resp.raise_for_status()
        except requests.RequestException as exc:
            raise RuntimeError("Google Cloud TTS request failed: %s" % exc) from exc

        data = resp.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise RuntimeError("Google Cloud TTS returned no audioContent")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return str(out_path)

    def _synthesize_espeak(self, text, out_path, lang):
        """Render audio via eSpeak NG for languages with no Piper voice.

        Produces a 22050 Hz mono 16-bit PCM WAV — same format Piper outputs,
        so the rest of the pipeline doesn't need to know which engine ran.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Speed (-s): 160 wpm is roughly natural. Pitch (-p): 50 = neutral.
        # -a 100 = max amplitude. -w writes WAV. -v ht selects Haitian Creole.
        cmd = [
            "espeak-ng",
            "-v", lang,
            "-s", "160",
            "-p", "50",
            "-a", "100",
            "-w", str(out_path),
            text,
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True, timeout=15)
        except FileNotFoundError as exc:
            raise RuntimeError(
                "espeak-ng is not installed; cannot synthesize %s audio" % lang
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
            raise RuntimeError(
                "espeak-ng failed for %s: %s" % (lang, stderr.strip() or exc)
            ) from exc
        return str(out_path)

    def synthesize(self, text, output_path="models/tts/output.wav", language=None):
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        lang = _normalize_language(language)
        out_path = Path(output_path)

        # Languages with no Piper voice → try Google Cloud TTS first if key is set,
        # otherwise fall back to eSpeak NG (currently: ht).
        if lang in ESPEAK_LANGUAGES:
            if self._use_cloud_tts(lang):
                try:
                    return self._synthesize_google(text, out_path, lang)
                except Exception:
                    # If Google TTS fails for any reason, silently fall back to eSpeak
                    pass
            return self._synthesize_espeak(text, out_path, lang)

        if self._use_cloud_tts(lang):
            try:
                return self._synthesize_google(text, out_path, lang)
            except Exception:
                # Keep speech reliable if the cloud provider is unavailable or a
                # language is rejected; local Piper remains the durable fallback.
                pass

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
