import json


class WSHub:
    def __init__(self):
        self.connections = {}  # session_id -> { user_id: websocket }

    async def connect(self, session_id: str, user_id: str, websocket):
        if session_id not in self.connections:
            self.connections[session_id] = {}
        self.connections[session_id][user_id] = websocket

    async def broadcast(self, session_id: str, message: dict):
        if session_id not in self.connections:
            return
        for _, ws in list(self.connections[session_id].items()):
            try:
                await ws.send_json(message)
            except Exception:
                # Ignore broken pipes; caller may clean up later
                pass
