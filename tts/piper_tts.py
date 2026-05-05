import subprocess
import sys
from pathlib import Path


class PiperTextToSpeech:
    def __init__(self, model_path: str = "models/tts/en_US-lessac-medium.onnx"):
        self.model_path = model_path

    def preload(self) -> bool:
        return Path(self.model_path).exists()

    def synthesize(self, text: str, output_path: str = "models/tts/output.wav") -> str:
        if not text.strip():
            raise ValueError("Cannot synthesize empty text.")

        model = Path(self.model_path)
        if not model.exists():
            raise FileNotFoundError(f"Piper voice model not found: {self.model_path}")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

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
