import wave
from pathlib import Path


class CoquiTextToSpeech:
    def __init__(self, model_name: str = "tts_models/en/ljspeech/tacotron2-DDC"):
        self.model_name = model_name
        self._engine = None

    def _load_engine(self):
        if self._engine is not None:
            return self._engine

        try:
            from TTS.api import TTS
        except ImportError:
            return None

        self._engine = TTS(self.model_name)
        return self._engine

    def synthesize(self, text: str, output_path: str = "models/output.wav") -> str:
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        engine = self._load_engine()
        if engine is None:
            with wave.open(str(path), "w") as wav_file:
                wav_file.setnchannels(1)
                wav_file.setsampwidth(2)
                wav_file.setframerate(16000)
                wav_file.writeframes(b"\x00\x00" * 16000)
            return str(path)

        engine.tts_to_file(text=text, file_path=str(path))
        return str(path)
