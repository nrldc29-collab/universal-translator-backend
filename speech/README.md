# Speech

Speech-processing adapters for Anai Translator.

- `whisper_stt.py` — faster-whisper speech-to-text adapter.
- `silero_vad.py` — voice activity detection.
- `audio_decode.py` — audio transcoding helpers.
- `noise_suppression.py` and `speaker_diarization.py` — optional/experimental speech utilities.

Model/cache files belong in `models/whisper/`, not in this package.
