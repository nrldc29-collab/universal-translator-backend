"""Governed tool executor."""

from __future__ import annotations

import time

from pydantic import BaseModel, Field

from tools.permissions import PermissionContext, PermissionManager
from tools.registry import ToolRegistry, ToolRequest, ToolResult, ToolStatus
from tools.risk_gate import ToolRiskGate
from tools.sandbox import SandboxManager


class ToolExecutionRecord(BaseModel):
    request: ToolRequest
    result: ToolResult
    permission_reason: str
    risk_notes: list[str] = Field(default_factory=list)


class ToolExecutor:
    def __init__(
        self,
        *,
        registry: ToolRegistry | None = None,
        permissions: PermissionManager | None = None,
        risk_gate: ToolRiskGate | None = None,
        sandbox: SandboxManager | None = None,
    ) -> None:
        from tools.registry import create_default_registry

        self.registry = registry or create_default_registry()
        self.permissions = permissions or PermissionManager()
        self.risk_gate = risk_gate or ToolRiskGate()
        self.sandbox = sandbox or SandboxManager()
        self.execution_log: list[ToolExecutionRecord] = []

    def execute(
        self, request: ToolRequest, context: PermissionContext
    ) -> ToolResult:
        started = time.perf_counter()
        definition = self.registry.get(request.tool_name)
        if definition is None:
            return self._record(
                request,
                ToolResult(
                    tool_name=request.tool_name,
                    status=ToolStatus.BLOCKED,
                    logs=["tool is not registered"],
                    execution_time=self._elapsed(started),
                ),
                permission_reason="unknown tool",
                risk_notes=[],
            )

        permission_result = self.permissions.check(definition, context)
        if not permission_result.allowed:
            return self._record(
                request,
                ToolResult(
                    tool_name=request.tool_name,
                    status=ToolStatus.BLOCKED,
                    logs=[permission_result.reason],
                    execution_time=self._elapsed(started),
                    metadata={"definition": definition.model_dump(mode="json")},
                ),
                permission_reason=permission_result.reason,
                risk_notes=[],
            )

        risk_decision = self.risk_gate.evaluate(definition, request)
        if not risk_decision.allowed:
            return self._record(
                request,
                ToolResult(
                    tool_name=request.tool_name,
                    status=ToolStatus.BLOCKED,
                    logs=[next((note for note in risk_decision.risk_notes if "forbidden import" in note), risk_decision.risk_notes[-1] if risk_decision.risk_notes else "tool blocked by risk gate")],
                    risk_notes=risk_decision.risk_notes,
                    execution_time=self._elapsed(started),
                    metadata={
                        "definition": definition.model_dump(mode="json"),
                        "risk": risk_decision.model_dump(mode="json"),
                    },
                ),
                permission_reason=permission_result.reason,
                risk_notes=risk_decision.risk_notes,
            )

        handler = self.registry.handler_for(request.tool_name)
        if handler is None:
            return self._record(
                request,
                ToolResult(
                    tool_name=request.tool_name,
                    status=ToolStatus.BLOCKED,
                    logs=["tool handler is missing"],
                    execution_time=self._elapsed(started),
                ),
                permission_reason=permission_result.reason,
                risk_notes=risk_decision.risk_notes,
            )

        try:
            sandbox_result = handler(request.arguments, self.sandbox)
            status = (
                ToolStatus.SUCCESS
                if sandbox_result.status == "success"
                else ToolStatus.BLOCKED
                if sandbox_result.status == "blocked"
                else ToolStatus.FAILED
            )
            result = ToolResult(
                tool_name=request.tool_name,
                status=status,
                result=sandbox_result.result,
                logs=sandbox_result.logs,
                risk_notes=[*risk_decision.risk_notes, *sandbox_result.risk_notes],
                execution_time=self._elapsed(started),
                metadata={
                    "definition": definition.model_dump(mode="json"),
                    "risk": risk_decision.model_dump(mode="json"),
                    "sandbox_type": definition.sandbox_type.value,
                },
            )
        except Exception as exc:
            result = ToolResult(
                tool_name=request.tool_name,
                status=ToolStatus.FAILED,
                logs=[f"tool execution failed: {exc}"],
                risk_notes=risk_decision.risk_notes,
                execution_time=self._elapsed(started),
                metadata={"definition": definition.model_dump(mode="json")},
            )

        return self._record(
            request,
            result,
            permission_reason=permission_result.reason,
            risk_notes=risk_decision.risk_notes,
        )

    def _record(
        self,
        request: ToolRequest,
        result: ToolResult,
        *,
        permission_reason: str,
        risk_notes: list[str],
    ) -> ToolResult:
        self.execution_log.append(
            ToolExecutionRecord(
                request=request,
                result=result,
                permission_reason=permission_reason,
                risk_notes=risk_notes,
            )
        )
        return result

    def _elapsed(self, started: float) -> float:
        return round(time.perf_counter() - started, 6)

