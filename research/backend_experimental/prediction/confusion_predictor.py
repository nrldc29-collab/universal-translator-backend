class ConfusionPredictor:
    def predict(self, text: str, context: dict):
        score = 0.0
        words = (text or "").lower().split()
        ambiguous_words = ["bank", "charge", "case", "run", "set"]
        for w in words:
            if w in ambiguous_words:
                score += 0.2
        if len(words) > 20:
            score += 0.3
        if not (context or {}).get("topic"):
            score += 0.2
        return min(score, 1.0)
