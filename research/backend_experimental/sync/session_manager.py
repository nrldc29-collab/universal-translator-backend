import time
import uuid
from typing import Dict, Any


class SessionManager:
    def __init__(self):
        self.sessions: Dict[str, Dict[str, Any]] = {}

    def create_session(self, host_id: str) -> str:
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {
            "host": host_id,
            "users": [host_id],
            "messages": [],
            "created_at": time.time(),
        }
        return session_id

    def join_session(self, session_id: str, user_id: str) -> bool:
        sess = self.sessions.get(session_id)
        if not sess:
            return False
        if user_id not in sess["users"]:
            sess["users"].append(user_id)
        return True

    def get_session(self, session_id: str) -> Dict[str, Any] | None:
        return self.sessions.get(session_id)
