"""Governed bridge between agents and tools."""

from __future__ import annotations

from tools.executor import ToolExecutor
from tools.permissions import PermissionContext, PermissionLevel, ToolPermission
from tools.registry import ToolRequest, ToolResult


class AgentToolBridge:
    def __init__(self, tool_executor: ToolExecutor) -> None:
        self.tool_executor = tool_executor

    def execute(
        self,
        request: ToolRequest,
        *,
        session_id: str | None,
        confirmed: bool = False,
    ) -> ToolResult:
        request.session_id = request.session_id or session_id
        request.confirmed = request.confirmed or confirmed
        context = PermissionContext(
            max_level=PermissionLevel.LIMITED_WRITE,
            allowed_permissions={
                ToolPermission.API_ACCESS,
                ToolPermission.CODE_EXECUTION,
                ToolPermission.FILE_READ,
                ToolPermission.FILE_WRITE,
                ToolPermission.WEB_ACCESS,
            },
            confirmed=confirmed,
            session_id=session_id,
            reason="agent bounded tool bridge",
        )
        return self.tool_executor.execute(request, context)
