"""Persistent registry for active agents."""

from __future__ import annotations

import json
from pathlib import Path

from agents.agent_core import Agent, AgentState


class AgentRegistry:
    def __init__(self, checkpoint_path: str | Path | None = None) -> None:
        self.checkpoint_path = Path(
            checkpoint_path or Path("agents") / "agent_registry.state.json"
        )
        self._agents: dict[str, Agent] = {}
        self._load()

    def create_agent(
        self,
        goal: str,
        *,
        parent_agent_id: str | None = None,
        metadata: dict | None = None,
    ) -> Agent:
        agent = Agent(
            goal=goal,
            parent_agent_id=parent_agent_id,
            metadata=metadata or {},
        )
        agent.transition(AgentState.CREATED, note="agent created")
        self._agents[agent.agent_id] = agent
        if parent_agent_id and parent_agent_id in self._agents:
            parent = self._agents[parent_agent_id]
            parent.child_agent_ids.append(agent.agent_id)
            parent.touch()
        self.save()
        return agent

    def register(self, agent: Agent) -> Agent:
        self._agents[agent.agent_id] = agent
        self.save()
        return agent

    def get(self, agent_id: str) -> Agent | None:
        return self._agents.get(agent_id)

    def require(self, agent_id: str) -> Agent:
        agent = self.get(agent_id)
        if agent is None:
            raise KeyError(f"unknown agent: {agent_id}")
        return agent

    def update(self, agent: Agent) -> Agent:
        self._agents[agent.agent_id] = agent
        self.save()
        return agent

    def destroy(self, agent_id: str) -> bool:
        removed = self._agents.pop(agent_id, None)
        self.save()
        return removed is not None

    def list_agents(self) -> list[Agent]:
        return sorted(
            self._agents.values(),
            key=lambda agent: agent.created_at,
            reverse=True,
        )

    def save(self) -> None:
        self.checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [
            agent.model_dump(mode="json") for agent in self._agents.values()
        ]
        self.checkpoint_path.write_text(
            json.dumps(payload, indent=2),
            encoding="utf-8",
        )

    def _load(self) -> None:
        if not self.checkpoint_path.exists():
            return
        try:
            payload = json.loads(self.checkpoint_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return
        self._agents = {
            agent.agent_id: agent for agent in (Agent.model_validate(item) for item in payload)
        }
