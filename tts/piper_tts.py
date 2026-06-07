import asyncio
import base64
import html
import logging
import math
import os
import re
import shutil
import subprocess
import sys
import time
import wave
from pathlib import Path
from threading import Lock, get_ident
from typing import Optional

import requests

from backend.tts_pacing import natural_baseline_emotion_config
from tts.tts_readiness import is_neural_tts_ready

logger = logging.getLogger(__name__)

# Map language codes to Piper voice file names. The Dockerfile downloads the
# .onnx + .onnx.json pair for each entry into models/tts/. If a language is
# requested but no voice is configured, we fall back to the default English voice.
DEFAULT_VOICES = {
    "en": "models/tts/en_US-lessac-medium.onnx",
    "es": "models/tts/es_ES-carlfm-x_low.onnx",
    "fr": "models/tts/fr_FR-siwis-medium.onnx",
    "de": "models/tts/de_DE-thorsten-medium.onnx",
    "it": "models/tts/it_IT-riccardo-x_low.onnx",
    "pt": "models/tts/pt_BR-faber-medium.onnx",
    "nl": "models/tts/nl_NL-rlt-medium.onnx",
    "ru": "models/tts/ru_RU-dmitri-medium.onnx",
    "zh": "models/tts/zh_CN-huayan-medium.onnx",
    "ar": "models/tts/ar_JO-kareem-medium.onnx",
    "hi": "models/tts/hi_IN-pratham-medium.onnx",
}

# Languages with no Piper voice — synthesized via eSpeak NG (free, no API key).
# eSpeak works offline for all of these. Google TTS is used instead when
# GOOGLE_TTS_API_KEY is set (better quality).
ESPEAK_LANGUAGES = {"ht", "ja", "ko"}

# eSpeak voice names that differ from the ISO language code
ESPEAK_VOICE_MAP = {
    "zh": "cmn",   # Mandarin Chinese
    "ht": "ht",    # Haitian Creole
    "hi": "hi",    # Hindi
    "ko": "ko",    # Korean
    "ja": "ja",    # Japanese
}

EDGE_TTS_VOICES = {
    "en": "en-US-JennyNeural",
    "es": "es-MX-DaliaNeural",
    "fr": "fr-FR-DeniseNeural",
    "de": "de-DE-KatjaNeural",
    "it": "it-IT-IsabellaNeural",
    "pt": "pt-BR-FranciscaNeural",
    "nl": "nl-NL-ColetteNeural",
    "ru": "ru-RU-SvetlanaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "ja": "ja-JP-NanamiNeural",
    "ko": "ko-KR-SunHiNeural",
    "ar": "ar-SA-ZariyahNeural",
    "hi": "hi-IN-SwaraNeural",
    # No HT neural voice — Canadian French reads Creole more naturally than Parisian.
    "ht": "fr-CA-SylvieNeural",
}

GOOGLE_TTS_NEURAL_VOICES = {
    "en": "en-US-Neural2-F",
    "es": "es-ES-Neural2-A",
    "fr": "fr-FR-Neural2-A",
    "de": "de-DE-Neural2-F",
    "it": "it-IT-Neural2-A",
    "pt": "pt-BR-Neural2-A",
    "nl": "nl-NL-Neural2-F",
    "ru": "ru-RU-Neural2-A",
    "zh": "cmn-CN-Wavenet-A",
    "ja": "ja-JP-Neural2-B",
    "ko": "ko-KR-Neural2-A",
    "ar": "ar-XA-Wavenet-A",
    "hi": "hi-IN-Neural2-A",
    "ht": "ht-HT-Standard-A",
}

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

# Retry configuration
MAX_RETRIES = 3
RETRY_DELAY_MS = 500
GOOGLE_TTS_TIMEOUT = 30
EDGE_TTS_TIMEOUT = 60
FFMPEG_TIMEOUT = 30
ESPEAK_TIMEOUT = 15
PIPER_TIMEOUT = 60


def _normalize_language(code):
    if not code:
        return "en"
    return str(code).strip().lower().split("-")[0].split("_")[0] or "en"


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def google_audio_config_from_emotion(emotion_config: Optional[dict]) -> dict:
    """Map an AILang EmotionTTS tts_config to Google Cloud TTS audioConfig overrides.

    Returns only the keys that differ from neutral so callers can merge them into
    the base audioConfig. Safe with None or partial configs.
    """
    overrides: dict = {}
    if not emotion_config:
        return overrides
    speed = emotion_config.get("speed")
    if isinstance(speed, (int, float)) and speed > 0 and float(speed) != 1.0:
        overrides["speakingRate"] = round(_clamp(float(speed), 0.25, 4.0), 3)
    pitch_shift = emotion_config.get("pitch_shift")
    if isinstance(pitch_shift, (int, float)) and pitch_shift:
        overrides["pitch"] = round(_clamp(float(pitch_shift), -20.0, 20.0), 3)
    volume = emotion_config.get("volume")
    if isinstance(volume, (int, float)) and volume > 0 and float(volume) != 1.0:
        overrides["volumeGainDb"] = round(_clamp(20.0 * math.log10(float(volume)), -96.0, 16.0), 3)
    return overrides


def espeak_flags_from_emotion(emotion_config: Optional[dict]) -> tuple:
    """Map an AILang EmotionTTS tts_config to eSpeak NG (speed_wpm, pitch, amplitude).

    Defaults match the neutral baseline (160 wpm, pitch 50, amplitude 100).
    """
    speed_wpm, pitch, amplitude = 160, 50, 100
    if not emotion_config:
        return speed_wpm, pitch, amplitude
    speed = emotion_config.get("speed")
    if isinstance(speed, (int, float)) and speed > 0:
        speed_wpm = int(_clamp(160.0 * float(speed), 80, 450))
    pitch_shift = emotion_config.get("pitch_shift")
    if isinstance(pitch_shift, (int, float)):
        pitch = int(_clamp(50.0 + float(pitch_shift) * 2.5, 0, 99))
    volume = emotion_config.get("volume")
    if isinstance(volume, (int, float)) and volume > 0:
        amplitude = int(_clamp(100.0 * float(volume), 0, 200))
    return speed_wpm, pitch, amplitude


def edge_tts_controls_from_emotion(emotion_config: Optional[dict]) -> tuple[str, str, str]:
    """Map emotion config into Edge TTS rate, pitch, and volume strings."""
    rate, pitch, volume = "+0%", "+0Hz", "+0%"
    if not emotion_config:
        return rate, pitch, volume

    speed = emotion_config.get("speed")
    if isinstance(speed, (int, float)) and speed > 0 and float(speed) != 1.0:
        rate_pct = int(_clamp((float(speed) - 1.0) * 100.0, -50, 100))
        rate = f"{rate_pct:+d}%"

    pitch_shift = emotion_config.get("pitch_shift")
    if isinstance(pitch_shift, (int, float)) and pitch_shift:
        pitch_hz = int(_clamp(float(pitch_shift) * 20.0, -200, 200))
        pitch = f"{pitch_hz:+d}Hz"

    requested_volume = emotion_config.get("volume")
    if isinstance(requested_volume, (int, float)) and requested_volume > 0 and float(requested_volume) != 1.0:
        volume_pct = int(_clamp((float(requested_volume) - 1.0) * 100.0, -50, 100))
        volume = f"{volume_pct:+d}%"

    return rate, pitch, volume


def _merge_emotion_config(emotion_config: Optional[dict]) -> dict:
    merged = dict(natural_baseline_emotion_config())
    if emotion_config:
        merged.update(emotion_config)
    return merged


def _edge_ssml_enabled() -> bool:
    # Edge neural voices already pause naturally — extra SSML breaks sound stilted/robotic.
    if os.getenv("TTS_NEURAL_MINIMAL_PROCESSING", "1").strip().lower() not in FALSE_VALUES:
        return os.getenv("TTS_EDGE_SSML_PAUSES", "0").strip().lower() not in FALSE_VALUES
    return os.getenv("TTS_EDGE_SSML_PAUSES", "1").strip().lower() not in FALSE_VALUES


FALSE_VALUES = {"0", "false", "no", "off"}


def _edge_ssml_text(text: str) -> str:
    """Insert short pauses at punctuation so neural TTS breathes like a person."""
    stripped = (text or "").strip()
    if not stripped or not _edge_ssml_enabled():
        return stripped
    if stripped.startswith("<speak"):
        return stripped
    body = html.escape(stripped, quote=False)
    body = re.sub(r"([.!?])(\s+)", r'\1<break time="240ms"/>\2', body)
    body = re.sub(r"([,;:])(\s+)", r'\1<break time="130ms"/>\2', body)
    return (
        '<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">'
        f"{body}</speak>"
    )


def _piper_synthesis_config_from_emotion(emotion_config: Optional[dict]):
    """Build a piper SynthesisConfig from an emotion tts_config.

    Always applies a slightly slower length_scale so Piper sounds less rushed.
    """
    emotion_config = _merge_emotion_config(emotion_config)
    try:
        from piper import SynthesisConfig
    except Exception:
        return None
    kwargs: dict = {}
    speed = emotion_config.get("speed")
    if isinstance(speed, (int, float)) and speed > 0:
        kwargs["length_scale"] = round(_clamp(1.0 / float(speed), 0.25, 4.0), 3)
    else:
        kwargs["length_scale"] = 1.07
    volume = emotion_config.get("volume")
    if isinstance(volume, (int, float)) and volume > 0:
        kwargs["volume"] = round(_clamp(float(volume), 0.0, 4.0), 3)
    try:
        return SynthesisConfig(**kwargs)
    except TypeError:
        try:
            return SynthesisConfig(length_scale=kwargs.get("length_scale", 1.07))
        except Exception:
            return None


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
        self._synthesis_count = 0
        self._synthesis_errors = 0

    def _voice_path(self, language):
        return self.voices.get(_normalize_language(language)) or self.voices["en"]

    def preload(self):
        any_ok = False
        for lang in self.voices:
            try:
                if self._load_voice(lang) is not None:
                    any_ok = True
            except (OSError, RuntimeError, ImportError):
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

    def _use_cloud_tts(self, lang, google_api_key=None):
        normalized = _normalize_language(lang)
        effective_key = google_api_key or os.getenv("GOOGLE_TTS_API_KEY")
        if not effective_key:
            return False
        if normalized not in GOOGLE_TTS_LANGUAGE_CODES:
            return False
        return os.getenv("PREFER_CLOUD_TTS", "1").strip().lower() not in {
            "0",
            "false",
            "no",
            "off",
        }

    def _prefer_edge_tts(self, lang):
        normalized = _normalize_language(lang)
        if normalized not in EDGE_TTS_VOICES:
            return False
        if os.getenv("PREFER_EDGE_TTS", "1").strip().lower() in FALSE_VALUES:
            return False
        return is_neural_tts_ready()

    def _try_edge_tts(self, text, out_path, lang, emotion_config=None):
        if not self._prefer_edge_tts(lang):
            return None
        try:
            rendered = self._synthesize_edge_tts(text, out_path, lang, emotion_config=emotion_config)
            return self._finalize_audio(rendered, lang, engine="edge")
        except Exception as exc:
            logger.warning("Edge TTS failed for %s: %s", lang, exc)
            return None

    def _allow_espeak_fallback(self) -> bool:
        return os.getenv("ALLOW_ESPEAK_FALLBACK", "0").strip().lower() not in FALSE_VALUES

    def _finalize_audio(self, path, lang, engine=None):
        try:
            from backend.voice_effects import postprocess_tts_wav

            return postprocess_tts_wav(path, language=lang, engine=engine)
        except Exception as exc:
            logger.warning("tts_softening_failed language=%s path=%s error=%s", lang, path, exc)
            return str(path)

    def _synthesize_google(self, text, out_path, lang, google_api_key=None, emotion_config=None):
        """Render audio via Google Cloud Text-to-Speech neural voice.

        Produces a 22050 Hz mono 16-bit PCM WAV — same format Piper outputs.
        Requires GOOGLE_TTS_API_KEY environment variable or google_api_key param.
        """
        api_key = google_api_key or os.getenv("GOOGLE_TTS_API_KEY")
        if not api_key:
            raise RuntimeError("GOOGLE_TTS_API_KEY is not set")

        url = (
            "https://texttospeech.googleapis.com/v1/text:synthesize"
            f"?key={api_key}"
        )
        language_code = GOOGLE_TTS_LANGUAGE_CODES.get(_normalize_language(lang))
        if not language_code:
            raise RuntimeError("Google Cloud TTS language is not configured: %s" % lang)

        normalized = _normalize_language(lang)
        voice_name = GOOGLE_TTS_NEURAL_VOICES.get(normalized)
        voice_spec = {"languageCode": language_code}
        if voice_name:
            voice_spec["name"] = voice_name
        payload = {
            "input": {"text": text},
            "voice": voice_spec,
            "audioConfig": {
                "audioEncoding": "LINEAR16",
                "sampleRateHertz": 24000,
                "effectsProfileId": ["handset-class-device"],
            },
        }
        payload["audioConfig"].update(
            google_audio_config_from_emotion(_merge_emotion_config(emotion_config))
        )
        
        for attempt in range(MAX_RETRIES):
            try:
                resp = requests.post(url, json=payload, timeout=GOOGLE_TTS_TIMEOUT)
                resp.raise_for_status()
                break
            except requests.RequestException as exc:
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(f"Google Cloud TTS request failed after {MAX_RETRIES} retries: {exc}") from exc
                logger.warning(f"Google TTS attempt {attempt + 1} failed, retrying: {exc}")
                time.sleep(RETRY_DELAY_MS / 1000 * (attempt + 1))

        data = resp.json()
        audio_b64 = data.get("audioContent")
        if not audio_b64:
            raise RuntimeError("Google Cloud TTS returned no audioContent")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "wb") as f:
            f.write(base64.b64decode(audio_b64))
        return str(out_path)

    def _synthesize_espeak(self, text, out_path, lang, emotion_config=None):
        """Render audio via eSpeak NG for languages with no Piper voice.

        Produces a 22050 Hz mono 16-bit PCM WAV — same format Piper outputs,
        so the rest of the pipeline doesn't need to know which engine ran.
        """
        out_path.parent.mkdir(parents=True, exist_ok=True)
        # Speed (-s): 160 wpm is roughly natural. Pitch (-p): 50 = neutral.
        # -a 100 = max amplitude. -w writes WAV. -v ht selects Haitian Creole.
        espeak_voice = ESPEAK_VOICE_MAP.get(lang, lang)
        speed_wpm, pitch, amplitude = espeak_flags_from_emotion(emotion_config)
        cmd = [
            "espeak-ng",
            "-v", espeak_voice,
            "-s", str(speed_wpm),
            "-p", str(pitch),
            "-a", str(amplitude),
            "-w", str(out_path),
            text,
        ]
        
        for attempt in range(MAX_RETRIES):
            try:
                subprocess.run(cmd, check=True, capture_output=True, timeout=ESPEAK_TIMEOUT)
                break
            except FileNotFoundError as exc:
                raise RuntimeError(
                    "espeak-ng is not installed; cannot synthesize %s audio" % lang
                ) from exc
            except subprocess.CalledProcessError as exc:
                stderr = exc.stderr.decode("utf-8", errors="ignore") if exc.stderr else ""
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(
                        "espeak-ng failed for %s after %d retries: %s" % (lang, MAX_RETRIES, stderr.strip() or exc)
                    ) from exc
                logger.warning(f"eSpeak attempt {attempt + 1} failed for {lang}, retrying: {stderr.strip()}")
                time.sleep(RETRY_DELAY_MS / 1000 * (attempt + 1))
            except subprocess.TimeoutExpired as exc:
                if attempt == MAX_RETRIES - 1:
                    raise RuntimeError(f"eSpeak timeout for {lang} after {MAX_RETRIES} retries") from exc
                logger.warning(f"eSpeak attempt {attempt + 1} timed out for {lang}, retrying")
                time.sleep(RETRY_DELAY_MS / 1000 * (attempt + 1))
                
        return str(out_path)

    def _synthesize_edge_tts(self, text, out_path, lang, emotion_config=None):
        """Render audio via Microsoft Edge neural TTS, then convert MP3 to WAV."""
        normalized = _normalize_language(lang)
        voice = EDGE_TTS_VOICES.get(normalized)
        if not voice:
            raise RuntimeError(f"Edge TTS voice is not configured for language {normalized}")

        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            raise RuntimeError("ffmpeg is not installed; cannot convert Edge TTS audio to WAV")

        out_path.parent.mkdir(parents=True, exist_ok=True)
        mp3_path = out_path.with_name(f"{out_path.stem}.edge-{get_ident()}-{int(time.time() * 1000)}.mp3")
        merged_emotion = _merge_emotion_config(emotion_config)
        rate, pitch, volume = edge_tts_controls_from_emotion(merged_emotion)
        edge_text = _edge_ssml_text(text)

        async def render_edge_audio() -> None:
            import edge_tts

            communicator = edge_tts.Communicate(
                edge_text,
                voice=voice,
                rate=rate,
                pitch=pitch,
                volume=volume,
                connect_timeout=10,
                receive_timeout=EDGE_TTS_TIMEOUT,
            )
            await communicator.save(str(mp3_path))

        try:
            asyncio.run(render_edge_audio())
            subprocess.run(
                [
                    ffmpeg,
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-i",
                    str(mp3_path),
                    "-ac",
                    "1",
                    "-ar",
                    "24000",
                    "-sample_fmt",
                    "s16",
                    str(out_path),
                ],
                check=True,
                capture_output=True,
                timeout=FFMPEG_TIMEOUT,
            )
            if not out_path.exists() or out_path.stat().st_size < 100:
                raise RuntimeError(f"Edge TTS conversion returned empty audio at {out_path}")
            return str(out_path)
        finally:
            try:
                mp3_path.unlink(missing_ok=True)
            except OSError:
                pass

    def synthesize(self, text, output_path="models/tts/output.wav", language=None, google_api_key=None, emotion_config=None):
        if not text or not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        self._synthesis_count += 1
        lang = _normalize_language(language)
        emotion_config = _merge_emotion_config(emotion_config)
        out_path = Path(output_path)
        try:
            edge_audio = self._try_edge_tts(text, out_path, lang, emotion_config=emotion_config)
            if edge_audio:
                logger.info("tts_engine=edge_neural lang=%s chars=%d", lang, len(text.strip()))
                return edge_audio

            # Languages with no Piper voice → Google Cloud, then Edge, then eSpeak (last resort).
            if lang in ESPEAK_LANGUAGES:
                if self._use_cloud_tts(lang, google_api_key=google_api_key):
                    try:
                        rendered = self._synthesize_google(text, out_path, lang, google_api_key=google_api_key, emotion_config=emotion_config)
                        return self._finalize_audio(rendered, lang, engine="google")
                    except (requests.RequestException, ConnectionError, TimeoutError) as exc:
                        logger.warning(f"Google TTS failed for {lang}, falling back: {exc}")
                edge_audio = self._try_edge_tts(text, out_path, lang, emotion_config=emotion_config)
                if edge_audio:
                    return edge_audio
                if not self._allow_espeak_fallback():
                    raise RuntimeError(
                        f"Neural TTS unavailable for {lang}. Install edge-tts + ffmpeg "
                        "(pip install edge-tts) or set GOOGLE_TTS_API_KEY."
                    )
                logger.warning("Using eSpeak for %s — voice will sound robotic. Install edge-tts.", lang)
                rendered = self._synthesize_espeak(text, out_path, lang, emotion_config=emotion_config)
                return self._finalize_audio(rendered, lang)

            if self._use_cloud_tts(lang, google_api_key=google_api_key):
                try:
                    rendered = self._synthesize_google(text, out_path, lang, google_api_key=google_api_key, emotion_config=emotion_config)
                    return self._finalize_audio(rendered, lang, engine="google")
                except (requests.RequestException, ConnectionError, TimeoutError) as exc:
                    logger.warning(f"Google TTS failed for {lang}, falling back to Piper: {exc}")

            edge_audio = self._try_edge_tts(text, out_path, lang, emotion_config=emotion_config)
            if edge_audio:
                return edge_audio

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
                logger.warning(f"Voice for {language} not found, using English fallback")

            out_path.parent.mkdir(parents=True, exist_ok=True)

            voice = self._load_voice(lang)
            if voice is not None:
                logger.warning(
                    "tts_engine=piper_fallback lang=%s — voice may sound robotic. Install edge-tts.",
                    lang,
                )
                # Non-blocking for partials: if the lock is already held (another
                # synthesis running), skip rather than queue — keeps audio responsive.
                acquired = self._lock.acquire(blocking=False)
                if not acquired:
                    raise RuntimeError("TTS synthesis busy — skipping partial to stay current.")
                try:
                    syn_config = _piper_synthesis_config_from_emotion(emotion_config)
                    if syn_config is not None:
                        try:
                            audio_chunks = list(voice.synthesize(text, syn_config=syn_config))
                        except TypeError:
                            audio_chunks = list(voice.synthesize(text))
                    else:
                        audio_chunks = list(voice.synthesize(text))
                finally:
                    self._lock.release()
                if not audio_chunks:
                    raise RuntimeError("Piper returned no audio.")
                first_chunk = audio_chunks[0]
                with wave.open(str(out_path), "wb") as wav_file:
                    wav_file.setnchannels(first_chunk.sample_channels)
                    wav_file.setsampwidth(first_chunk.sample_width)
                    wav_file.setframerate(first_chunk.sample_rate)
                    for chunk in audio_chunks:
                        wav_file.writeframes(chunk.audio_int16_bytes)
                return self._finalize_audio(out_path, lang)

            # Fallback to subprocess piper
            for attempt in range(MAX_RETRIES):
                try:
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
                        timeout=PIPER_TIMEOUT,
                    )
                    break
                except subprocess.TimeoutExpired as exc:
                    if attempt == MAX_RETRIES - 1:
                        raise RuntimeError(f"Piper timeout after {MAX_RETRIES} retries") from exc
                    logger.warning(f"Piper attempt {attempt + 1} timed out, retrying")
                    time.sleep(RETRY_DELAY_MS / 1000 * (attempt + 1))
                except subprocess.CalledProcessError as exc:
                    if attempt == MAX_RETRIES - 1:
                        raise RuntimeError(f"Piper failed after {MAX_RETRIES} retries: {exc}") from exc
                    logger.warning(f"Piper attempt {attempt + 1} failed, retrying")
                    time.sleep(RETRY_DELAY_MS / 1000 * (attempt + 1))
                    
            return self._finalize_audio(out_path, lang)
        except Exception as exc:
            self._synthesis_errors += 1
            logger.error(f"TTS synthesis failed: {exc}")
            raise

    def get_stats(self) -> dict:
        """Get TTS synthesis statistics."""
        return {
            "total_syntheses": self._synthesis_count,
            "total_errors": self._synthesis_errors,
            "error_rate": self._synthesis_errors / self._synthesis_count if self._synthesis_count > 0 else 0,
            "loaded_voices": list(self._loaded.keys()),
        }
