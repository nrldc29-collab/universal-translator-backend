"""Critic agent for plans, outputs, and safety checks."""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Any

from pydantic import BaseModel, Field

from agents.agent_core import Agent, AgentTaskStatus
from agents.task_graph import TaskGraph

logger = logging.getLogger(__name__)


class CriticReport(BaseModel):
    passed: bool
    issues: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)
    score: float = Field(ge=0.0, le=1.0, default=0.5)


class CriticAgent:
    HIGH_RISK_TERMS = {
        "delete everything",
        "drop production",
        "format drive",
        "send email",
        "transfer money",
        "wipe",
    }

    def __init__(
        self,
        use_claude: bool = False,
        model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """Initialize the critic agent.

        Args:
            use_claude: Whether to use Claude for criticism.
            model: Claude model to use.
        """
        self.use_claude = use_claude
        self.model = model
        self.client: Any = None

        if use_claude:
            api_key = os.getenv("ANTHROPIC_API_KEY")
            if api_key:
                try:
                    from anthropic import Anthropic
                    self.client = Anthropic(api_key=api_key)
                    logger.info("Critic agent initialized with Claude")
                except Exception as exc:  # noqa: BLE001
                    logger.warning("Failed to initialize Claude for critic: %s", exc)
                    self.client = None

    def review_plan(self, agent: Agent) -> CriticReport:
        if self.use_claude and self.client is not None:
            claude_result = self._review_plan_with_claude(agent)
            if claude_result is not None:
                return claude_result
        return self._review_plan_with_keywords(agent)

    def review_completion(self, agent: Agent) -> CriticReport:
        if self.use_claude and self.client is not None:
            claude_result = self._review_completion_with_claude(agent)
            if claude_result is not None:
                return claude_result
        return self._review_completion_with_keywords(agent)

    def _review_plan_with_claude(self, agent: Agent) -> CriticReport | None:
        """Review a plan using Claude for deeper analysis."""
        try:
            tasks_summary = "\n".join(
                f"- {task.title}: {task.description}" for task in agent.tasks
            )

            system_prompt = (
                "You are NAIA's critic agent. Review agent plans for safety, "
                "correctness, and feasibility.\n\n"
                "Evaluate the plan and identify:\n"
                "- Any safety or security concerns\n"
                "- Logical inconsistencies or missing steps\n"
                "- Overly complex or unbounded operations\n"
                "- Dependencies that might cause issues\n\n"
                "Provide your assessment as JSON with:\n"
                "- passed: true/false\n"
                "- issues: list of specific problems\n"
                "- recommendations: list of suggestions\n"
                "- score: 0.0-1.0 confidence score"
            )

            user_prompt = (
                f"Agent goal: {agent.goal}\n\nPlan:\n{tasks_summary}\n\n"
                "Review this plan and provide your assessment in JSON format."
            )

            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text
            result = _extract_json(content)
            return CriticReport(**result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude plan review failed, using keywords: %s", exc)
            return None

    def _review_completion_with_claude(self, agent: Agent) -> CriticReport | None:
        """Review completion using Claude."""
        try:
            tasks_status = "\n".join(
                f"- {task.title}: {task.status.value}" for task in agent.tasks
            )
            system_prompt = (
                "You are NAIA's critic agent. Review agent execution results.\n\n"
                "Evaluate the execution and identify:\n"
                "- Failed or blocked tasks\n"
                "- Incomplete work\n"
                "- Unexpected errors\n"
                "- Quality of the final result\n\n"
                "Provide your assessment as JSON with:\n"
                "- passed: true/false\n"
                "- issues: list of specific problems\n"
                "- score: 0.0-1.0 confidence score"
            )
            user_prompt = (
                f"Agent goal: {agent.goal}\n\n"
                f"Task execution status:\n{tasks_status}\n\n"
                "Review this execution and provide your assessment in JSON format."
            )
            response = self.client.messages.create(
                model=self.model,
                max_tokens=512,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            content = response.content[0].text
            result = _extract_json(content)
            return CriticReport(**result)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Claude completion review failed, using keywords: %s", exc)
            return None

    def _review_plan_with_keywords(self, agent: Agent) -> CriticReport:
        """Review a plan using keyword heuristics (original implementation)."""
        issues: list[str] = []
        recommendations: list[str] = []
        graph_validation = TaskGraph(tasks=agent.tasks).validate_graph()
        issues.extend(graph_validation.issues)
        if not agent.tasks:
            issues.append("agent has no tasks")
        if len(agent.tasks) > 12:
            issues.append("plan exceeds bounded task limit")
            recommendations.append("split the goal into smaller governed agents")
        lowered_goal = agent.goal.lower()
        if any(term in lowered_goal for term in self.HIGH_RISK_TERMS):
            issues.append("goal contains high-risk action language")
            recommendations.append("require explicit human approval before execution")
        return CriticReport(
            passed=not issues, issues=issues, recommendations=recommendations
        )

    def _review_completion_with_keywords(self, agent: Agent) -> CriticReport:
        """Review completion using keyword heuristics (original implementation)."""
        issues: list[str] = []
        failed = [
            task.title
            for task in agent.tasks
            if task.status in {AgentTaskStatus.FAILED, AgentTaskStatus.BLOCKED}
        ]
        incomplete = [
            task.title
            for task in agent.tasks
            if task.status
            not in {
                AgentTaskStatus.COMPLETED,
                AgentTaskStatus.SKIPPED,
                AgentTaskStatus.FAILED,
                AgentTaskStatus.BLOCKED,
            }
        ]
        if failed:
            issues.append(f"failed tasks: {', '.join(failed)}")
        if incomplete:
            issues.append(f"incomplete tasks: {', '.join(incomplete)}")
        return CriticReport(passed=not issues, issues=issues)


# ---- helpers ---------------------------------------------------------------

_JSON_OBJECT_RE = re.compile(r"\{[\s\S]*\}")


def _extract_json(text: str) -> dict[str, Any]:
    """Extract and parse the first JSON object found in ``text``.

    Looser than the version in ``models.local_client`` -- Claude often emits
    structured output wrapped in prose or markdown fences. We try the literal
    decode first, then strip code fences, then fall back to a regex search.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    stripped = text.strip()
    if stripped.startswith("```"):
        # Strip the opening fence (with or without a language tag).
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```\s*$", "", stripped)
        try:
            return json.loads(stripped)
        except json.JSONDecodeError:
            pass

    match = _JSON_OBJECT_RE.search(text)
    if match:
        return json.loads(match.group(0))
    raise ValueError(f"No JSON object found in: {text[:200]!r}")
