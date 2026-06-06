import re
from threading import RLock
from time import time
from typing import Any, Dict, Optional


class SpeakerMemory:
    def __init__(self):
        self.speakers: Dict[str, Dict[str, Any]] = {}
        self._lock = RLock()

    def register(self, speaker_id: str, language: Optional[str] = None):
        with self._lock:
            if speaker_id not in self.speakers:
                self.speakers[speaker_id] = {
                    "language": language,
                    "history": [],
                    "turns": 0,
                    "last_seen": time(),
                }
            elif language and not self.speakers[speaker_id].get("language"):
                self.speakers[speaker_id]["language"] = language
            if speaker_id in self.speakers:
                self.speakers[speaker_id]["last_seen"] = time()

    def add_message(self, speaker_id: str, text: str):
        self.register(speaker_id)
        with self._lock:
            profile = self.speakers[speaker_id]
            profile["history"].append(str(text or "").strip())
            profile["history"] = [item for item in profile["history"] if item][-10:]
            profile["turns"] = int(profile.get("turns") or 0) + 1
            profile["last_seen"] = time()

    def get_language(self, speaker_id: str) -> Optional[str]:
        with self._lock:
            return self.speakers.get(speaker_id, {}).get("language")

    def get_context(self, speaker_id: str) -> Dict[str, Any]:
        with self._lock:
            profile = self.speakers.get(speaker_id, {})
            return {
                **profile,
                "history": list(profile.get("history", [])),
            }


ES_WORDS = {"el", "la", "los", "las", "de", "que", "y", "en", "con", "para", "por", "hola", "gracias"}
FR_WORDS = {"le", "la", "les", "des", "et", "de", "bonjour", "avec", "pour", "merci"}
HT_WORDS = {
    "mwen", "ou", "li", "nou", "yo", "se", "pa", "nan", "ak", "pou", "ki", "sa", "gen", "ka", "ap", "te",
    "la", "wi", "non", "mesi", "mèsi", "bonjou", "sak", "kijan", "kote", "jan", "poukisa", "bezwen", "ed", "èd",
}


def normalize_language_code(code: str | None) -> str:
    return str(code or "en").lower().split("-")[0]


def language_pair_has_ht(source_language: str | None, target_language: str | None) -> bool:
    return normalize_language_code(source_language) == "ht" or normalize_language_code(target_language) == "ht"


def resolve_whisper_language(
    source_language: str | None,
    target_language: str | None,
    *,
    stt_only: bool = False,
) -> str | None:
    """Return Whisper language code, or None to auto-detect."""

    if stt_only or language_pair_has_ht(source_language, target_language):
        return None
    lang = normalize_language_code(source_language)
    if lang in {"auto", "detect"}:
        return None
    return lang


def detect_language_in_pair(text: str, source_language: str | None, target_language: str | None) -> str:
    src = normalize_language_code(source_language)
    tgt = normalize_language_code(target_language)
    candidates = [code for code in (src, tgt) if code not in {"auto", "detect"}]
    detected = detect_language_heuristic(text)
    if detected in candidates:
        return detected
    return candidates[0] if candidates else "en"


def detect_language_heuristic(text: str) -> str:
    t = (text or "").lower()
    tokens = set(re.findall(
        r"[a-z\u00e0\u00e2\u00e4\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f6\u00f9\u00fb\u00fc\u00ff\u0153\u00f1\u00e1\u00ed\u00f3\u00fa]+",
        t,
    ))
    ht_votes = len(tokens & HT_WORDS)
    es_votes = len(tokens & ES_WORDS)
    fr_votes = len(tokens & FR_WORDS)
    if ht_votes >= 1 and ht_votes >= max(es_votes, fr_votes):
        return "ht"
    if re.search(r"[\u00e1\u00e9\u00ed\u00f3\u00fa\u00f1\u00bf\u00a1]", t):
        return "es"
    if re.search(r"[\u00e0\u00e2\u00e4\u00e7\u00e9\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f6\u00f9\u00fb\u00fc\u00ff\u0153]", t):
        return "fr"
    if es_votes > fr_votes and es_votes >= 1:
        return "es"
    if fr_votes > es_votes and fr_votes >= 1:
        return "fr"
    return "en"
