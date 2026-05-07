import subprocess
import sys
import wave
from pathlib import Path
from threading import Lock


class PiperTextToSpeech:
    def __init__(self, model_path: str = "models/tts/en_US-lessac-medium.onnx"):
        self.model_path = model_path
        self._voice = None
        self._lock = Lock()

    def preload(self) -> bool:
        if not Path(self.model_path).exists():
            return False
        return self._load_voice() is not None

    def _load_voice(self):
        if self._voice is not None:
            return self._voice

        try:
            from piper import PiperVoice
        except ImportError:
            return None

        self._voice = PiperVoice.load(self.model_path)
        return self._voice

    def synthesize(self, text: str, output_path: str = "models/tts/output.wav") -> str:
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        model = Path(self.model_path)
        if not model.exists():
            raise FileNotFoundError(f"Piper voice model not found: {self.model_path}")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        voice = self._load_voice()
        if voice is not None:
            with self._lock:
                audio_chunks = list(voice.synthesize(text))
            if not audio_chunks:
                raise RuntimeError("Piper returned no audio.")
            first_chunk = audio_chunks[0]
            with wave.open(str(path), "wb") as wav_file:
                wav_file.setnchannels(first_chunk.sample_channels)
                wav_file.setsampwidth(first_chunk.sample_width)
                wav_file.setframerate(first_chunk.sample_rate)
                for chunk in audio_chunks:
                    wav_file.writeframes(chunk.audio_int16_bytes)
            return str(path)

        subprocess.run(
            [
                sys.executable,
                "-m",
                "piper",
                "--model",
                str(model),
                "--output-file",
                str(path),
            ],
            input=text,
            text=True,
            check=True,
        )
        return str(path)
