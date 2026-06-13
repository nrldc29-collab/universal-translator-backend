from threading import RLock
from time import time
from uuid import uuid4

from backend.config import get_session_history_limit, get_session_ttl_seconds


GENERIC_SPEAKER_NAMES = {"", "auto", "speaker", "this device", "this phone", "unknown"}


def normalize_device_id(device_id: str | None) -> str:
    value = str(device_id or "").strip()
    return value[:96] if value else f"device-{uuid4()}"


def normalize_speaker_name(name: str | None) -> str:
    value = str(name or "").strip()
    return value[:40]


def speaker_label_for_index(index: int, preferred_name: str | None = None) -> str:
    preferred = normalize_speaker_name(preferred_name)
    if preferred.lower() not in GENERIC_SPEAKER_NAMES:
        return preferred
    return f"Person {index}"


class SessionRegistry:
    def __init__(self):
        self.sessions = {}
        self.shared_sessions = {}
        self._lock = RLock()

    def _shared_key(self, session_id: str, identity: str) -> str:
        return f"{identity}:{session_id}"

    def _session_key(self, session_id: str, speaker: str, identity: str, device_id: str | None = None) -> str:
        suffix = normalize_device_id(device_id) if device_id else speaker
        return f"{identity}:{session_id}:{speaker}:{suffix}"

    def _new_shared_state(self, session_id: str, identity: str) -> dict:
        return {
            "session_id": session_id,
            "identity": identity,
            "devices": {},
            "speakers": {},
            "history": [],
            "next_speaker_index": 1,
            "last_seen": time(),
        }

    def _next_speaker_index(self, shared_state: dict) -> int:
        next_index = int(shared_state.get("next_speaker_index") or 1)
        used_indexes = [
            int(profile.get("speaker_index", 0))
            for profile in shared_state.get("speakers", {}).values()
            if str(profile.get("speaker_index", "")).isdigit()
        ]
        if used_indexes:
            next_index = max(next_index, max(used_indexes) + 1)
        shared_state["next_speaker_index"] = next_index + 1
        return next_index

    def resolve_auto_speaker(
        self,
        session_id: str,
        identity: str,
        device_id: str | None,
        source_language: str,
        target_language: str,
        speaker_name: str | None = None,
        connected: bool = True,
    ) -> dict:
        self.cleanup()
        normalized_device_id = normalize_device_id(device_id)
        with self._lock:
            shared_key = self._shared_key(session_id, identity)
            shared_state = self.shared_sessions.get(shared_key) or self._new_shared_state(session_id, identity)
            devices = shared_state.setdefault("devices", {})
            speakers = shared_state.setdefault("speakers", {})

            device_state = devices.get(normalized_device_id)
            if device_state and device_state.get("speaker"):
                speaker = device_state["speaker"]
                speaker_profile = speakers.get(speaker, {})
                speaker_index = int(speaker_profile.get("speaker_index") or device_state.get("speaker_index") or 1)
                speaker_label = speaker_profile.get("speaker_label") or device_state.get("speaker_label") or speaker_label_for_index(speaker_index, speaker_name)
            else:
                speaker_index = self._next_speaker_index(shared_state)
                speaker = f"person-{speaker_index}"
                speaker_label = speaker_label_for_index(speaker_index, speaker_name)
                speaker_profile = {
                    "speaker": speaker,
                    "speaker_label": speaker_label,
                    "speaker_index": speaker_index,
                    "detection": "device_source",
                    "created_at": time(),
                }
                speakers[speaker] = speaker_profile

            shared_state["last_seen"] = time()
            self.shared_sessions[shared_key] = shared_state
            state = self.bind(
                session_id=session_id,
                speaker=speaker,
                identity=identity,
                source_language=source_language,
                target_language=target_language,
                device_id=normalized_device_id,
                speaker_label=speaker_label,
                speaker_index=speaker_index,
                detection="device_source",
                connected=connected,
            )
            return {
                "speaker": speaker,
                "speaker_label": speaker_label,
                "speaker_index": speaker_index,
                "device_id": normalized_device_id,
                "detection": "device_source",
                "confidence": 1.0,
                "session": state,
            }

    def bind(
        self,
        session_id: str,
        speaker: str,
        identity: str,
        source_language: str,
        target_language: str,
        device_id: str | None = None,
        speaker_label: str | None = None,
        speaker_index: int | None = None,
        detection: str = "manual",
        connected: bool = True,
    ) -> dict:
        self.cleanup()
        normalized_device_id = normalize_device_id(device_id) if device_id else None
        with self._lock:
            shared_key = self._shared_key(session_id, identity)
            shared_state = self.shared_sessions.get(shared_key) or self._new_shared_state(session_id, identity)
            speakers = shared_state.setdefault("speakers", {})
            devices = shared_state.setdefault("devices", {})

            if speaker_index is None:
                speaker_index = int(speakers.get(speaker, {}).get("speaker_index") or 0) or None
            if speaker_index is None and speaker.startswith("person-") and speaker.rsplit("-", 1)[-1].isdigit():
                speaker_index = int(speaker.rsplit("-", 1)[-1])
            if speaker_index is None:
                speaker_index = self._next_speaker_index(shared_state)

            label = speaker_label or speakers.get(speaker, {}).get("speaker_label") or speaker_label_for_index(speaker_index)
            speakers[speaker] = {
                **speakers.get(speaker, {}),
                "speaker": speaker,
                "speaker_label": label,
                "speaker_index": speaker_index,
                "detection": detection,
                "last_seen": time(),
            }
            if normalized_device_id:
                devices[normalized_device_id] = {
                    "device_id": normalized_device_id,
                    "speaker": speaker,
                    "speaker_label": label,
                    "speaker_index": speaker_index,
                    "source_language": source_language,
                    "target_language": target_language,
                    "connected": connected,
                    "last_seen": time(),
                    "detection": detection,
                }

            shared_state["last_seen"] = time()
            self.shared_sessions[shared_key] = shared_state
            key = self._session_key(session_id, speaker, identity, normalized_device_id)
            state = self.sessions.get(key, {})
            state.update({
                "session_id": session_id,
                "speaker": speaker,
                "speaker_label": label,
                "speaker_index": speaker_index,
                "identity": identity,
                "device_id": normalized_device_id,
                "source_language": source_language,
                "target_language": target_language,
                "connected": connected,
                "last_seen": time(),
                "reconnects": state.get("reconnects", -1) + 1,
                "detection": detection,
                "shared": shared_state,
            })
            self.sessions[key] = state
            return state

    def disconnect(self, session_id: str, speaker: str, identity: str, device_id: str | None = None) -> None:
        normalized_device_id = normalize_device_id(device_id) if device_id else None
        with self._lock:
            shared_key = self._shared_key(session_id, identity)
            for state in self.sessions.values():
                if state.get("session_id") != session_id or state.get("identity") != identity or state.get("speaker") != speaker:
                    continue
                if normalized_device_id and state.get("device_id") != normalized_device_id:
                    continue
                state["connected"] = False
                state["last_seen"] = time()

            shared_state = self.shared_sessions.get(shared_key)
            if shared_state and normalized_device_id and normalized_device_id in shared_state.get("devices", {}):
                shared_state["devices"][normalized_device_id]["connected"] = False
                shared_state["devices"][normalized_device_id]["last_seen"] = time()

    def disconnect_session(self, session_id: str, identity: str) -> None:
        """Mark every stream in a session disconnected (e.g. when a WebSocket closes)."""
        with self._lock:
            shared_key = self._shared_key(session_id, identity)
            for state in self.sessions.values():
                if state.get("session_id") == session_id and state.get("identity") == identity:
                    state["connected"] = False
                    state["last_seen"] = time()
            shared_state = self.shared_sessions.get(shared_key)
            if shared_state:
                for device_state in shared_state.get("devices", {}).values():
                    device_state["connected"] = False
                    device_state["last_seen"] = time()
                shared_state["last_seen"] = time()

    def snapshot(self) -> dict:
        self.cleanup()
        with self._lock:
            # Return a shallow copy so metrics readers can iterate safely while
            # other threads bind/cleanup — avoids "dict changed size during iteration".
            return dict(self.sessions)

    def record_turn(
        self,
        session_id: str,
        identity: str,
        speaker: str,
        source_text: str,
        translated_text: str,
        semantic_context: dict,
        device_id: str | None = None,
        speaker_label: str | None = None,
    ) -> dict:
        with self._lock:
            shared_key = self._shared_key(session_id, identity)
            shared_state = self.shared_sessions.get(shared_key) or self._new_shared_state(session_id, identity)
            speaker_profile = shared_state.setdefault("speakers", {}).get(speaker, {})
            label = speaker_label or speaker_profile.get("speaker_label") or speaker
            shared_state["history"].append({
                "speaker": speaker,
                "speaker_label": label,
                "device_id": normalize_device_id(device_id) if device_id else None,
                "source_text": source_text,
                "translated_text": translated_text,
                "semantic_context": semantic_context,
                "created_at": time(),
            })
            shared_state["history"] = shared_state["history"][-get_session_history_limit():]
            shared_state["last_seen"] = time()
            self.shared_sessions[shared_key] = shared_state
            return shared_state

    def next_auto_speaker(self, session_id: str, identity: str) -> str:
        with self._lock:
            shared_state = self.shared_sessions.get(self._shared_key(session_id, identity))
            if not shared_state:
                return "person-1"
            used_indexes = [
                int(profile.get("speaker_index", 0))
                for profile in shared_state.get("speakers", {}).values()
                if str(profile.get("speaker_index", "")).isdigit()
            ]
            return f"person-{(max(used_indexes) + 1) if used_indexes else 1}"

    def active_stream_count(self, identity: str) -> int:
        self.cleanup()
        with self._lock:
            return len([
                session
                for session in self.sessions.values()
                if session.get("identity") == identity and session.get("connected")
            ])

    def cleanup(self) -> None:
        now = time()
        ttl = get_session_ttl_seconds()
        with self._lock:
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

    def reset_all(self) -> None:
        """Clear all in-memory session state (test isolation)."""
        with self._lock:
            self.sessions.clear()
            self.shared_sessions.clear()


session_registry = SessionRegistry()
