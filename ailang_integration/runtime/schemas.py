"""Type-Safe Schemas — Validated AI output structures.

Provides schema definitions that ensure AI agent outputs conform
to expected structures, catching errors before they propagate.

Usage:
    from ailang_integration.runtime.schemas import TranslationResult, QualityReview

    result = TranslationResult.validate(agent_output)
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


@dataclass
class TranslationResult:
    """Schema for a complete translation result."""
    translated_text: str = ""
    source_text: str = ""
    source_lang: str = "en"
    target_lang: str = "es"
    domain: str = "general"
    formality: str = "neutral"
    model_used: str = "fast"
    confidence: float = 0.0
    require_confirmation: bool = False
    idioms_detected: List[str] = field(default_factory=list)
    terminology_overrides: List[Dict[str, str]] = field(default_factory=list)

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "TranslationResult":
        """Validate and coerce a dict into a TranslationResult."""
        return cls(
            translated_text=str(data.get("translated_text", "")),
            source_text=str(data.get("source_text", data.get("text", ""))),
            source_lang=str(data.get("source_lang", "en")),
            target_lang=str(data.get("target_lang", "es")),
            domain=str(data.get("domain", data.get("analysis", {}).get("domain", "general"))),
            formality=str(data.get("formality", data.get("analysis", {}).get("formality", "neutral"))),
            model_used=str(data.get("model_used", data.get("analysis", {}).get("model", "fast"))),
            confidence=float(data.get("confidence", 0.0)),
            require_confirmation=bool(data.get("require_confirmation", False)),
            idioms_detected=list(data.get("idioms_detected", [])),
            terminology_overrides=list(data.get("terminology_overrides", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class QualityReview:
    """Schema for quality check results."""
    score: int = 7
    passed: bool = True
    critical: bool = False
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "QualityReview":
        if data is None:
            return cls()
        return cls(
            score=int(data.get("score", 7)),
            passed=bool(data.get("pass", data.get("passed", True))),
            critical=bool(data.get("critical", False)),
            issues=list(data.get("issues", [])),
            suggestions=list(data.get("suggestions", [])),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EmotionAnalysis:
    """Schema for emotion detection results."""
    emotion: str = "neutral"
    confidence: float = 0.8
    keyword_hits: int = 0

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "EmotionAnalysis":
        return cls(
            emotion=str(data.get("emotion", "neutral")),
            confidence=float(data.get("confidence", 0.8)),
            keyword_hits=int(data.get("keyword_hits", 0)),
        )


@dataclass
class TTSConfig:
    """Schema for TTS output configuration."""
    text: str = ""
    language: str = "en"
    speed: float = 1.0
    pitch_shift: int = 0
    volume: float = 1.0
    emotion: str = "neutral"
    voice_id: str = "default"
    emphasis_words: List[str] = field(default_factory=list)
    pause_between_sentences_ms: int = 200
    speaker_matched: bool = False

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "TTSConfig":
        return cls(
            text=str(data.get("text", "")),
            language=str(data.get("language", "en")),
            speed=float(data.get("speed", 1.0)),
            pitch_shift=int(data.get("pitch_shift", 0)),
            volume=float(data.get("volume", 1.0)),
            emotion=str(data.get("emotion", "neutral")),
            voice_id=str(data.get("voice_id", "default")),
            emphasis_words=list(data.get("emphasis_words", [])),
            pause_between_sentences_ms=int(data.get("pause_between_sentences_ms", 200)),
            speaker_matched=bool(data.get("speaker_matched", False)),
        )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class DialectInfo:
    """Schema for dialect detection results."""
    dialect: str = ""
    confidence: float = 0.5
    method: str = "unknown"
    markers_found: int = 0

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "DialectInfo":
        return cls(
            dialect=str(data.get("dialect", "")),
            confidence=float(data.get("confidence", 0.5)),
            method=str(data.get("method", "unknown")),
            markers_found=int(data.get("markers_found", 0)),
        )


@dataclass
class VoiceProfile:
    """Schema for voice cloning profile."""
    speaker_id: str = ""
    avg_speed: float = 1.0
    pitch_category: str = "neutral"
    energy_level: float = 0.5
    samples_analyzed: int = 0

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "VoiceProfile":
        return cls(
            speaker_id=str(data.get("speaker_id", "")),
            avg_speed=float(data.get("avg_speed", 1.0)),
            pitch_category=str(data.get("pitch_category", "neutral")),
            energy_level=float(data.get("energy_level", 0.5)),
            samples_analyzed=int(data.get("samples_analyzed", 0)),
        )


@dataclass
class PipelineStepMeta:
    """Schema for pipeline step metadata."""
    step_name: str = ""
    duration_ms: float = 0.0
    success: bool = True
    error: Optional[str] = None

    @classmethod
    def validate(cls, data: Dict[str, Any]) -> "PipelineStepMeta":
        return cls(
            step_name=str(data.get("step_name", "")),
            duration_ms=float(data.get("duration_ms", 0.0)),
            success=bool(data.get("success", True)),
            error=data.get("error"),
        )
