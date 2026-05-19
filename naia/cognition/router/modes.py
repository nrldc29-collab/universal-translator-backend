"""Cognitive operating modes for NAIA routing."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class CognitiveMode(StrEnum):
    REFLEX = "REFLEX"
    CONVERSATIONAL = "CONVERSATIONAL"
    ANALYTICAL = "ANALYTICAL"
    RESEARCH = "RESEARCH"
    EXECUTION = "EXECUTION"
    HIGH_RISK = "HIGH_RISK"


class VerificationLevel(StrEnum):
    NONE = "NONE"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    STRICT = "STRICT"


class ResponsePriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"


class CognitiveModeProfile(BaseModel):
    mode: CognitiveMode
    description: str
    default_reasoning_depth: int
    default_tool_access: bool
    default_memory_access: bool
    default_reflection_enabled: bool
    default_verification_level: VerificationLevel
    default_response_priority: ResponsePriority


MODE_PROFILES: dict[CognitiveMode, CognitiveModeProfile] = {
    CognitiveMode.REFLEX: CognitiveModeProfile(
        mode=CognitiveMode.REFLEX,
        description="Fast response path for greetings and tiny requests.",
        default_reasoning_depth=1,
        default_tool_access=False,
        default_memory_access=False,
        default_reflection_enabled=False,
        default_verification_level=VerificationLevel.NONE,
        default_response_priority=ResponsePriority.NORMAL,
    ),
    CognitiveMode.CONVERSATIONAL: CognitiveModeProfile(
        mode=CognitiveMode.CONVERSATIONAL,
        description="Balanced interaction path for normal conversation.",
        default_reasoning_depth=2,
        default_tool_access=False,
        default_memory_access=False,
        default_reflection_enabled=False,
        default_verification_level=VerificationLevel.LOW,
        default_response_priority=ResponsePriority.NORMAL,
    ),
    CognitiveMode.ANALYTICAL: CognitiveModeProfile(
        mode=CognitiveMode.ANALYTICAL,
        description="Deeper reasoning path for analysis, strategy, and design.",
        default_reasoning_depth=4,
        default_tool_access=False,
        default_memory_access=True,
        default_reflection_enabled=True,
        default_verification_level=VerificationLevel.MEDIUM,
        default_response_priority=ResponsePriority.NORMAL,
    ),
    CognitiveMode.RESEARCH: CognitiveModeProfile(
        mode=CognitiveMode.RESEARCH,
        description="Retrieval and verification oriented path for research.",
        default_reasoning_depth=4,
        default_tool_access=False,
        default_memory_access=True,
        default_reflection_enabled=True,
        default_verification_level=VerificationLevel.HIGH,
        default_response_priority=ResponsePriority.NORMAL,
    ),
    CognitiveMode.EXECUTION: CognitiveModeProfile(
        mode=CognitiveMode.EXECUTION,
        description="Tool-enabled path for coding and controlled execution.",
        default_reasoning_depth=3,
        default_tool_access=True,
        default_memory_access=False,
        default_reflection_enabled=False,
        default_verification_level=VerificationLevel.MEDIUM,
        default_response_priority=ResponsePriority.HIGH,
    ),
    CognitiveMode.HIGH_RISK: CognitiveModeProfile(
        mode=CognitiveMode.HIGH_RISK,
        description="Constrained path with stronger verification and approval.",
        default_reasoning_depth=3,
        default_tool_access=False,
        default_memory_access=False,
        default_reflection_enabled=True,
        default_verification_level=VerificationLevel.STRICT,
        default_response_priority=ResponsePriority.HIGH,
    ),
}


class CognitiveModeSelector:
    def select_mode(self, intent: str, complexity: str, context: dict | None = None) -> str:
        if not intent or not complexity:
            raise ValueError("intent and complexity are required")
        if complexity in {"HIGH", "EXTREME"}:
            return "DEEP"
        if intent in {"coding", "automation"}:
            return "STANDARD"
        return "FAST"
