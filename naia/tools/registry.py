"""Explicit registry for every available tool."""

from __future__ import annotations

from collections.abc import Callable
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from tools.permissions import PermissionLevel, ToolPermission
from tools.sandbox import SandboxManager, SandboxResult, SandboxType


ToolHandler = Callable[[dict[str, Any], SandboxManager], SandboxResult]


class ToolRiskLevel(StrEnum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ToolStatus(StrEnum):
    SUCCESS = "success"
    FAILED = "failed"
    BLOCKED = "blocked"


class ToolDefinition(BaseModel):
    name: str
    description: str
    risk_level: ToolRiskLevel
    permission_level: PermissionLevel
    permissions_required: list[ToolPermission]
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    sandbox_type: SandboxType


class ToolRequest(BaseModel):
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    session_id: str | None = None
    user_intent: str = ""
    confirmed: bool = False


class ToolResult(BaseModel):
    tool_name: str
    status: ToolStatus
    result: dict[str, Any] = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)
    execution_time: float = 0.0
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolRegistry:
    def __init__(self) -> None:
        self._definitions: dict[str, ToolDefinition] = {}
        self._handlers: dict[str, ToolHandler] = {}

    def register(
        self, definition: ToolDefinition, handler: ToolHandler
    ) -> None:
        if definition.name in self._definitions:
            raise ValueError(f"tool already registered: {definition.name}")
        self._definitions[definition.name] = definition
        self._handlers[definition.name] = handler

    def get(self, name: str) -> ToolDefinition | None:
        return self._definitions.get(name)

    def handler_for(self, name: str) -> ToolHandler | None:
        return self._handlers.get(name)

    def list_tools(self) -> list[ToolDefinition]:
        return sorted(self._definitions.values(), key=lambda tool: tool.name)

    def require(self, name: str) -> ToolDefinition:
        definition = self.get(name)
        if definition is None:
            raise KeyError(f"unknown tool: {name}")
        return definition


def create_default_registry() -> ToolRegistry:
    from tools.api_tools import api_get
    from tools.code_tools import run_python
    from tools.system_tools import (
        list_directory,
        read_file,
        run_system_command_review,
        write_file,
    )
    from tools.web_tools import fetch_url, web_search

    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="run_python",
            description="Executes Python code in an isolated temporary sandbox.",
            risk_level=ToolRiskLevel.MEDIUM,
            permission_level=PermissionLevel.LIMITED_WRITE,
            permissions_required=[ToolPermission.CODE_EXECUTION],
            input_schema={"code": "str", "timeout_seconds": "float?"},
            output_schema={"stdout": "str", "stderr": "str", "returncode": "int"},
            sandbox_type=SandboxType.CODE,
        ),
        run_python,
    )
    registry.register(
        ToolDefinition(
            name="read_file",
            description="Reads a UTF-8 text file inside the workspace sandbox.",
            risk_level=ToolRiskLevel.LOW,
            permission_level=PermissionLevel.READ_ONLY,
            permissions_required=[ToolPermission.FILE_READ],
            input_schema={"path": "str", "max_chars": "int?"},
            output_schema={"path": "str", "content": "str", "truncated": "bool"},
            sandbox_type=SandboxType.SYSTEM,
        ),
        read_file,
    )
    registry.register(
        ToolDefinition(
            name="list_directory",
            description="Lists directory entries inside the workspace sandbox.",
            risk_level=ToolRiskLevel.LOW,
            permission_level=PermissionLevel.READ_ONLY,
            permissions_required=[ToolPermission.FILE_READ],
            input_schema={"path": "str?"},
            output_schema={"path": "str", "entries": "list"},
            sandbox_type=SandboxType.SYSTEM,
        ),
        list_directory,
    )
    registry.register(
        ToolDefinition(
            name="write_file",
            description="Writes a UTF-8 text file inside the workspace sandbox.",
            risk_level=ToolRiskLevel.MEDIUM,
            permission_level=PermissionLevel.LIMITED_WRITE,
            permissions_required=[ToolPermission.FILE_WRITE],
            input_schema={"path": "str", "content": "str", "overwrite": "bool?"},
            output_schema={"path": "str", "bytes_written": "int"},
            sandbox_type=SandboxType.SYSTEM,
        ),
        write_file,
    )
    registry.register(
        ToolDefinition(
            name="fetch_url",
            description="Fetches a URL through the network sandbox.",
            risk_level=ToolRiskLevel.LOW,
            permission_level=PermissionLevel.READ_ONLY,
            permissions_required=[ToolPermission.WEB_ACCESS],
            input_schema={"url": "str", "max_chars": "int?"},
            output_schema={"url": "str", "content": "str", "status_code": "int?"},
            sandbox_type=SandboxType.NETWORK,
        ),
        fetch_url,
    )
    registry.register(
        ToolDefinition(
            name="web_search",
            description="Performs a bounded web search through the network sandbox.",
            risk_level=ToolRiskLevel.LOW,
            permission_level=PermissionLevel.READ_ONLY,
            permissions_required=[ToolPermission.WEB_ACCESS],
            input_schema={"query": "str", "max_results": "int?"},
            output_schema={"query": "str", "results": "list"},
            sandbox_type=SandboxType.NETWORK,
        ),
        web_search,
    )
    registry.register(
        ToolDefinition(
            name="api_get",
            description="Performs an allowlisted HTTP GET API request.",
            risk_level=ToolRiskLevel.MEDIUM,
            permission_level=PermissionLevel.LIMITED_WRITE,
            permissions_required=[ToolPermission.API_ACCESS],
            input_schema={"url": "str", "allow_external": "bool?"},
            output_schema={"url": "str", "content": "str", "status_code": "int?"},
            sandbox_type=SandboxType.API,
        ),
        api_get,
    )
    registry.register(
        ToolDefinition(
            name="run_system_command",
            description="Reviews a system command request; execution is blocked in Step 6.",
            risk_level=ToolRiskLevel.CRITICAL,
            permission_level=PermissionLevel.ADMIN,
            permissions_required=[ToolPermission.SYSTEM_EXECUTION],
            input_schema={"command": "str"},
            output_schema={"blocked": "bool", "reason": "str"},
            sandbox_type=SandboxType.SYSTEM,
        ),
        run_system_command_review,
    )
    return registry
