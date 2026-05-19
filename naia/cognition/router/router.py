"""Main cognitive routing engine."""

from __future__ import annotations

import time
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from cognition.router.classifier import TaskClassification, TaskClassifier
from cognition.router.complexity import ComplexityAssessment, ComplexityEstimator
from cognition.router.modes import CognitiveMode, ResponsePriority, VerificationLevel
from cognition.router.policies import CognitiveBudget, RoutingPolicies
from cognition.router.reasoning import ReasoningModule, ReasoningResult
from cognition.router.risk import RiskAssessment, RiskEngine
from memory.rag_retrieval import RAGRetriever


class RoutePlan(BaseModel):
    mode: CognitiveMode
    task_type: str
    intent: str
    reasoning_depth: int = Field(ge=1, le=5)
    reflection_enabled: bool
    memory_enabled: bool
    tool_access: bool
    verification_level: VerificationLevel
    agent_activation: bool
    response_priority: ResponsePriority
    execution_budget: CognitiveBudget
    classification: TaskClassification
    complexity: ComplexityAssessment
    risk: RiskAssessment
    policy_triggers: list[str] = Field(default_factory=list)
    selected_modules: list[str] = Field(default_factory=list)
    estimated_cost: float
    latency_ms: float
    reasoning_result: ReasoningResult | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CognitiveRouter:
    """Executive cognition selector for NAIA runtime sessions."""

    def __init__(
        self,
        *,
        classifier: TaskClassifier | None = None,
        complexity_estimator: ComplexityEstimator | None = None,
        risk_engine: RiskEngine | None = None,
        policies: RoutingPolicies | None = None,
        reasoning_module: ReasoningModule | None = None,
        rag_retriever: RAGRetriever | None = None,
    ) -> None:
        self.classifier = classifier or TaskClassifier()
        self.complexity_estimator = complexity_estimator or ComplexityEstimator()
        self.risk_engine = risk_engine or RiskEngine()
        self.policies = policies or RoutingPolicies()
        self.reasoning_module = reasoning_module or ReasoningModule()
        self.rag_retriever = rag_retriever

    def route(self, user_input: str) -> RoutePlan:
        if not user_input.strip():
            raise ValueError("user_input is required")
        started = time.perf_counter()
        classification = self.classifier.classify(user_input)
        complexity = self.complexity_estimator.estimate(user_input, classification)
        risk = self.risk_engine.estimate(user_input, classification)
        policy = self.policies.apply(classification, complexity, risk)

        # Perform reasoning for ANALYTICAL mode
        reasoning_result: ReasoningResult | None = None
        if policy.mode == CognitiveMode.ANALYTICAL:
            reasoning_result = self.reasoning_module.reason(
                query=user_input,
                context={
                    "classification": classification.task_type.value,
                    "complexity": complexity.complexity.value,
                    "risk": risk.risk.value,
                },
                max_depth=policy.reasoning_depth,
            )

        latency_ms = (time.perf_counter() - started) * 1000

        return RoutePlan(
            mode=policy.mode,
            task_type=classification.task_type.value,
            intent=classification.task_type.value,
            reasoning_depth=policy.reasoning_depth,
            reflection_enabled=policy.reflection_enabled,
            memory_enabled=policy.memory_enabled,
            tool_access=policy.tool_access,
            verification_level=policy.verification_level,
            agent_activation=policy.agent_activation,
            response_priority=policy.response_priority,
            execution_budget=policy.execution_budget,
            classification=classification,
            complexity=complexity,
            risk=risk,
            policy_triggers=policy.policy_triggers,
            selected_modules=self._selected_modules(policy.mode),
            estimated_cost=self._estimate_cost(policy.execution_budget),
            latency_ms=latency_ms,
            reasoning_result=reasoning_result,
        )

    def _selected_modules(self, mode: CognitiveMode) -> list[str]:
        modules = ["runtime.pipeline", "cognition.router"]
        if mode == CognitiveMode.RESEARCH:
            if self.rag_retriever and self.rag_retriever.is_available():
                modules.append("memory.rag_retrieval")
            else:
                modules.append("memory.retriever")
        if mode == CognitiveMode.EXECUTION:
            modules.append("tools.tool_router")
        if mode == CognitiveMode.ANALYTICAL:
            modules.append("cognition.router.reasoning")
        if mode == CognitiveMode.HIGH_RISK:
            modules.append("governance.governance_hook")
        return modules

    def _estimate_cost(self, budget: CognitiveBudget) -> float:
        cost = (
            budget.max_time_seconds * 0.0005
            + budget.max_tokens * 0.000002
            + budget.max_tool_calls * 0.002
            + budget.max_reflections * 0.001
        )
        return round(cost, 4)


