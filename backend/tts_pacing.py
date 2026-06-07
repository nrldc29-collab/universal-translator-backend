"""
Advanced TTS pacing module with emotional nuance and prosody control.
Implements frontier-level emotional awareness for natural-sounding speech.
"""

import math
import re
from typing import Dict, List, Optional
from enum import Enum


class EmotionType(str, Enum):
    """Supported emotion types for TTS."""
    NEUTRAL = "neutral"
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    EXCITED = "excited"
    APOLOGETIC = "apologetic"
    CURIOUS = "curious"
    SERIOUS = "serious"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    FRUSTRATED = "frustrated"


class ProsodyFeatures:
    """Prosodic features for fine-grained emotional control."""
    
    def __init__(
        self,
        pitch: float = 1.0,  # 0.5 to 2.0 (relative to neutral)
        speed: float = 1.0,   # 0.5 to 2.0 (relative to neutral)
        energy: float = 1.0,  # 0.5 to 2.0 (relative to neutral)
        pause_duration: float = 0.25,  # seconds
        emphasis_words: Optional[List[str]] = None,
    ):
        self.pitch = max(0.5, min(2.0, pitch))
        self.speed = max(0.5, min(2.0, speed))
        self.energy = max(0.5, min(2.0, energy))
        self.pause_duration = pause_duration
        self.emphasis_words = emphasis_words or []
        
    def to_dict(self) -> Dict:
        return {
            "pitch": self.pitch,
            "speed": self.speed,
            "energy": self.energy,
            "pause_seconds": self.pause_duration,
            "emphasis_words": self.emphasis_words,
        }


# Advanced emotion detection with contextual awareness
def detect_emotion_advanced(text: str, intent: str | None = None, context: dict | None = None) -> tuple[str, float]:
    """
    Advanced emotion detection with confidence scoring.
    Returns (emotion, confidence).
    """
    normalized = text.lower()
    intent = intent or ""
    
    # Emotion keywords with weights
    emotion_patterns = {
        EmotionType.HAPPY: {
            "keywords": ["happy", "great", "excellent", "wonderful", "amazing", "fantastic", 
                        "love", "perfect", "brilliant", "joy", "delighted"],
            "weight": 1.0,
        },
        EmotionType.SAD: {
            "keywords": ["sad", "unfortunate", "terrible", "awful", "horrible", 
                        "depressed", "unhappy", "miserable", "disappointed"],
            "weight": 1.0,
        },
        EmotionType.ANGRY: {
            "keywords": ["angry", "furious", "outraged", "annoyed", "hate", 
                        "stupid", "damn", "hell", "idiot"],
            "weight": 1.2,  # Angry is easier to detect
        },
        EmotionType.EXCITED: {
            "keywords": ["excited", "awesome", "incredible", "wow", "amazing", 
                        "!", "!!", "!!!", "yay", "wohoo"],
            "weight": 1.1,
        },
        EmotionType.APOLOGETIC: {
            "keywords": ["sorry", "apologize", "forgive", "regret", "my fault", 
                        "excuse me", "pardon"],
            "weight": 1.0,
        },
        EmotionType.CURIOUS: {
            "keywords": ["?", "wonder", "curious", "what if", "how come", 
                        "why is", "tell me", "explain"],
            "weight": 0.9,
        },
        EmotionType.SERIOUS: {
            "keywords": ["must", "should", "important", "urgent", "critical", 
                        "emergency", "asap", "immediately"],
            "weight": 1.0,
        },
        EmotionType.FEARFUL: {
            "keywords": ["scared", "afraid", "terrified", "worried", "nervous", 
                        "panic", "help", "danger"],
            "weight": 1.1,
        },
        EmotionType.SURPRISED: {
            "keywords": ["surprised", "shocked", "unexpected", "whoa", 
                        "no way", "really?", "omg"],
            "weight": 1.0,
        },
        EmotionType.FRUSTRATED: {
            "keywords": ["frustrated", "annoyed", "can't", "won't work", 
                        "useless", "broken", "failed"],
            "weight": 1.1,
        },
    }
    
    # Score each emotion
    scores = {}
    for emotion, config in emotion_patterns.items():
        score = 0
        for keyword in config["keywords"]:
            if keyword in normalized:
                score += config["weight"]
        if score > 0:
            scores[emotion] = score
    
    # Check for punctuation emphasis
    if "!!!" in text or "???" in text:
        scores[EmotionType.EXCITED] = scores.get(EmotionType.EXCITED, 0) + 0.5
    
    # Check intent override
    if intent == "refusal" and EmotionType.APOLOGETIC not in scores:
        scores[EmotionType.APOLOGETIC] = 0.8
    elif intent == "question" and EmotionType.CURIOUS not in scores:
        scores[EmotionType.CURIOUS] = 0.7
    
    # Context awareness (previous emotions)
    if context and "previous_emotion" in context:
        prev_emotion = context["previous_emotion"]
        if prev_emotion in scores:
            scores[prev_emotion] *= 1.2  # Boost if emotion continues
    
    if not scores:
        return (EmotionType.NEUTRAL, 1.0)
    
    # Return emotion with highest score
    best_emotion = max(scores.items(), key=lambda x: x[1])
    confidence = min(1.0, best_emotion[1] / 3.0)  # Normalize confidence
    return (best_emotion[0], confidence)


def detect_urgency_advanced(text: str, intent: str | None = None, emotion: str | None = None) -> str:
    """
    Advanced urgency detection with emotional context.
    Returns: "low", "medium", or "high"
    """
    normalized = text.lower()
    intent = intent or ""
    emotion = emotion or ""
    
    # High urgency indicators
    high_urgency = ["emergency", "urgent", "asap", "immediately", "now", 
                   "critical", "help", "danger", "hurry", "quick"]
    if any(word in normalized for word in high_urgency):
        return "high"
    
    # Emotional urgency
    if emotion in {EmotionType.ANGRY, EmotionType.FEARFUL, EmotionType.FRUSTRATED}:
        return "high"
    
    # Intent-based urgency
    if intent in {"warning", "instruction", "refusal"}:
        return "medium"
    
    # Medium urgency indicators
    medium_urgency = ["soon", "please", "important", "need", "required"]
    if any(word in normalized for word in medium_urgency):
        return "medium"
    
    return "low"


# Advanced TTS style mapping with prosodic control
TTS_STYLE_MAP_ADVANCED = {
    EmotionType.NEUTRAL: ProsodyFeatures(
        pitch=1.0, speed=1.0, energy=1.0, pause_duration=0.25
    ),
    EmotionType.HAPPY: ProsodyFeatures(
        pitch=1.15, speed=1.1, energy=1.2, pause_duration=0.2
    ),
    EmotionType.SAD: ProsodyFeatures(
        pitch=0.85, speed=0.85, energy=0.7, pause_duration=0.4
    ),
    EmotionType.ANGRY: ProsodyFeatures(
        pitch=1.1, speed=1.15, energy=1.4, pause_duration=0.15
    ),
    EmotionType.EXCITED: ProsodyFeatures(
        pitch=1.25, speed=1.3, energy=1.5, pause_duration=0.1
    ),
    EmotionType.APOLOGETIC: ProsodyFeatures(
        pitch=0.9, speed=0.85, energy=0.8, pause_duration=0.5
    ),
    EmotionType.CURIOUS: ProsodyFeatures(
        pitch=1.05, speed=1.0, energy=1.0, pause_duration=0.3
    ),
    EmotionType.SERIOUS: ProsodyFeatures(
        pitch=0.9, speed=0.9, energy=1.1, pause_duration=0.35
    ),
    EmotionType.FEARFUL: ProsodyFeatures(
        pitch=1.2, speed=1.1, energy=1.3, pause_duration=0.2
    ),
    EmotionType.SURPRISED: ProsodyFeatures(
        pitch=1.3, speed=1.2, energy=1.4, pause_duration=0.15
    ),
    EmotionType.FRUSTRATED: ProsodyFeatures(
        pitch=1.15, speed=1.2, energy=1.35, pause_duration=0.18
    ),
}


def style_for_emotion_advanced(emotion: str, urgency: str = "low", confidence: float = 1.0) -> Dict:
    """
    Get TTS style for emotion with confidence weighting.
    """
    try:
        emotion_type = EmotionType(emotion)
    except ValueError:
        emotion_type = EmotionType.NEUTRAL
    
    base_style = TTS_STYLE_MAP_ADVANCED.get(emotion_type, TTS_STYLE_MAP_ADVANCED[EmotionType.NEUTRAL])
    
    # Adjust based on urgency
    if urgency == "high":
        base_style.speed = max(base_style.speed, 1.15)
        base_style.pause_duration = min(base_style.pause_duration, 0.2)
    elif urgency == "medium":
        base_style.speed = max(base_style.speed, 1.0)
    
    # Apply confidence weighting (blend with neutral if low confidence)
    if confidence < 0.5:
        neutral = TTS_STYLE_MAP_ADVANCED[EmotionType.NEUTRAL]
        blend_factor = confidence
        base_style.pitch = (base_style.pitch * blend_factor + neutral.pitch * (1 - blend_factor))
        base_style.speed = (base_style.speed * blend_factor + neutral.speed * (1 - blend_factor))
        base_style.energy = (base_style.energy * blend_factor + neutral.energy * (1 - blend_factor))
    
    return base_style.to_dict()


def apply_human_pauses_advanced(text: str, emotion: str, intent: str | None = None) -> List[str]:
    """
    Apply human-like pauses based on emotion and sentence structure.
    Returns list of text segments with appropriate pause markers.
    """
    # Base pause token
    if emotion == EmotionType.APOLOGETIC:
        pause_token = "... "
    elif emotion == EmotionType.EXCITED:
        pause_token = "! "
    elif emotion == EmotionType.ANGRY:
        pause_token = ". "
    else:
        pause_token = " "
    
    # Split by sentence endings
    parts = [part.strip() for part in re.split(r"(?<=[.!?;:])\s+", text.strip()) if part.strip()]
    
    if not parts:
        return [text]
    
    # Add emotional pauses
    segments = []
    for i, part in enumerate(parts):
        # Add pause before part (except first)
        if i > 0:
            segments.append(pause_token)
        
        # Emphasize certain words based on emotion
        if emotion == EmotionType.ANGRY:
            # Emphasize negative words
            emphasized = re.sub(r"\b(never|no|not|can't|won't|don't)\b", r"**\1**", part, flags=re.IGNORECASE)
            segments.append(emphasized)
        elif emotion == EmotionType.EXCITED:
            # Add excitement markers
            if i == len(parts) - 1:  # Last part
                segments.append(part + "!")
            else:
                segments.append(part)
        else:
            segments.append(part)
    
    return segments


def build_tts_pacing_advanced(
    text: str,
    intent: str | None = None,
    urgency: str | None = None,
    context: dict | None = None,
) -> dict:
    """
    Build advanced TTS pacing with full emotional nuance.
    This is frontier-level TTS control.
    """
    # Detect emotion with confidence
    emotion, confidence = detect_emotion_advanced(text, intent, context)
    
    # Detect urgency with emotional context
    resolved_urgency = urgency or detect_urgency_advanced(text, intent, emotion)
    
    # Get TTS style with confidence weighting
    style = style_for_emotion_advanced(emotion, resolved_urgency, confidence)
    
    # Apply human-like pauses
    segments = apply_human_pauses_advanced(text, emotion, intent)
    
    return {
        "text": text,
        "emotion": emotion,
        "emotion_confidence": confidence,
        "intent": intent or "statement",
        "urgency": resolved_urgency,
        "style": style,
        "segments": segments,
        "pause_between_segments": style["pause_seconds"],
    }


# Backward compatibility
def detect_emotion(text: str, intent: str | None = None) -> str:
    emotion, _ = detect_emotion_advanced(text, intent)
    return emotion


def detect_urgency(text: str, intent: str | None = None) -> str:
    return detect_urgency_advanced(text, intent)


TTS_STYLE_MAP = {
    # Slightly slower / warmer than flat 1.0 — reads more like conversation.
    "neutral": {"speed": 0.94, "pitch": 0.98, "pause_seconds": 0.32, "tone": "warm"},
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
    return style


def apply_human_pauses(text: str, emotion: str) -> list[str]:
    pause_token = "... " if emotion == "apologetic" else " "
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


def _neural_minimal_prosody() -> bool:
    """Edge/Google neural audio is already lifelike — avoid stacking slow/warm filters."""
    import os
    return os.getenv("TTS_NEURAL_MINIMAL_PROCESSING", "1").strip().lower() not in {
        "0", "false", "no", "off",
    }


def emotion_config_from_style(style=None):
    if not style:
        return natural_baseline_emotion_config()
    import math
    config = dict(natural_baseline_emotion_config())
    neural = _neural_minimal_prosody()
    speed = style.get("speed")
    if isinstance(speed, (int, float)) and speed > 0:
        if not neural or abs(float(speed) - 1.0) > 0.08:
            config["speed"] = float(speed)
    pitch = style.get("pitch")
    if isinstance(pitch, (int, float)) and pitch > 0:
        if not neural or abs(float(pitch) - 1.0) > 0.05:
            config["pitch_shift"] = round(12.0 * math.log2(float(pitch)), 3)
    energy = style.get("energy")
    if isinstance(energy, (int, float)) and energy > 0:
        config["volume"] = float(energy)
    return config


def natural_baseline_emotion_config() -> dict:
    """Conversational defaults applied when no AILang emotion is present."""
    import os
    if _neural_minimal_prosody():
        return {"speed": 1.0, "pitch_shift": 0, "volume": 1.0}
    try:
        speed = float(os.getenv("TTS_NATURAL_SPEED", "0.94"))
    except (TypeError, ValueError):
        speed = 0.94
    try:
        pitch_shift = float(os.getenv("TTS_NATURAL_PITCH_SHIFT", "-0.6"))
    except (TypeError, ValueError):
        pitch_shift = -0.6
    return {"speed": max(0.5, min(1.5, speed)), "pitch_shift": pitch_shift, "volume": 1.0}


def resolve_tts_emotion_config(text: str, emotion_config: dict | None = None) -> dict:
    """Merge pacing-derived prosody with any explicit emotion config."""
    pacing = build_tts_pacing(text or "")
    resolved = emotion_config_from_style(pacing.get("style"))
    if emotion_config:
        merged = dict(emotion_config)
        if _neural_minimal_prosody():
            for key in ("speed", "pitch_shift", "volume"):
                value = merged.get(key)
                if key == "speed" and isinstance(value, (int, float)) and 0.92 <= float(value) <= 1.08:
                    merged.pop(key, None)
                elif key == "pitch_shift" and isinstance(value, (int, float)) and abs(float(value)) <= 1.5:
                    merged.pop(key, None)
                elif key == "volume" and isinstance(value, (int, float)) and 0.95 <= float(value) <= 1.05:
                    merged.pop(key, None)
        resolved.update(merged)
    return resolved
