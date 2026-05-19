import json
import logging
from pathlib import Path
from threading import RLock
from typing import Any, Dict

logger = logging.getLogger("anai_translator")


DEFAULT_PROFILE = {
    "preferred_languages": [],
    "conversation_style": "natural",  # natural | formal | concise | literal
    "partial_translation": True,
    "voice": "default",
    "history": [],  # list of {type, source, translated}
}


class ProfileMemory:
    def __init__(self, storage_path: str | None = None):
        self._path = Path(storage_path or "models/profiles.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self.profiles: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()
        self._load()

    def _load(self) -> None:
        try:
            if self._path.is_file():
                self.profiles = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            self.profiles = {}

    def _save(self) -> None:
        try:
            temp_path = self._path.with_suffix(f"{self._path.suffix}.tmp")
            temp_path.write_text(json.dumps(self.profiles, ensure_ascii=False, indent=2), encoding="utf-8")
            temp_path.replace(self._path)
        except (OSError, PermissionError) as exc:
            logger.warning("profile_memory_save_failed path=%s error=%s", self._path, exc)

    def get(self, user_id: str) -> Dict[str, Any]:
        with self._lock:
            data = self.profiles.get(user_id)
            if not data:
                data = {**DEFAULT_PROFILE, "preferred_languages": [], "history": []}
                self.profiles[user_id] = data
                self._save()
            return {**data, "preferred_languages": list(data.get("preferred_languages") or []), "history": list(data.get("history") or [])}

    def save(self, user_id: str, data: Dict[str, Any]) -> None:
        with self._lock:
            self.profiles[user_id] = {
                **DEFAULT_PROFILE,
                **data,
                "preferred_languages": list(data.get("preferred_languages") or []),
                "history": list(data.get("history") or [])[-50:],
            }
            self._save()
