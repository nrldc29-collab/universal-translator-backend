class SignalFusion:
    def fuse(self, semantic_result: dict, emotion_result: dict, prosody_result: dict):
        return {
            "meaning": (semantic_result or {}).get("output"),
            "intent": (semantic_result or {}).get("intent"),
            "confidence": (semantic_result or {}).get("confidence"),
            "emotion": (emotion_result or {}).get("emotion"),
            "stress": (prosody_result or {}).get("stress_level"),
            "communication_state": self._classify_state(
                (emotion_result or {}).get("emotion"),
                float((prosody_result or {}).get("stress_level", 0.0)),
            ),
        }

    def _classify_state(self, emotion: str | None, stress: float) -> str:
        if stress > 0.7:
            return "high_tension"
        if emotion == "uncertain":
            return "needs_clarification"
        if emotion == "apologetic":
            return "repair_mode"
        return "stable"
