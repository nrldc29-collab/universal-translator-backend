class IntentProxy:
    def refine(self, intent_data: dict) -> str:
        intent = (intent_data or {}).get("intent") or "unknown"
        if intent == "unknown":
            return "clarification_required"
        if intent == "request_action":
            return "action_intent_confirmed"
        if intent == "asking_menu_price":
            return "context_specific_query"
        return intent
