class SemanticStateEngine:
    def __init__(self):
        self.state = {}

    def update(self, session_id: str, meaning: dict):
        if session_id not in self.state:
            self.state[session_id] = []
        self.state[session_id].append(meaning)

    def get_state(self, session_id: str):
        return self.state.get(session_id, [])
