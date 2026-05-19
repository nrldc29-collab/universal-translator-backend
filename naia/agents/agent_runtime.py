"""Persistent runtime for governed agents."""

from __future__ import annotations

import logging
import re
import threading
from pathlib import Path
from typing import Any

from agents.agent_core import Agent, AgentState, AgentTaskStatus
from agents.coordinator import AgentCoordinator
from agents.critic_agent import CriticAgent, CriticReport
from agents.executor import AgentExecutor
from agents.memory_bridge import AgentMemoryBridge
from agents.planner import AgentPlanner
from agents.registry import AgentRegistry
from agents.task_graph import TaskGraph
from agents.tool_bridge import AgentToolBridge
from memory.memory_engine import MemoryEngine
from tools.executor import ToolExecutor
from tools.sandbox import SandboxManager

logger = logging.getLogger(__name__)


class AgentRuntime:
    def __init__(
        self,
        *,
        memory_engine: MemoryEngine | None = None,
        tool_executor: ToolExecutor | None = None,
        registry: AgentRegistry | None = None,
        planner: AgentPlanner | None = None,
        critic: CriticAgent | None = None,
    ) -> None:
        memory_engine = memory_engine or MemoryEngine(db_path=Path("memory") / "agent_runtime_test.sqlite3")
        tool_executor = tool_executor or ToolExecutor(sandbox=SandboxManager(allow_subprocess_fallback=True))
        self.registry = registry or AgentRegistry()
        self.planner = planner or AgentPlanner()
        self.critic = critic or CriticAgent()
        self.memory_bridge = AgentMemoryBridge(memory_engine)
        self.tool_bridge = AgentToolBridge(tool_executor)
        self.executor = AgentExecutor(
            memory_bridge=self.memory_bridge,
            tool_bridge=self.tool_bridge,
        )
        self.coordinator = AgentCoordinator(self.registry)
        self._lock = threading.Lock()

    def create_agent(
        self,
        goal: str,
        *,
        session_id: str | None = None,
        metadata: dict[str, Any] | None = None,
        auto_plan: bool = True,
    ) -> Agent:
        with self._lock:
            agent = self.registry.create_agent(
                goal,
                metadata={"session_id": session_id, **(metadata or {})},
            )
        if auto_plan:
            self.plan_agent(agent.agent_id)
        return self.registry.require(agent.agent_id)

    def plan_agent(self, agent_id: str) -> CriticReport:
        agent = self.registry.require(agent_id)
        agent.transition(AgentState.PLANNING, note="planning started")
        graph = self.planner.plan(agent.goal)
        agent.tasks = graph.tasks
        agent.tool_access = sorted(
            {
                task.tool_request["tool_name"]
                for task in agent.tasks
                if task.tool_request
            }
        )
        agent.update_progress()
        report = self.critic.review_plan(agent)
        if report.passed:
            agent.transition(AgentState.EXECUTING, note="plan accepted")
        else:
            agent.last_error = "; ".join(report.issues)
            agent.transition(AgentState.FAILED, note="plan rejected by critic")
        self.registry.update(agent)
        return report

    def step_agent(self, agent_id: str) -> Agent:
        agent = self.registry.require(agent_id)
        if agent.state == AgentState.PAUSED:
            return agent
        if agent.state == AgentState.CREATED or not agent.tasks:
            self.plan_agent(agent_id)
            agent = self.registry.require(agent_id)
        if agent.state == AgentState.FAILED:
            return agent

        agent.transition(AgentState.EXECUTING, note="execution step started")
        graph = TaskGraph(tasks=agent.tasks)
        ready = graph.ready_tasks()
        if not ready:
            if graph.is_complete():
                self._verify_agent(agent)
            elif graph.failed_tasks():
                agent.last_error = "one or more tasks failed or were blocked"
                agent.transition(AgentState.FAILED, note=agent.last_error)
            self.registry.update(agent)
            return agent

        task = ready[0]
        task.status = AgentTaskStatus.READY
        task.touch()
        self.executor.execute_task(agent, task)
        agent.update_progress()

        graph = TaskGraph(tasks=agent.tasks)
        if graph.is_complete():
            self._verify_agent(agent)
        elif graph.failed_tasks():
            agent.last_error = "one or more tasks failed or were blocked"
            agent.transition(AgentState.FAILED, note=agent.last_error)
        else:
            agent.transition(AgentState.EXECUTING, note="execution step completed")

        self.registry.update(agent)
        return agent

    def run_agent(self, agent_id: str, *, max_steps: int = 10) -> Agent:
        steps = max(1, min(max_steps, 25))
        agent = self.registry.require(agent_id)
        for _ in range(steps):
            agent = self.step_agent(agent_id)
            if agent.state in {
                AgentState.COMPLETED,
                AgentState.FAILED,
                AgentState.PAUSED,
            }:
                break
        return agent

    def pause_agent(self, agent_id: str) -> Agent:
        agent = self.registry.require(agent_id)
        agent.transition(AgentState.PAUSED, note="agent paused")
        return self.registry.update(agent)

    def resume_agent(self, agent_id: str) -> Agent:
        agent = self.registry.require(agent_id)
        if agent.state == AgentState.PAUSED:
            agent.transition(AgentState.EXECUTING, note="agent resumed")
        return self.registry.update(agent)

    def recover_agent(self, agent_id: str) -> Agent:
        agent = self.registry.require(agent_id)
        agent.transition(AgentState.RECOVERING, note="recovery started")
        recovered = False
        for task in agent.tasks:
            if (
                task.status in {AgentTaskStatus.FAILED, AgentTaskStatus.BLOCKED}
                and task.attempts < task.max_attempts
            ):
                task.status = AgentTaskStatus.PENDING
                task.error = None
                task.touch()
                recovered = True
        if recovered:
            agent.last_error = None
            agent.transition(AgentState.EXECUTING, note="failed tasks reset")
        else:
            agent.transition(AgentState.FAILED, note="no recoverable tasks")
        agent.update_progress()
        return self.registry.update(agent)

    def extract_goal(self, text: str) -> str | None:
        patterns = [
            r"(?i)\bcreate agent to\s+(.+)$",
            r"(?i)\brun agent to\s+(.+)$",
            r"(?i)\bagent goal\s*:\s*(.+)$",
            r"(?i)\bstart agent for\s+(.+)$",
        ]
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.DOTALL)
            if match:
                return match.group(1).strip()
        return None

    def status(self) -> dict[str, Any]:
        agents = self.registry.list_agents()
        by_state = {}
        for agent in agents:
            by_state[agent.state.value] = by_state.get(agent.state.value, 0) + 1
        return {
            "total": len(agents),
            "by_state": by_state,
            "count": len(agents),
            "agents": {
                "total": len(agents),
                "by_state": by_state,
                "items": [self.summarize_agent(agent) for agent in agents],
            },
            "coordination": self.coordinator.coordinate().model_dump(mode="json"),
        }

    def summarize_agent(self, agent: Agent) -> dict[str, Any]:
        return {
            "agent_id": agent.agent_id,
            "goal": agent.goal,
            "state": agent.state.value,
            "progress": agent.progress,
            "tasks": [
                {
                    "task_id": task.task_id,
                    "title": task.title,
                    "status": task.status.value,
                    "result": task.result,
                    "error": task.error,
                    "attempts": task.attempts,
                }
                for task in agent.tasks
            ],
            "tool_access": agent.tool_access,
            "last_error": agent.last_error,
            "child_agent_ids": agent.child_agent_ids,
        }

    def _verify_agent(self, agent: Agent) -> None:
        agent.transition(AgentState.VERIFYING, note="critic verification started")
        report = self.critic.review_completion(agent)
        if report.passed:
            agent.progress = 1.0
            agent.transition(AgentState.COMPLETED, note="agent completed")
        else:
            agent.last_error = "; ".join(report.issues)
            agent.transition(AgentState.FAILED, note="critic verification failed")
