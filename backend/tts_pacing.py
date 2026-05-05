import re


def detect_emotion(text: str, intent: str | None = None) -> str:
    normalized = text.lower()
    intent = intent or ""
    if "sorry" in normalized or "apolog" in normalized or intent == "refusal":
        return "apologetic"
    if "urgent" in normalized or "emergency" in normalized or "now" in normalized:
        return "serious"
    if "!" in text:
        return "excited"
    if "?" in text or intent == "question":
        return "curious"
    return "neutral"


def detect_urgency(text: str, intent: str | None = None) -> str:
    normalized = text.lower()
    intent = intent or ""
    if any(word in normalized for word in ["emergency", "urgent", "hurry", "immediately", "now"]):
        return "high"
    if intent in {"instruction", "warning"}:
        return "medium"
    return "low"


TTS_STYLE_MAP = {
    "neutral": {"speed": 1.0, "pitch": 1.0, "pause_seconds": 0.25, "tone": "flat"},
    "apologetic": {"speed": 0.85, "pitch": 0.95, "pause_seconds": 0.5, "tone": "soft"},
    "excited": {"speed": 1.2, "pitch": 1.1, "pause_seconds": 0.15, "tone": "energetic"},
    "serious": {"speed": 0.9, "pitch": 0.9, "pause_seconds": 0.4, "tone": "deliberate"},
    "curious": {"speed": 1.05, "pitch": 1.05, "pause_seconds": 0.25, "tone": "questioning"},
}


def style_for_emotion(emotion: str, urgency: str = "low") -> dict:
    style = dict(TTS_STYLE_MAP.get(emotion, TTS_STYLE_MAP["neutral"]))
    if urgency == "high":
        style["speed"] = max(style["speed"], 1.15)
        style["pause_seconds"] = min(style["pause_seconds"], 0.2)
    elif urgency == "medium":
        style["speed"] = max(style["speed"], 1.0)
    return style


def apply_human_pauses(text: str, emotion: str) -> list[str]:
    pause_token = " ... " if emotion == "apologetic" else " "
    parts = [part.strip() for part in re.split(r"(?<=[.!?;:])\s+", text.strip()) if part.strip()]
    if not parts:
        return [text]
    if emotion == "apologetic" and len(parts) == 1:
        soft_parts = re.split(r"\s+(?=(?:I|we|you|they|he|she|it)\b)", parts[0], maxsplit=1, flags=re.IGNORECASE)
        return [part.strip() for part in soft_parts if part.strip()]
    return [pause_token.join([part]) for part in parts]


def build_tts_pacing(text: str, intent: str | None = None, urgency: str | None = None) -> dict:
    emotion = detect_emotion(text, intent)
    resolved_urgency = urgency or detect_urgency(text, intent)
    style = style_for_emotion(emotion, resolved_urgency)
    return {
        "text": text,
        "emotion": emotion,
        "intent": intent or "statement",
        "urgency": resolved_urgency,
        "style": style,
        "segments": apply_human_pauses(text, emotion),
    }
