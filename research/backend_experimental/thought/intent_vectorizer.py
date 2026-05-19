class IntentVectorizer:
    def vectorize(self, text: str, context: dict):
        t = (text or "")
        ctx = context or {}
        return {
            "goal": self._extract_goal(t),
            "emotion": ctx.get("emotion", "neutral"),
            "certainty": float(ctx.get("confidence", 0.5)),
            "urgency": self._urgency(t),
            "social_weight": self._social(t),
        }

    def _extract_goal(self, text: str) -> str:
        tl = text.lower()
        if "need" in tl:
            return "request"
        if "why" in tl:
            return "inquiry"
        return "statement"

    def _urgency(self, text: str) -> float:
        return 0.8 if "now" in (text or "").lower() else 0.3

    def _social(self, text: str) -> float:
        return 0.7 if "sorry" in (text or "").lower() else 0.4
