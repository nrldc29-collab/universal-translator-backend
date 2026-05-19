class InterpreterRoom:
    def __init__(self, mediator, state, hub):
        self.mediator = mediator
        self.state = state
        self.hub = hub

    async def handle_message(self, session_id: str, user_id: str, payload: dict):
        text = payload.get("text", "")
        stt_conf = float(payload.get("stt_conf", 1.0))
        trans_conf = float(payload.get("trans_conf", 1.0))
        context = {
            "history": self.state.get_context(session_id),
            "target_language": payload.get("target_language", "en"),
        }
        result = self.mediator.process(stt_conf, trans_conf, text, context)
        # Save conversation state
        self.state.append(session_id, {
            "user": user_id,
            "input": text,
            "output": result,
        })
        # Broadcast to everyone in the session
        await self.hub.broadcast(session_id, {
            "type": "translation_update",
            "user": user_id,
            "data": result,
        })
