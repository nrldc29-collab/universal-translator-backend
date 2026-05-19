class ProsodyAnalyzer:
    def analyze(self, audio_features: dict):
        speech_rate = float(audio_features.get("speech_rate", 1.0) or 1.0)
        pitch_variance = float(audio_features.get("pitch_variance", 0.5) or 0.5)
        pauses = float(audio_features.get("pause_ratio", 0.2) or 0.2)

        stress_score = ((1.2 - speech_rate) * 0.4) + (pitch_variance * 0.4) + (pauses * 0.2)
        stress_level = min(max(stress_score, 0.0), 1.0)

        return {
            "stress_level": stress_level,
            "speech_rate": speech_rate,
        }
