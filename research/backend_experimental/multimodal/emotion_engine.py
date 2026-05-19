class EmotionEngine:
    def infer(self, text: str, prosody: dict):
        t = (text or "").lower()
        emotion = "neutral"
        if "!" in t:
            emotion = "excited"
        if prosody.get("stress_level", 0.0) > 0.7:
            emotion = "anxious"
        if "sorry" in t or "my bad" in t:
            emotion = "apologetic"
        if "..." in t:
            emotion = "uncertain"
        return {
            "emotion": emotion,
            "confidence": 0.7 + float(prosody.get("stress_level", 0.0)) * 0.2,
        }
