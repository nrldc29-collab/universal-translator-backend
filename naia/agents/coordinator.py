"""Coordinator for multiple governed agents with handoff, critique loops, and shared scratchpad."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from anthropic import Anthropic
from pydantic import BaseModel, Field

from agents.agent_core import Agent, AgentState
from agents.critic_agent import CriticAgent, CriticReport
from agents.registry import AgentRegistry

logger = logging.getLogger(__name__)


class SharedScratchpad(BaseModel):
    """Shared scratchpad for agent coordination."""

    entries: list[dict[str, Any]] = Field(default_factory=list)
    last_updated: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def add_entry(self, agent_id: str, content: str, entry_type: str = "note") -> None:
        """Add an entry to the scratchpad."""
        self.entries.append(
            {
                "agent_id": agent_id,
                "content": content,
                "entry_type": entry_type,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        )
        self.last_updated = datetime.now(timezone.utc)

    def get_context(self, agent_id: str | None = None) -> str:
        """Get context from scratchpad, optionally filtered by agent."""
        if agent_id:
            entries = [e for e in self.entries if e["agent_id"] == agent_id]
        else:
            entries = self.entries

        return "\n".join([
            f"[{e['entry_type']}] {e['agent_id']}: {e['content']}"
            for e in entries
        ])


class HandoffRequest(BaseModel):
    """Request for agent handoff."""

    from_agent_id: str
    to_agent_id: str
    reason: str
    context: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class CritiqueLoopConfig(BaseModel):
    """Configuration for critique loops."""

    enabled: bool = True
    max_iterations: int = 3
    critique_agent: str = "critic"
    auto_fix: bool = True


class CoordinationReport(BaseModel):
    """Report from agent coordination."""

    active_agents: int
    completed_agents: int
    failed_agents: int
    summary: str
    conflicts: list[str] = Field(default_factory=list)
    handoffs_completed: int = 0
    critique_iterations: int = 0
    scratchpad_entries: int = 0


class AgentCoordinator:
    """Coordinator for multiple governed agents with advanced coordination features."""

    def __init__(
        self,
        registry: AgentRegistry,
        use_claude_coordination: bool = False,
        claude_model: str = "claude-3-5-sonnet-20241022",
    ) -> None:
        """
        Initialize the agent coordinator.

        Args:
            registry: Agent registry
            use_claude_coordination: Whether to use Claude for coordination decisions
            claude_model: Claude model for coordination
        """
        self.registry = registry
        self.scratchpad = SharedScratchpad()
        self.handoff_queue: list[HandoffRequest] = []
        self.critique_config = CritiqueLoopConfig()
        self.critic_agent = CriticAgent(use_claude=use_claude_coordination, model=claude_model)
        self.use_claude_coordination = use_claude_coordination
        self.claude_model = claude_model
        self.client: Anthropic | None = None

        if use_claude_coordination:
            try:
                import os
                api_key = os.getenv("ANTHROPIC_API_KEY")
                if api_key:
                    self.client = Anthropic(api_key=api_key)
                    logger.info("Agent coordinator initialized with Claude coordination")
            except ImportError:
                logger.warning("Anthropic not installed, Claude coordination disabled")

    def create_child_agents(
        self, parent: Agent, goals: list[str]
    ) -> list[Agent]:
        """Create child agents with shared scratchpad context."""
        children: list[Agent] = []
        parent_context = self.scratchpad.get_context(parent.agent_id)

        for goal in goals:
            child = self.registry.create_agent(
                goal,
                parent_agent_id=parent.agent_id,
                metadata={
                    "coordinated_by": parent.agent_id,
                    "parent_context": parent_context,
                },
            )
            # Add to scratchpad
            self.scratchpad.add_entry(
                parent.agent_id,
                f"Created child agent {child.agent_id} with goal: {goal}",
                "agent_creation",
            )
            children.append(child)
        return children

    def request_handoff(
        self,
        from_agent_id: str,
        to_agent_id: str,
        reason: str,
        context: dict[str, Any] | None = None,
    ) -> None:
        """Request a handoff between agents."""
        handoff = HandoffRequest(
            from_agent_id=from_agent_id,
            to_agent_id=to_agent_id,
            reason=reason,
            context=context or {},
        )
        self.handoff_queue.append(handoff)
        self.scratchpad.add_entry(
            from_agent_id,
            f"Handoff requested to {to_agent_id}: {reason}",
            "handoff",
        )

    def process_handoffs(self) -> int:
        """Process pending handoff requests."""
        completed = 0
        while self.handoff_queue:
            handoff = self.handoff_queue.pop(0)
            try:
                from_agent = self.registry.get_agent(handoff.from_agent_id)
                to_agent = self.registry.get_agent(handoff.to_agent_id)

                if from_agent and to_agent:
                    # Transfer context via scratchpad
                    self.scratchpad.add_entry(
                        to_agent.agent_id,
                        f"Received handoff from {handoff.from_agent_id}: {handoff.reason}",
                        "handoff",
                    )
                    completed += 1
            except Exception as exc:
                logger.error(f"Failed to process handoff: {exc}")

        return completed

    def run_critique_loop(self, agent: Agent) -> CriticReport:
        """Run critique loop for an agent with bounded iterations."""
        if not self.critique_config.enabled:
            return CriticReport(passed=True, issues=[])

        iterations = 0
        max_iterations = self.critique_config.max_iterations

        while iterations < max_iterations:
            iterations += 1
            report = self.critic_agent.review_plan(agent)

            if report.passed:
                break

            if self.critique_config.auto_fix and self.use_claude_coordination and self.client:
                # Try to fix issues with Claude
                fixed = self._fix_issues_with_claude(agent, report.issues)
                if fixed:
                    continue

            # Log critique to scratchpad
            self.scratchpad.add_entry(
                agent.agent_id,
                f"Critique iteration {iterations}: {report.issues}",
                "critique",
            )

        return CriticReport(
            passed=report.passed,
            issues=report.issues,
            score=report.score,
        )

    def _fix_issues_with_claude(self, agent: Agent, issues: list[str]) -> bool:
        """Attempt to fix agent issues using Claude."""
        try:
            system_prompt = """You are NAIA's agent fixer. Given an agent goal and a list of issues, suggest fixes.

Return your suggestions as JSON:
{
  "fixes": ["fix1", "fix2"],
  "requires_human": true/false
}"""

            user_prompt = f"""Agent goal: {agent.goal}

Issues:
{chr(10).join(f"- {issue}" for issue in issues)}

Suggest fixes for these issues."""

            response = self.client.messages.create(
                model=self.claude_model,
                max_tokens=512,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text

            # Parse and apply fixes (simplified)
            import json
            import re

            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                fixes = json.loads(json_match.group())
                self.scratchpad.add_entry(
                    agent.agent_id,
                    f"Applied fixes: {fixes.get('fixes', [])}",
                    "fix",
                )
                return True

        except Exception as exc:
            logger.warning("Claude fix failed: %s", exc)

        return False

    def coordinate(self) -> CoordinationReport:
        """Coordinate all agents and return report."""
        # Process handoffs
        handoffs_completed = self.process_handoffs()

        # Get agent states
        agents = self.registry.list_agents()
        active = sum(
            1
            for agent in agents
            if agent.state
            in {
                AgentState.CREATED,
                AgentState.PLANNING,
                AgentState.EXECUTING,
                AgentState.RECOVERING,
                AgentState.VERIFYING,
            }
        )
        completed = sum(1 for agent in agents if agent.state == AgentState.COMPLETED)
        failed = sum(1 for agent in agents if agent.state == AgentState.FAILED)

        # Run critique on active agents
        critique_iterations = 0
        for agent in agents:
            if agent.state in {AgentState.PLANNING, AgentState.EXECUTING}:
                self.run_critique_loop(agent)
                critique_iterations += 1

        return CoordinationReport(
            active_agents=active,
            completed_agents=completed,
            failed_agents=failed,
            summary=(
                f"{active} active, {completed} completed, {failed} failed agents. "
                f"{handoffs_completed} handoffs, {critique_iterations} critiques."
            ),
            handoffs_completed=handoffs_completed,
            critique_iterations=critique_iterations,
            scratchpad_entries=len(self.scratchpad.entries),
        )

    def get_scratchpad(self) -> SharedScratchpad:
        """Get the shared scratchpad."""
        return self.scratchpad
