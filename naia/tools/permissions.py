"""Permission model for governed tool execution."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field


class PermissionLevel(StrEnum):
    READ_ONLY = "READ_ONLY"
    LIMITED_WRITE = "LIMITED_WRITE"
    FULL_WRITE = "FULL_WRITE"
    ADMIN = "ADMIN"


class ToolPermission(StrEnum):
    WEB_ACCESS = "web_access"
    CODE_EXECUTION = "code_execution"
    FILE_READ = "file_read"
    FILE_WRITE = "file_write"
    API_ACCESS = "api_access"
    SYSTEM_EXECUTION = "system_execution"


PERMISSION_LEVEL_ORDER = {
    PermissionLevel.READ_ONLY: 0,
    PermissionLevel.LIMITED_WRITE: 1,
    PermissionLevel.FULL_WRITE: 2,
    PermissionLevel.ADMIN: 3,
}


class PermissionContext(BaseModel):
    max_level: PermissionLevel = PermissionLevel.READ_ONLY
    allowed_permissions: set[ToolPermission] = Field(default_factory=set)
    confirmed: bool = False
    session_id: str | None = None
    reason: str = ""


class PermissionResult(BaseModel):
    allowed: bool
    reason: str = ""
    missing_permissions: list[ToolPermission] = Field(default_factory=list)


class PermissionManager:
    def check(self, definition, context: PermissionContext) -> PermissionResult:
        required_level = definition.permission_level
        if (
            PERMISSION_LEVEL_ORDER[required_level]
            > PERMISSION_LEVEL_ORDER[context.max_level]
        ):
            return PermissionResult(
                allowed=False,
                reason=(
                    f"tool requires {required_level.value}, "
                    f"context allows {context.max_level.value}"
                ),
            )

        required_permissions = set(definition.permissions_required)
        missing = sorted(
            required_permissions - context.allowed_permissions,
            key=lambda permission: permission.value,
        )
        if missing:
            return PermissionResult(
                allowed=False,
                reason="tool permission missing",
                missing_permissions=missing,
            )
        return PermissionResult(allowed=True, reason="permission granted")
