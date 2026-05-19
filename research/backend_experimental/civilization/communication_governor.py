class CommunicationGovernor:
    def __init__(self):
        self.global_rules = {
            "prefer_clarity": True,
            "limit_ambiguity": True,
            "encourage_confirmation": True,
        }

    def evaluate_message(self, message_data: dict) -> dict:
        risk = float((message_data or {}).get("confusion_score", 0.0))
        if risk > 0.7:
            return {"action": "enforce_clarification", "reason": "High ambiguity detected"}
        if risk > 0.4:
            return {"action": "soft_rewrite", "reason": "Improve clarity before sending"}
        return {"action": "allow", "reason": "Safe communication"}
