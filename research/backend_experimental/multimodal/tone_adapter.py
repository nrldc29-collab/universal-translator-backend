class ToneAdapter:
    def adapt_response(self, fused_signal: dict):
        state = (fused_signal or {}).get("communication_state") or "stable"
        if state == "high_tension":
            return {"tone": "calm", "prefix": "I understand — let’s slow this down."}
        if state == "needs_clarification":
            return {"tone": "gentle_clarification", "prefix": "Just to make sure I understand correctly:"}
        if state == "repair_mode":
            return {"tone": "supportive", "prefix": "No problem — I think I see what you mean."}
        return {"tone": "neutral", "prefix": ""}
