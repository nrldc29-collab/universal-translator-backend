from pathlib import Path
from tempfile import NamedTemporaryFile


class SileroVoiceActivityDetector:
    def __init__(self, threshold: float = 0.3, min_speech_duration_ms: int = 200):
        self.threshold = threshold
        self.min_speech_duration_ms = min_speech_duration_ms
        self._model = None
        self._utils = None

    def _load(self):
        if self._model is not None and self._utils is not None:
            return self._model, self._utils

        try:
            import torch
        except ImportError as exc:
            raise RuntimeError("torch is required for Silero VAD.") from exc

        self._model, self._utils = torch.hub.load(
            repo_or_dir="snakers4/silero-vad",
            model="silero_vad",
            force_reload=False,
            onnx=False,
            trust_repo=True,
        )
        return self._model, self._utils

    def detect_file(self, audio_path: str) -> dict:
        path = Path(audio_path)
        if not path.exists() or path.stat().st_size == 0:
            return {"speech_detected": False, "segments": [], "speech_seconds": 0.0}

        model, utils = self._load()
        get_speech_timestamps = utils[0]
        read_audio = utils[2]

        wav = read_audio(str(path), sampling_rate=16000)
        speech_timestamps = get_speech_timestamps(
            wav,
            model,
            threshold=self.threshold,
            min_speech_duration_ms=self.min_speech_duration_ms,
            sampling_rate=16000,
        )
        speech_seconds = sum((item["end"] - item["start"]) / 16000 for item in speech_timestamps)

        return {
            "speech_detected": bool(speech_timestamps),
            "segments": speech_timestamps,
            "speech_seconds": speech_seconds,
        }

    def detect_bytes(self, audio_bytes: bytes, suffix: str = ".webm") -> dict:
        with NamedTemporaryFile(delete=False, suffix=suffix) as temp_file:
            temp_file.write(audio_bytes)
            temp_path = temp_file.name

        try:
            return self.detect_file(temp_path)
        finally:
            Path(temp_path).unlink(missing_ok=True)
