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


LANGUAGE_WORDS = {
    "en": {
        "hello", "hi", "hey", "thanks", "thank", "please", "yes", "no", "good", "morning",
        "night", "how", "are", "you", "i", "we", "they", "what", "where", "when", "why",
    },
    "es": {
        "el", "la", "los", "las", "de", "que", "y", "en", "con", "para", "por", "hola",
        "gracias", "buenos", "dias", "como", "estas", "usted", "si", "no",
    },
    "ht": {
        "bonjou", "mesi", "anpil", "mwen", "ou", "nou", "yo", "kijan", "sak", "pase",
        "tanpri", "wi", "non", "byen", "zanmi", "eskize", "orevwa", "bezwen", "ed",
        "konprann", "kote", "twalet", "pale", "angle",
    },
    "it": {
        "ciao", "grazie", "prego", "buongiorno", "buonasera", "come", "stai", "sono",
        "si", "no", "per", "con", "buona", "notte", "favore", "scusi", "arrivederci",
        "perfavore", "capisco", "aiuto", "dov", "bagno", "ospedale", "taxi", "sinistra",
        "destra", "dritto", "ferma", "quanto", "costa", "parla", "inglese",
    },
    "ja": {
        "konnichiwa", "arigato", "ohayo", "oyasumi", "hai", "iie", "desu", "masu",
        "sumimasen", "gomen", "kudasai", "doko", "ikura", "tabemono", "mizu",
        "byoin", "kusuri", "taxi", "basu", "migi", "hidari", "massugu",
    },
    "ko": {
        "annyeong", "gamsa", "ne", "ani", "jebal", "mian", "eotteoke", "jinaeyo",
        "annyeonghaseyo", "gamsahabnida", "sillye", "eodi", "eolma", "bap",
        "mul", "byeongwon", "yakguk", "taeksi", "beoseu", "oreun", "oen",
    },
    "ar": {
        "marhaba", "shukran", "naam", "la", "min", "fadlik", "keef", "halak", "ana",
        "anta", "kayf",
    },
    "hi": {
        "namaste", "dhanyavad", "haan", "nahin", "kripya", "maaf", "kaise", "hain",
        "main", "aap",
    },
    "fr": {
        "le", "la", "les", "des", "et", "de", "bonjour", "bonsoir", "avec", "pour",
        "merci", "vous", "nous", "comment", "oui", "non", "bien",
    },
    "de": {
        "hallo", "danke", "bitte", "und", "ich", "du", "sie", "wir", "nicht", "guten",
        "morgen", "abend", "ja", "nein",
    },
    "pt": {
        "ola", "olá", "obrigado", "obrigada", "por", "favor", "voce", "você", "nao",
        "não", "sim", "bom", "dia", "como", "adeus", "obrigada", "preciso", "ajuda",
        "banheiro", "hospital", "taxi", "esquerda", "direita", "frente", "onde",
        "quanto", "custa", "fala", "ingles",
    },
    "nl": {
        "hallo", "dank", "bedankt", "alsjeblieft", "goed", "morgen", "avond", "ja",
        "nee", "ik", "jij", "wij", "alstublieft", "tot", "ziens", "hoe", "gaat",
        "toilet", "ziekenhuis", "taxi", "links", "rechts", "rechtdoor", "waar",
        "kost", "spreekt", "engels",
    },
    "ru": {
        "da", "net", "privet", "spasibo", "pozhaluysta", "izvinite", "kak", "dela",
        "ya", "vy", "my", "gde", "eto", "pomogite", "vrach", "politsiya", "bolnitsa",
        "taksi", "nalevo", "napravo", "pryamo", "skolko", "govorite", "angliyski",
    },
    "zh": {
        "ni", "hao", "ma", "wo", "shi", "de", "bu", "xie", "xie", "qing", "zai",
        "jian", "nimen", "women",
    },
}

SCRIPT_LANGUAGES = (
    ("ja", re.compile(r"[\u3040-\u30ff]")),
    ("ko", re.compile(r"[\uac00-\ud7af]")),
    ("ar", re.compile(r"[\u0600-\u06ff]")),
    ("hi", re.compile(r"[\u0900-\u097f]")),
    ("ru", re.compile(r"[\u0400-\u04ff]")),
    ("zh", re.compile(r"[\u4e00-\u9fff]")),
)

ACCENT_LANGUAGES = (
    ("es", re.compile(r"[\u00e1\u00ed\u00f3\u00fa\u00f1\u00bf\u00a1]")),
    ("pt", re.compile(r"[\u00e3\u00f5]")),
    ("de", re.compile(r"[\u00e4\u00f6\u00fc\u00df]")),
    ("fr", re.compile(r"[\u00e0\u00e2\u00e7\u00e8\u00ea\u00eb\u00ee\u00ef\u00f4\u00f9\u00fb\u00fc\u00ff\u0153]")),
    ("ht", re.compile(r"[\u00e8\u00f2\u00ea\u00e0\u00e9]")),
)


def _language_code(language: str | None) -> str:
    return str(language or "").strip().lower().replace("_", "-").split("-")[0] or "en"


def detect_language_with_confidence(text: str) -> Dict[str, Any]:
    t = (text or "").lower()
    if not t.strip():
        return {"language": "en", "confidence": 0.0, "reason": "empty"}

    for language, pattern in SCRIPT_LANGUAGES:
        if pattern.search(t):
            return {"language": language, "confidence": 0.96, "reason": "script"}

    tokens = set(re.findall(r"[a-z\u00c0-\u024f]+", t))
    ht_markers = len(tokens & LANGUAGE_WORDS["ht"])
    if ht_markers >= 2:
        return {"language": "ht", "confidence": 0.9, "reason": "creole_markers"}

    for language, pattern in ACCENT_LANGUAGES:
        if pattern.search(t):
            return {"language": language, "confidence": 0.84, "reason": "accent"}

    scores = {
        language: len(tokens & words)
        for language, words in LANGUAGE_WORDS.items()
    }
    best_language, best_score = max(scores.items(), key=lambda item: item[1])
    sorted_scores = sorted(scores.values(), reverse=True)
    runner_up = sorted_scores[1] if len(sorted_scores) > 1 else 0
    if best_score > 0 and best_score > runner_up:
        confidence = min(0.94, 0.72 + (best_score * 0.08))
        return {"language": best_language, "confidence": confidence, "reason": "word_votes"}
    if best_score > 0:
        return {"language": best_language, "confidence": 0.5, "reason": "ambiguous_words"}
    return {"language": "en", "confidence": 0.42, "reason": "default"}


def detect_language_heuristic(text: str) -> str:
    return str(detect_language_with_confidence(text).get("language") or "en")


def resolve_barrier_route(
    text: str,
    primary_source_language: str,
    primary_target_language: str,
    *,
    enabled: bool = True,
) -> Dict[str, Any]:
    """Resolve the active speaker and translation direction for a two-language conversation.

    Barrier mode treats the configured source/target languages as the two sides
    of a conversation. The detected source language decides which side spoke
    and automatically flips the translation direction for the listener.
    """

    primary_source = _language_code(primary_source_language)
    primary_target = _language_code(primary_target_language)
    detection = detect_language_with_confidence(text)
    detected = _language_code(detection.get("language"))
    confidence = float(detection.get("confidence") or 0.0)
    in_pair = detected in {primary_source, primary_target}
    if not enabled:
        detected = primary_source
        confidence = 1.0
        in_pair = True

    if enabled and in_pair and detected == primary_target and primary_source != primary_target:
        source_language = primary_target
        target_language = primary_source
        speaker_index = 2
    else:
        source_language = primary_source
        target_language = primary_target
        speaker_index = 1

    route_confidence = confidence if in_pair else min(confidence, 0.45)
    return {
        "barrier_mode": bool(enabled),
        "source_language": source_language,
        "target_language": target_language,
        "detected_language": detected,
        "detected_language_confidence": round(confidence, 3),
        "route_confidence": round(route_confidence, 3),
        "route_reason": detection.get("reason"),
        "needs_confirmation": bool(enabled and (not in_pair or route_confidence < 0.5)),
        "speaker": f"person-{speaker_index}",
        "speaker_label": f"Person {speaker_index}",
        "speaker_index": speaker_index,
        "listener_label": f"Person {1 if speaker_index == 2 else 2}",
        "detection": "language_route" if enabled else "manual",
    }
