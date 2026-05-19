"""Directed acyclic task graph for agent work."""

from __future__ import annotations

from pydantic import BaseModel, Field

from agents.agent_core import AgentTask, AgentTaskStatus


class TaskGraphValidation(BaseModel):
    valid: bool
    issues: list[str] = Field(default_factory=list)


class TaskGraph(BaseModel):
    tasks: list[AgentTask] = Field(default_factory=list)

    def validate_graph(self) -> TaskGraphValidation:
        issues: list[str] = []
        task_ids = {task.task_id for task in self.tasks}
        for task in self.tasks:
            for dependency in task.dependencies:
                if dependency not in task_ids:
                    issues.append(
                        f"task {task.task_id} depends on missing task {dependency}"
                    )
        if self._has_cycle():
            issues.append("task graph contains a cycle")
        return TaskGraphValidation(valid=not issues, issues=issues)

    def ready_tasks(self) -> list[AgentTask]:
        completed = {
            task.task_id
            for task in self.tasks
            if task.status == AgentTaskStatus.COMPLETED
        }
        return [
            task
            for task in self.tasks
            if task.status in {AgentTaskStatus.PENDING, AgentTaskStatus.READY}
            and all(dependency in completed for dependency in task.dependencies)
        ]

    def failed_tasks(self) -> list[AgentTask]:
        return [
            task
            for task in self.tasks
            if task.status in {AgentTaskStatus.FAILED, AgentTaskStatus.BLOCKED}
        ]

    def is_complete(self) -> bool:
        return bool(self.tasks) and all(
            task.status
            in {
                AgentTaskStatus.COMPLETED,
                AgentTaskStatus.SKIPPED,
            }
            for task in self.tasks
        )

    def _has_cycle(self) -> bool:
        graph = {task.task_id: set(task.dependencies) for task in self.tasks}
        visiting: set[str] = set()
        visited: set[str] = set()

        def visit(task_id: str) -> bool:
            if task_id in visiting:
                return True
            if task_id in visited:
                return False
            visiting.add(task_id)
            for dependency in graph.get(task_id, set()):
                if visit(dependency):
                    return True
            visiting.remove(task_id)
            visited.add(task_id)
            return False

        return any(visit(task_id) for task_id in graph)
