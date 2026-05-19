"""Routing policies that convert analysis into execution behavior."""

from __future__ import annotations

from pydantic import BaseModel, Field

from cognition.router.classifier import TaskClassification, TaskType
from cognition.router.complexity import ComplexityAssessment, ComplexityLevel
from cognition.router.modes import (
    MODE_PROFILES,
    CognitiveMode,
    ResponsePriority,
    VerificationLevel,
)
from cognition.router.risk import RiskAssessment, RiskLevel


class CognitiveBudget(BaseModel):
    max_time_seconds: float
    max_tokens: int
    max_tool_calls: int
    max_reflections: int
    max_agents: int


class RoutingPolicyResult(BaseModel):
    mode: CognitiveMode
    reasoning_depth: int = Field(ge=1, le=5)
    reflection_enabled: bool
    memory_enabled: bool
    tool_access: bool
    verification_level: VerificationLevel
    agent_activation: bool
    response_priority: ResponsePriority
    execution_budget: CognitiveBudget
    policy_triggers: list[str] = Field(default_factory=list)


class RoutingPolicies:
    """Stable policy layer for cognitive execution plans."""

    def apply(
        self,
        classification: TaskClassification,
        complexity: ComplexityAssessment,
        risk: RiskAssessment,
    ) -> RoutingPolicyResult:
        triggers: list[str] = []
        mode = complexity.recommended_mode

        if classification.task_type == TaskType.RESEARCH:
            mode = CognitiveMode.RESEARCH
            triggers.append("research enables retrieval-oriented mode")
        elif (
            classification.task_type in {TaskType.CODING, TaskType.AUTOMATION}
            or classification.requires_tools
        ):
            mode = CognitiveMode.EXECUTION
            triggers.append("execution task enables controlled tool mode")
        elif complexity.complexity == ComplexityLevel.MINIMAL:
            mode = CognitiveMode.REFLEX
            triggers.append("minimal complexity disables extra cognition")
        elif complexity.complexity in {ComplexityLevel.HIGH, ComplexityLevel.EXTREME}:
            mode = CognitiveMode.ANALYTICAL
            triggers.append("high complexity enables analytical mode")

        if risk.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            mode = CognitiveMode.HIGH_RISK
            triggers.append("high risk overrides mode selection")

        profile = MODE_PROFILES[mode]
        reasoning_depth = max(
            profile.default_reasoning_depth,
            complexity.estimated_reasoning_depth,
        )
        reflection_enabled = profile.default_reflection_enabled
        memory_enabled = profile.default_memory_access or classification.requires_memory
        tool_access = (
            profile.default_tool_access or classification.requires_tools
        ) and risk.risk not in {RiskLevel.HIGH, RiskLevel.CRITICAL}
        verification_level = profile.default_verification_level
        response_priority = profile.default_response_priority

        if complexity.complexity == ComplexityLevel.LOW:
            reflection_enabled = False
            triggers.append("low complexity disables reflection")
        if complexity.complexity == ComplexityLevel.EXTREME:
            reasoning_depth = 5
            reflection_enabled = True
            memory_enabled = True
            triggers.append("extreme complexity expands reasoning budget")

        if risk.risk == RiskLevel.MEDIUM:
            verification_level = max_verification(
                verification_level, VerificationLevel.HIGH
            )
            triggers.append("medium risk increases verification")
        elif risk.risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            verification_level = VerificationLevel.STRICT
            tool_access = False
            response_priority = ResponsePriority.HIGH
            triggers.append("high risk disables tool access pending approval")

        agent_activation = False
        triggers.append("agent activation remains disabled in step 3")

        return RoutingPolicyResult(
            mode=mode,
            reasoning_depth=reasoning_depth,
            reflection_enabled=reflection_enabled,
            memory_enabled=memory_enabled,
            tool_access=tool_access,
            verification_level=verification_level,
            agent_activation=agent_activation,
            response_priority=response_priority,
            execution_budget=self._budget_for(
                complexity.complexity,
                risk.risk,
                tool_access=tool_access,
                reflection_enabled=reflection_enabled,
            ),
            policy_triggers=triggers,
        )

    def _budget_for(
        self,
        complexity: ComplexityLevel,
        risk: RiskLevel,
        *,
        tool_access: bool,
        reflection_enabled: bool,
    ) -> CognitiveBudget:
        base = {
            ComplexityLevel.MINIMAL: CognitiveBudget(
                max_time_seconds=2,
                max_tokens=500,
                max_tool_calls=0,
                max_reflections=0,
                max_agents=0,
            ),
            ComplexityLevel.LOW: CognitiveBudget(
                max_time_seconds=5,
                max_tokens=1200,
                max_tool_calls=0,
                max_reflections=0,
                max_agents=0,
            ),
            ComplexityLevel.MEDIUM: CognitiveBudget(
                max_time_seconds=10,
                max_tokens=2400,
                max_tool_calls=2,
                max_reflections=1,
                max_agents=0,
            ),
            ComplexityLevel.HIGH: CognitiveBudget(
                max_time_seconds=15,
                max_tokens=4000,
                max_tool_calls=3,
                max_reflections=2,
                max_agents=0,
            ),
            ComplexityLevel.EXTREME: CognitiveBudget(
                max_time_seconds=25,
                max_tokens=7000,
                max_tool_calls=4,
                max_reflections=3,
                max_agents=0,
            ),
        }[complexity]

        if not tool_access:
            base.max_tool_calls = 0
        elif base.max_tool_calls == 0:
            base.max_tool_calls = 1
        if not reflection_enabled:
            base.max_reflections = 0
        if risk in {RiskLevel.HIGH, RiskLevel.CRITICAL}:
            base.max_tool_calls = 0
            base.max_reflections = min(base.max_reflections, 1)
            base.max_time_seconds = min(base.max_time_seconds, 10)
        return base


def max_verification(
    current: VerificationLevel, requested: VerificationLevel
) -> VerificationLevel:
    order = [
        VerificationLevel.NONE,
        VerificationLevel.LOW,
        VerificationLevel.MEDIUM,
        VerificationLevel.HIGH,
        VerificationLevel.STRICT,
    ]
    return order[max(order.index(current), order.index(requested))]
