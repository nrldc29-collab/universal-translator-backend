class ConversationState:
    def __init__(self):
        self.state = {}

    def append(self, session_id: str, message: dict) -> None:
        if session_id not in self.state:
            self.state[session_id] = []
        self.state[session_id].append(message)
        self.state[session_id] = self.state[session_id][-200:]

    def get_context(self, session_id: str):
        return self.state.get(session_id, [])
