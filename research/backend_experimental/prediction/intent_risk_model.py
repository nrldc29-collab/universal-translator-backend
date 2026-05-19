class IntentRiskModel:
    def evaluate(self, intent: str):
        risky_intents = {
            "request_action": 0.2,
            "location_query": 0.1,
            "unknown": 0.5,
            "emotional_statement": 0.4,
        }
        return risky_intents.get(intent or "unknown", 0.3)
