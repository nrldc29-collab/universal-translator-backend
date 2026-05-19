class SharedUnderstandingBus:
    def __init__(self):
        self.memory = {}

    def publish(self, session_id: str, thought: dict) -> None:
        if session_id not in self.memory:
            self.memory[session_id] = []
        self.memory[session_id].append(thought)

    def sync(self, session_id: str):
        return self.memory.get(session_id, [])
