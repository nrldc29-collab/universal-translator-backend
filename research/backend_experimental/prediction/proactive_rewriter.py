class ProactiveRewriter:
    def rewrite(self, text: str, confusion_score: float, intent_risk: float):
        if float(confusion_score) + float(intent_risk) > 0.6:
            return {
                "original": text,
                "rewritten": self._simplify(text),
                "reason": "Reduced ambiguity for clarity",
            }
        return {"original": text, "rewritten": text, "reason": "No change needed"}

    def _simplify(self, text: str):
        return "Let me explain this more clearly: " + (text or "").strip()
