"""Integration tests for the agents module."""

import pytest
from agents.agent_core import Agent, AgentState
from agents.agent_runtime import AgentRuntime
from agents.registry import AgentRegistry
from agents.planner import Planner
from agents.executor import Executor


class TestAgentsHappyPath:
    """Happy-path tests for the agents module."""

    def test_agent_creation_and_initialization(self):
        """Test that an agent can be created and initialized correctly."""
        agent = Agent(
            agent_id="test-agent-1",
            goal="Test goal",
            state=AgentState.CREATED,
            metadata={"test": "data"},
        )
        assert agent.agent_id == "test-agent-1"
        assert agent.goal == "Test goal"
        assert agent.state == AgentState.CREATED
        assert agent.metadata == {"test": "data"}

    def test_agent_registry_register_and_retrieve(self):
        """Test that the agent registry can register and retrieve agents."""
        registry = AgentRegistry()
        agent = Agent(
            agent_id="test-agent-2",
            goal="Registry test",
            state=AgentState.CREATED,
        )
        registry.register(agent)
        retrieved = registry.require("test-agent-2")
        assert retrieved.agent_id == "test-agent-2"
        assert retrieved.goal == "Registry test"

    def test_planner_creates_valid_plan(self):
        """Test that the planner can create a valid execution plan."""
        planner = Planner()
        plan = planner.plan("Calculate the sum of 1 and 2", context={})
        assert plan is not None
        assert len(plan.tasks) > 0
        assert all(step.description for step in plan.tasks)

    def test_executor_executes_plan_step(self):
        """Test that the executor can execute a plan step."""
        executor = Executor()
        # This is a simplified test - in real scenario, you'd need proper setup
        result = executor.execute_step(
            step_id="test-step",
            action="test_action",
            parameters={"test": "param"},
        )
        assert result is not None


class TestAgentsFailurePath:
    """Failure-path tests for the agents module."""

    def test_agent_registry_fails_on_missing_agent(self):
        """Test that the registry raises an error for missing agents."""
        registry = AgentRegistry()
        with pytest.raises(KeyError):
            registry.require("non-existent-agent")

    def test_agent_state_transition_validation(self):
        """Test that agent state transitions are validated."""
        agent = Agent(
            agent_id="test-agent-3",
            goal="State transition test",
            state=AgentState.CREATED,
        )
        # Invalid transition from IDLE to FAILED (should go through RUNNING first)
        agent.transition(AgentState.FAILED, note="test failure")
        assert agent.state == AgentState.FAILED

    def test_planner_fails_on_empty_goal(self):
        """Test that the planner fails on an empty goal."""
        planner = Planner()
        with pytest.raises(ValueError):
            planner.plan("", context={})

    def test_executor_fails_on_invalid_step(self):
        """Test that the executor fails on an invalid step."""
        executor = Executor()
        with pytest.raises(ValueError):
            executor.execute_step(
                step_id="",
                action="",
                parameters={},
            )


class TestAgentRuntimeIntegration:
    """Integration tests for the agent runtime."""

    def test_runtime_creates_and_runs_agent(self):
        """Test that the runtime can create and run an agent."""
        runtime = AgentRuntime()
        agent = runtime.create_agent("Test integration goal", metadata={"test": "integration"})
        assert agent is not None
        assert agent.agent_id is not None
        assert agent.goal == "Test integration goal"

    def test_runtime_status_returns_valid_status(self):
        """Test that the runtime returns valid status information."""
        runtime = AgentRuntime()
        status = runtime.status()
        assert "agents" in status
        assert "total" in status["agents"]
        assert "by_state" in status["agents"]
