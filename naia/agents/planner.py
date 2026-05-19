"""Goal-to-plan conversion for agents."""

from __future__ import annotations

import logging
import re

from agents.agent_core import AgentTask
from agents.task_graph import TaskGraph

logger = logging.getLogger(__name__)


class AgentPlanner:
    def __init__(self, use_local_model: bool = False) -> None:
        """
        Initialize the agent planner.

        Args:
            use_local_model: Whether to use local model for planning
        """
        self.use_local_model = use_local_model

    def plan(self, goal: str) -> TaskGraph:
        if self.use_local_model:
            model_result = self._plan_with_model(goal)
            if model_result is not None:
                return model_result
        return self._plan_with_rules(goal)

    def _plan_with_model(self, goal: str) -> TaskGraph | None:
        """Use Claude model to generate a plan with model-driven task graphs."""
        try:
            from anthropic import Anthropic
            import os
        except ImportError:
            return None

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            return None

        try:
            client = Anthropic(api_key=api_key)
            model = "claude-3-5-sonnet-20241022"

            system_prompt = """You are NAIA's task planner. Break down the user's goal into a sequence of executable steps.

Each step should have:
- step_id: A unique identifier for the step
- description: What this step does
- tool: The tool to use (if applicable)
- arguments: Arguments for the tool (if applicable)
- expected_output: What you expect this step to produce

Available tools:
- run_python: Execute Python code
- read_file: Read a workspace file
- write_file: Write to a workspace file
- list_directory: List files in a directory
- search_web: Search the web
- calculator: Perform calculations

Keep the plan practical and executable. Return the plan as JSON."""

            user_prompt = f"""User goal: {goal}

Generate a task graph in the following JSON format:
{{
  "steps": [
    {{
      "step_id": "1",
      "description": "<brief description>",
      "tool": "<tool_name or null>",
      "arguments": {{<tool arguments>}},
      "expected_output": "<what to expect>"
    }}
  ],
  "reasoning": "<overall reasoning>",
  "estimated_steps": <number>
}}"""

            response = client.messages.create(
                model=model,
                max_tokens=1024,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            content = response.content[0].text

            # Extract JSON from response
            import json
            import re

            json_match = re.search(r'\{[^}]+\}', content, re.DOTALL)
            if json_match:
                result = json.loads(json_match.group())
            else:
                result = json.loads(content)

            # Convert to TaskGraph
            tasks = []
            for i, step in enumerate(result.get("steps", [])):
                task = AgentTask(
                    title=step.get("step_id", f"step_{i}"),
                    description=step.get("description", ""),
                )
                if step.get("tool") and step.get("arguments"):
                    task.tool_request = {
                        "tool_name": step["tool"],
                        "arguments": step["arguments"],
                    }
                tasks.append(task)

            return TaskGraph(tasks=tasks)
        except Exception as exc:
            logger.warning("Claude planning failed, falling back to rules: %s", exc)
            return None

    def _plan_with_rules(self, goal: str) -> TaskGraph:
        """Use rule-based planning (original implementation)."""
        normalized = " ".join(goal.strip().split())
        tasks: list[AgentTask] = []

        first = AgentTask(
            title="Clarify objective",
            description=f"Restate and bound the goal: {normalized}",
        )
        tasks.append(first)

        if self._looks_like_calculation(normalized):
            code = self._python_for_calculation(normalized)
            tasks.append(
                AgentTask(
                    title="Execute bounded calculation",
                    description="Run the calculation in the code sandbox.",
                    dependencies=[first.task_id],
                    tool_request={
                        "tool_name": "run_python",
                        "arguments": {"code": code},
                    },
                )
            )
        elif "read file" in normalized.lower():
            path = normalized.lower().split("read file", 1)[1].strip() or "."
            tasks.append(
                AgentTask(
                    title="Read requested file",
                    description="Read a workspace file through the tool bridge.",
                    dependencies=[first.task_id],
                    tool_request={
                        "tool_name": "read_file",
                        "arguments": {"path": path},
                    },
                )
            )
        elif "list directory" in normalized.lower() or "list files" in normalized.lower():
            path = re.sub(
                r"(?i).*(list directory|list files)\s*",
                "",
                normalized,
            ).strip() or "."
            tasks.append(
                AgentTask(
                    title="List workspace directory",
                    description="List files through the system sandbox.",
                    dependencies=[first.task_id],
                    tool_request={
                        "tool_name": "list_directory",
                        "arguments": {"path": path},
                    },
                )
            )
        elif any(term in normalized.lower() for term in {"build", "design", "plan"}):
            architecture = AgentTask(
                title="Break goal into workstreams",
                description="Identify major workstreams, constraints, and dependencies.",
                dependencies=[first.task_id],
            )
            tasks.append(architecture)
            tasks.append(
                AgentTask(
                    title="Define execution sequence",
                    description="Order the workstreams into a practical sequence.",
                    dependencies=[architecture.task_id],
                )
            )
        else:
            tasks.append(
                AgentTask(
                    title="Produce bounded answer",
                    description="Generate a concise result for the goal.",
                    dependencies=[first.task_id],
                )
            )

        verification = AgentTask(
            title="Verify outcome",
            description="Check the plan or result against the goal and safety constraints.",
            dependencies=[tasks[-1].task_id],
        )
        tasks.append(verification)
        return TaskGraph(tasks=tasks)

    def _looks_like_calculation(self, goal: str) -> bool:
        lowered = goal.lower()
        return bool(re.search(r"\d+\s*[\+\-\*/]\s*\d+", goal)) or any(
            term in lowered for term in {"calculate", "compute"}
        )

    def _python_for_calculation(self, goal: str) -> str:
        expression_match = re.search(r"(\d+(?:\s*[\+\-\*/]\s*\d+)+)", goal)
        if expression_match:
            expression = expression_match.group(1)
            return f"print({expression})"
        return "print('No arithmetic expression found')"


class Planner(AgentPlanner):
    def plan(self, goal: str, context: dict | None = None) -> TaskGraph:
        if not goal.strip():
            raise ValueError("goal is required")
        return super().plan(goal)
