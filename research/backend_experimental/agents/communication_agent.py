class CommunicationAgent:
    def __init__(self, user_id, mediator):
        self.user_id = user_id
        self.mediator = mediator
        self.intent_memory = []

    def interpret(self, text, context):
        result = self.mediator.process(
            text,
            context.get("audio_features", {}),
            context,
        )
        self.intent_memory.append({
            "input": text,
            "output": result,
        })
        return result

    def propose_message(self, raw_text):
        return {
            "user_id": self.user_id,
            "proposal": raw_text,
            "status": "pending_negotiation",
        }
