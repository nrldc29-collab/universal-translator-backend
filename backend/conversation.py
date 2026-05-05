import re
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic

from backend.config import get_semantic_history_limit, get_topic_limit


@dataclass
class ArbitrationDecision:
    allowed: bool
    reason: str
    active_speaker: str | None
    playback_owner: str | None
    behavior: str = "normal"


@dataclass
class SemanticTurn:
    speaker: str
    text: str
    intent: str
    tone: str
    topics: list[str] = field(default_factory=list)


class ConversationBrain:
    def __init__(self):
        self._lock = Lock()
        self.active_speaker: str | None = None
        self.playback_owner: str | None = None
        self.turn_counter = 0
        self.active_since = 0.0
        self.playback_since = 0.0
        self.soft_overlap_seconds = 1.2
        self.interruption_grace_seconds = 0.8
        self.semantic_history: list[SemanticTurn] = []
        self.topic_counts: dict[str, int] = {}
        self.last_intent: str = "statement"
        self.conversation_mood: str = "neutral"

    def request_turn(self, speaker: str) -> ArbitrationDecision:
        with self._lock:
            now = monotonic()
            if self.playback_owner and self.playback_owner != speaker:
                playback_age = now - self.playback_since
                if playback_age >= self.interruption_grace_seconds:
                    self.active_speaker = speaker
                    self.active_since = now
                    return ArbitrationDecision(True, "Natural interruption accepted", self.active_speaker, self.playback_owner, "interruption")
                return ArbitrationDecision(False, "Briefly holding for playback", self.active_speaker, self.playback_owner, "hold")
            if self.active_speaker and self.active_speaker != speaker:
                active_age = now - self.active_since
                if active_age <= self.soft_overlap_seconds:
                    return ArbitrationDecision(True, "Soft overlap allowed", self.active_speaker, self.playback_owner, "overlap")
                self.active_speaker = speaker
                self.active_since = now
                return ArbitrationDecision(True, "Turn shifted after pause", self.active_speaker, self.playback_owner, "turn_shift")
            self.active_speaker = speaker
            self.active_since = now
            return ArbitrationDecision(True, "Turn granted", self.active_speaker, self.playback_owner, "normal")

    def begin_playback(self, speaker: str) -> ArbitrationDecision:
        with self._lock:
            self.playback_owner = speaker
            self.playback_since = monotonic()
            return ArbitrationDecision(True, "Playback started", self.active_speaker, self.playback_owner, "playback")

    def analyze_semantics(self, speaker: str, text: str) -> dict:
        with self._lock:
            intent = self._detect_intent(text)
            tone = self._detect_tone(text)
            topics = self._extract_topics(text)
            semantic_turn = SemanticTurn(speaker=speaker, text=text, intent=intent, tone=tone, topics=topics)
            self.semantic_history.append(semantic_turn)
            self.semantic_history = self.semantic_history[-get_semantic_history_limit():]

            for topic in topics:
                self.topic_counts[topic] = self.topic_counts.get(topic, 0) + 1

            self.last_intent = intent
            self.conversation_mood = self._derive_mood()
            self._prune_topics()
            return self.semantic_snapshot()

    def semantic_snapshot(self) -> dict:
        recent_topics = sorted(self.topic_counts, key=self.topic_counts.get, reverse=True)[:5]
        return {
            "last_intent": self.last_intent,
            "conversation_mood": self.conversation_mood,
            "topics": recent_topics,
            "recent_turns": [
                {
                    "speaker": turn.speaker,
                    "intent": turn.intent,
                    "tone": turn.tone,
                    "topics": turn.topics,
                }
                for turn in self.semantic_history[-4:]
            ],
        }

    def _detect_intent(self, text: str) -> str:
        lowered = text.lower().strip()
        if lowered.endswith("?") or lowered.startswith(("what", "why", "how", "when", "where", "who", "can you", "could you")):
            return "question"
        if any(word in lowered for word in ("please", "can you", "could you", "would you")):
            return "request"
        if any(word in lowered for word in ("sorry", "apologize", "my fault")):
            return "apology"
        if any(word in lowered for word in ("thanks", "thank you", "appreciate")):
            return "gratitude"
        if any(word in lowered for word in ("yes", "agree", "sure", "okay")):
            return "agreement"
        if any(word in lowered for word in ("no", "disagree", "can't", "cannot", "don't")):
            return "disagreement"
        return "statement"

    def _detect_tone(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("angry", "upset", "frustrated", "annoyed")) or "!" in text:
            return "emphatic"
        if any(word in lowered for word in ("please", "thank", "sorry", "appreciate")):
            return "polite"
        if any(word in lowered for word in ("urgent", "quickly", "now", "immediately")):
            return "urgent"
        return "neutral"

    def _extract_topics(self, text: str) -> list[str]:
        stop_words = {"the", "and", "for", "that", "this", "with", "you", "are", "was", "were", "have", "from", "your", "about"}
        words = re.findall(r"[A-Za-z][A-Za-z'-]{3,}", text.lower())
        topics = []
        for word in words:
            if word not in stop_words and word not in topics:
                topics.append(word)
        return topics[:5]

    def _derive_mood(self) -> str:
        tones = [turn.tone for turn in self.semantic_history[-5:]]
        if "urgent" in tones:
            return "urgent"
        if "emphatic" in tones:
            return "tense"
        if tones.count("polite") >= 2:
            return "polite"
        return "neutral"

    def _prune_topics(self) -> None:
        sorted_topics = sorted(self.topic_counts.items(), key=lambda item: item[1], reverse=True)
        self.topic_counts = dict(sorted_topics[:get_topic_limit()])

    def end_turn(self, speaker: str) -> ArbitrationDecision:
        with self._lock:
            if self.active_speaker == speaker:
                self.active_speaker = None
            if self.playback_owner == speaker:
                self.playback_owner = None
            self.turn_counter += 1
            return ArbitrationDecision(True, "Turn complete", self.active_speaker, self.playback_owner)

    def cancel(self, speaker: str) -> ArbitrationDecision:
        with self._lock:
            if self.active_speaker == speaker:
                self.active_speaker = None
            if self.playback_owner == speaker:
                self.playback_owner = None
            return ArbitrationDecision(True, "Turn cancelled", self.active_speaker, self.playback_owner)
