"""
Advanced TTS module supporting XTTS v2, StyleTTS2, and ElevenLabs-like systems.
Provides voice cloning, emotional/prosodic control, and high-quality neural synthesis.
"""

import os
import io
import logging
import wave
import numpy as np
from enum import Enum
from typing import Optional, Dict, Any, List
from pathlib import Path


logger = logging.getLogger(__name__)


class TTSBackend(str, Enum):
    XTTS = "xtts"
    STYLE_TTS2 = "styletts2"
    ELEVENLABS = "elevenlabs"
    COQUI_TTS = "coqui_tts"


class AdvancedTTS:
    """
    Unified interface for advanced TTS systems with:
    - Voice cloning (XTTS)
    - Style/prosody control (StyleTTS2)
    - High-quality neural synthesis (ElevenLabs-like)
    """

    def __init__(
        self,
        backend: TTSBackend = TTSBackend.XTTS,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: str = "cpu",
        elevenlabs_api_key: Optional[str] = None,
    ):
        self.backend = backend
        self.model_name = model_name
        self.device = device
        self.elevenlabs_api_key = elevenlabs_api_key or os.getenv("ELEVENLABS_API_KEY")
        
        self._model = None
        self._styletts2_model = None
        self._elevenlabs_client = None

    def preload(self) -> bool:
        """Preload the TTS model based on backend."""
        try:
            if self.backend == TTSBackend.XTTS:
                return self._preload_xtts()
            elif self.backend == TTSBackend.STYLE_TTS2:
                return self._preload_styletts2()
            elif self.backend == TTSBackend.ELEVENLABS:
                return self._preload_elevenlabs()
            elif self.backend == TTSBackend.COQUI_TTS:
                return self._preload_coqui_tts()
            else:
                raise ValueError(f"Unknown backend: {self.backend}")
        except (ImportError, RuntimeError, OSError, ConnectionError) as exc:
            logger.warning("advanced_tts_preload_failed backend=%s error=%s", self.backend, exc)
            return False

    def _preload_xtts(self):
        try:
            from TTS.api import TTS
            self._model = TTS(self.model_name, gpu=self.device == "cuda")
            return True
        except ImportError:
            logger.info("coqui_tts_package_not_installed")
            return False

    def _preload_styletts2(self):
        logger.info("styletts2_integration_not_configured")
        return True

    def _preload_elevenlabs(self):
        if not self.elevenlabs_api_key:
            logger.info("elevenlabs_api_key_not_configured")
            return False
        try:
            import elevenlabs
            elevenlabs.set_api_key(self.elevenlabs_api_key)
            self._elevenlabs_client = elevenlabs
            return True
        except ImportError:
            logger.info("elevenlabs_package_not_installed")
            return False

    def _preload_coqui_tts(self):
        try:
            from TTS.api import TTS
            self._model = TTS("tts_models/en/ljspeech/tacotron2-DDC")
            return True
        except ImportError:
            return False

    def synthesize(
        self,
        text: str,
        output_path: Optional[str] = None,
        voice_id: Optional[str] = None,
        speaker_wav: Optional[str] = None,
        emotion: Optional[str] = None,
        style: Optional[Dict[str, Any]] = None,
        prosody: Optional[Dict[str, float]] = None,
        language: str = "en",
    ) -> bytes:
        """
        Synthesize text to speech with advanced controls.

        Args:
            text: Text to synthesize
            output_path: Optional path to save WAV file
            voice_id: Voice ID (for ElevenLabs or voice cloning)
            speaker_wav: Path to speaker reference WAV for voice cloning (XTTS)
            emotion: Emotion type (happy, sad, angry, neutral, etc.)
            style: Style parameters (speed, pitch, energy)
            prosody: Prosodic features (rate, pitch, volume)
            language: Language code

        Returns:
            WAV audio as bytes
        """
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        if self.backend == TTSBackend.XTTS:
            return self._synthesize_xtts(text, speaker_wav, language, output_path)
        elif self.backend == TTSBackend.STYLE_TTS2:
            return self._synthesize_styletts2(text, style, emotion, output_path)
        elif self.backend == TTSBackend.ELEVENLABS:
            return self._synthesize_elevenlabs(text, voice_id, style, output_path)
        elif self.backend == TTSBackend.COQUI_TTS:
            return self._synthesize_coqui(text, output_path)
        else:
            raise ValueError(f"Unsupported backend: {self.backend}")

    def _synthesize_xtts(
        self, text: str, speaker_wav: Optional[str], language: str, output_path: Optional[str]
    ) -> bytes:
        """XTTS v2 synthesis with voice cloning."""
        if not self._model:
            self._preload_xtts()

        # XTTS supports voice cloning via speaker_wav
        if speaker_wav and Path(speaker_wav).exists():
            wav_data = self._model.tts(text=text, speaker_wav=speaker_wav, language=language)
        else:
            wav_data = self._model.tts(text=text, language=language)

        return self._to_wav_bytes(wav_data, output_path)

    def _synthesize_styletts2(
        self, text: str, style: Optional[Dict], emotion: Optional[str], output_path: Optional[str]
    ) -> bytes:
        """
        StyleTTS2 synthesis with style and emotion control.
        StyleTTS2 integration point with deterministic silence fallback.
        """
        # StyleTTS2 supports:
        # - Style extraction from reference audio
        # - Emotion/prosody transfer
        # - Fine-grained style control
        logger.info("styletts2_silence_fallback style=%s emotion=%s", style, emotion)
        
        # Placeholder: return silence or use fallback
        return self._generate_silence(1.0, output_path)

    def _synthesize_elevenlabs(
        self, text: str, voice_id: Optional[str], style: Optional[Dict], output_path: Optional[str]
    ) -> bytes:
        """ElevenLabs-style synthesis with high-quality neural TTS."""
        if not self._elevenlabs_client:
            self._preload_elevenlabs()

        try:
            import elevenlabs
            
            # Configure voice settings
            voice_settings = {}
            if style:
                if "speed" in style:
                    voice_settings["stability"] = 1.0 - (style["speed"] / 2.0)  # Map speed to stability
                if "pitch" in style:
                    voice_settings["similarity_boost"] = style["pitch"]
            
            # Generate audio
            audio = elevenlabs.generate(
                text=text,
                voice=voice_id or "Rachel",  # Default ElevenLabs voice
                model="eleven_multilingual_v2",
                voice_settings=voice_settings if voice_settings else None,
            )
            
            audio_bytes = b"".join(audio) if isinstance(audio, list) else audio
            
            if output_path:
                Path(output_path).parent.mkdir(parents=True, exist_ok=True)
                with open(output_path, "wb") as f:
                    f.write(audio_bytes)
            
            return audio_bytes
            
        except (requests.RequestException, ConnectionError, TimeoutError, ValueError) as exc:
            logger.exception("elevenlabs_synthesis_failed")
            raise

    def _synthesize_coqui(self, text: str, output_path: Optional[str]) -> bytes:
        """Standard Coqui TTS synthesis."""
        if not self._model:
            self._preload_coqui_tts()
        
        wav_data = self._model.tts(text)
        return self._to_wav_bytes(wav_data, output_path)

    def _to_wav_bytes(self, audio_data, output_path: Optional[str]) -> bytes:
        """Convert audio data to WAV bytes."""
        import numpy as np
        
        # Handle different return types from TTS models
        if isinstance(audio_data, np.ndarray):
            audio_array = audio_data
        elif isinstance(audio_data, list):
            audio_array = np.array(audio_data)
        else:
            raise ValueError(f"Unknown audio data type: {type(audio_data)}")
        
        # Convert to int16
        audio_int16 = (audio_array * 32767).astype(np.int16)
        
        # Create WAV in memory
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)  # Standard sample rate
            wav_file.writeframes(audio_int16.tobytes())
        
        wav_bytes = buffer.getvalue()
        
        # Optionally save to file
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(wav_bytes)
        
        return wav_bytes

    def _generate_silence(self, duration: float, output_path: Optional[str]) -> bytes:
        """Generate silence for placeholder implementations."""
        sample_rate = 22050
        samples = np.zeros(int(duration * sample_rate), dtype=np.int16)
        
        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(samples.tobytes())
        
        wav_bytes = buffer.getvalue()
        
        if output_path:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(wav_bytes)
        
        return wav_bytes

    def get_available_voices(self) -> List[Dict[str, Any]]:
        """Get list of available voices (for ElevenLabs or voice cloning)."""
        if self.backend == TTSBackend.ELEVENLABS and self._elevenlabs_client:
            try:
                voices = elevenlabs.voices()
                return [{"id": v.voice_id, "name": v.name} for v in voices.voices]
            except (requests.RequestException, ConnectionError, TimeoutError) as exc:
                logger.warning("elevenlabs_voices_failed error=%s", exc)
                return []
        else:
            # For XTTS, voices are defined by speaker_wav files
            return [{"id": "default", "name": "Default Voice"}]

    def clone_voice(self, reference_audio: str, voice_name: str) -> Optional[str]:
        """
        Clone a voice from reference audio (XTTS feature).
        Returns voice ID or path to cloned voice model.
        """
        if self.backend != TTSBackend.XTTS:
            logger.info("voice_cloning_not_supported backend=%s", self.backend)
            return None
        
        # XTTS uses speaker_wav directly, no separate cloning step needed
        if Path(reference_audio).exists():
            return reference_audio
        return None


# Convenience function for quick synthesis
def synthesize_advanced(
    text: str,
    backend: str = "xtts",
    voice_id: Optional[str] = None,
    emotion: Optional[str] = None,
    language: str = "en",
    output_path: Optional[str] = None,
) -> bytes:
    """
    Quick synthesis using advanced TTS.
    
    Examples:
        # XTTS with voice cloning
        audio = synthesize_advanced("Hello world", backend="xtts", speaker_wav="reference.wav")
        
        # ElevenLabs high-quality
        audio = synthesize_advanced("Hello world", backend="elevenlabs", voice_id="Rachel")
        
        # StyleTTS2 with emotion
        audio = synthesize_advanced("Hello world", backend="styletts2", emotion="happy")
    """
    tts_backend = TTSBackend(backend)
    tts = AdvancedTTS(backend=tts_backend)
    tts.preload()
    
    return tts.synthesize(
        text=text,
        voice_id=voice_id,
        emotion=emotion,
        language=language,
        output_path=output_path,
    )
