from time import time

from backend.config import get_session_history_limit, get_session_ttl_seconds


class SessionRegistry:
    def __init__(self):
        self.sessions = {}
        self.shared_sessions = {}

    def bind(self, session_id: str, speaker: str, identity: str, source_language: str, target_language: str) -> dict:
        self.cleanup()
        key = f"{identity}:{session_id}:{speaker}"
        shared_key = f"{identity}:{session_id}"
        shared_state = self.shared_sessions.get(shared_key, {"session_id": session_id, "identity": identity, "devices": {}, "history": []})
        shared_state["devices"][speaker] = {
            "speaker": speaker,
            "source_language": source_language,
            "target_language": target_language,
            "connected": True,
            "last_seen": time(),
        }
        shared_state["last_seen"] = time()
        self.shared_sessions[shared_key] = shared_state
        state = self.sessions.get(key, {})
        state.update({
            "session_id": session_id,
            "speaker": speaker,
            "identity": identity,
            "source_language": source_language,
            "target_language": target_language,
            "connected": True,
            "last_seen": time(),
            "reconnects": state.get("reconnects", -1) + 1,
            "shared": shared_state,
        })
        self.sessions[key] = state
        return state

    def disconnect(self, session_id: str, speaker: str, identity: str) -> None:
        key = f"{identity}:{session_id}:{speaker}"
        shared_key = f"{identity}:{session_id}"
        if key in self.sessions:
            self.sessions[key]["connected"] = False
            self.sessions[key]["last_seen"] = time()
        if shared_key in self.shared_sessions and speaker in self.shared_sessions[shared_key]["devices"]:
            self.shared_sessions[shared_key]["devices"][speaker]["connected"] = False
            self.shared_sessions[shared_key]["devices"][speaker]["last_seen"] = time()

    def snapshot(self) -> dict:
        self.cleanup()
        return self.sessions

    def record_turn(self, session_id: str, identity: str, speaker: str, source_text: str, translated_text: str, semantic_context: dict) -> dict:
        shared_key = f"{identity}:{session_id}"
        shared_state = self.shared_sessions.get(shared_key, {"session_id": session_id, "identity": identity, "devices": {}, "history": []})
        shared_state["history"].append({
            "speaker": speaker,
            "source_text": source_text,
            "translated_text": translated_text,
            "semantic_context": semantic_context,
            "created_at": time(),
        })
        shared_state["history"] = shared_state["history"][-get_session_history_limit():]
        shared_state["last_seen"] = time()
        self.shared_sessions[shared_key] = shared_state
        return shared_state

    def active_stream_count(self, identity: str) -> int:
        self.cleanup()
        return len([
            session
            for session in self.sessions.values()
            if session.get("identity") == identity and session.get("connected")
        ])

    def cleanup(self) -> None:
        now = time()
        ttl = get_session_ttl_seconds()
        expired_keys = [
            key
            for key, session in self.sessions.items()
            if not session.get("connected") and now - session.get("last_seen", now) > ttl
        ]
        for key in expired_keys:
            del self.sessions[key]
        expired_shared_keys = [
            key
            for key, session in self.shared_sessions.items()
            if now - session.get("last_seen", now) > ttl
        ]
        for key in expired_shared_keys:
            del self.shared_sessions[key]


session_registry = SessionRegistry()
