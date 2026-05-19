class MeaningKernel:
    def interpret(self, raw_input, context):
        meaning = {
            "intent": (context or {}).get("intent", "unknown"),
            "certainty": float((context or {}).get("confidence", 0.5)),
            "social_weight": self._social_weight(raw_input or ""),
        }
        return meaning

    def _social_weight(self, text):
        t = (text or "").lower()
        if "sorry" in t:
            return 0.8
        if "?" in (text or ""):
            return 0.6
        return 0.4
