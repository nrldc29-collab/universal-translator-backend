"""Risk gate for every tool call using structured argument schemas."""

from __future__ import annotations

import ast
import ipaddress
import os
import re
import shlex
from pathlib import PureWindowsPath
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from tools.permissions import PermissionLevel
from tools.registry import ToolRequest, ToolRiskLevel


RISK_ORDER = {
    ToolRiskLevel.LOW: 0,
    ToolRiskLevel.MEDIUM: 1,
    ToolRiskLevel.HIGH: 2,
    ToolRiskLevel.CRITICAL: 3,
}


class RiskDecision(BaseModel):
    allowed: bool
    risk_level: ToolRiskLevel
    requires_confirmation: bool = False
    blocked: bool = False
    risk_notes: list[str] = Field(default_factory=list)


class ToolRiskGate:
    """Structured risk gate using parsers instead of substring-only checks."""

    CRITICAL_COMMANDS = {"format", "shutdown", "reboot", "poweroff", "mkfs", "diskpart"}
    HIGH_COMMANDS = {"rm", "del", "erase", "rmdir", "remove-item", "kill", "taskkill"}
    CRITICAL_PYTHON_CALLS = {"__import__", "exec", "eval", "compile"}
    HIGH_PYTHON_ROOTS = {"os", "subprocess", "socket", "shutil", "pathlib", "ctypes"}

    def evaluate(self, definition, request: ToolRequest) -> RiskDecision:
        risk = definition.risk_level
        notes = [f"registered tool risk: {risk.value}"]

        schema_validation = self._validate_arguments(definition, request)
        if not schema_validation["valid"]:
            risk = ToolRiskLevel.CRITICAL
            notes.extend(schema_validation["errors"])

        pattern_risks = self._check_risky_patterns(definition, request)
        if pattern_risks["risk_level"] != ToolRiskLevel.LOW:
            if RISK_ORDER[pattern_risks["risk_level"]] > RISK_ORDER[risk]:
                risk = pattern_risks["risk_level"]
            notes.extend(pattern_risks["notes"])

        if definition.permission_level == PermissionLevel.ADMIN:
            risk = ToolRiskLevel.CRITICAL
            notes.append("admin-level tool requested")

        if risk == ToolRiskLevel.CRITICAL:
            return RiskDecision(
                allowed=False,
                risk_level=risk,
                requires_confirmation=True,
                blocked=True,
                risk_notes=notes + ["critical tool execution is blocked"],
            )

        if risk == ToolRiskLevel.HIGH and not request.confirmed:
            return RiskDecision(
                allowed=False,
                risk_level=risk,
                requires_confirmation=True,
                blocked=False,
                risk_notes=notes + ["high-risk tool execution requires confirmation"],
            )

        return RiskDecision(
            allowed=True,
            risk_level=risk,
            requires_confirmation=risk == ToolRiskLevel.HIGH,
            risk_notes=notes,
        )

    def _validate_arguments(self, definition, request: ToolRequest) -> dict[str, Any]:
        if not definition.input_schema:
            return {"valid": True, "errors": []}

        errors = []
        for field_name, field_type in definition.input_schema.items():
            field_name_clean = field_name.replace("?", "")
            if field_name_clean not in request.arguments and "?" not in field_type:
                errors.append(f"missing required argument: {field_name_clean}")

        return {"valid": len(errors) == 0, "errors": errors}

    def _check_risky_patterns(self, definition, request: ToolRequest) -> dict[str, Any]:
        max_risk = ToolRiskLevel.LOW
        notes: list[str] = []

        for arg_name, arg_value in request.arguments.items():
            if not isinstance(arg_value, str):
                continue

            arg_type = self._argument_type(arg_name)
            detected_risk, arg_notes = self._inspect_argument(arg_type, arg_value)
            if RISK_ORDER[detected_risk] > RISK_ORDER[max_risk]:
                max_risk = detected_risk
            notes.extend(f"{arg_name}: {note}" for note in arg_notes)

        return {"risk_level": max_risk, "notes": notes}

    def _argument_type(self, arg_name: str) -> str:
        normalized = arg_name.casefold()
        for candidate in ("path", "command", "url", "code"):
            if candidate in normalized:
                return candidate
        return "text"

    def _inspect_argument(self, arg_type: str, value: str) -> tuple[ToolRiskLevel, list[str]]:
        if arg_type == "path":
            return self._inspect_path(value)
        if arg_type == "command":
            return self._inspect_command(value)
        if arg_type == "url":
            return self._inspect_url(value)
        if arg_type == "code":
            return self._inspect_python_code(value)
        return ToolRiskLevel.LOW, []

    def _inspect_path(self, value: str) -> tuple[ToolRiskLevel, list[str]]:
        expanded = os.path.expandvars(value.strip())
        notes: list[str] = []
        risk = ToolRiskLevel.LOW
        windows_path = PureWindowsPath(expanded)
        if expanded in {"/", "\\"} or windows_path.anchor:
            risk = ToolRiskLevel.CRITICAL
            notes.append("absolute/root path requires blocking")
        if ".." in re.split(r"[/\\]+", expanded):
            risk = max(risk, ToolRiskLevel.HIGH, key=lambda item: RISK_ORDER[item])
            notes.append("path traversal segment detected")
        return risk, notes

    def _inspect_command(self, value: str) -> tuple[ToolRiskLevel, list[str]]:
        try:
            tokens = shlex.split(value, posix=False)
        except ValueError:
            tokens = value.split()
        commands = [self._command_name(token) for token in tokens if token.strip()]
        risk = ToolRiskLevel.LOW
        notes: list[str] = []
        if any(command in self.CRITICAL_COMMANDS for command in commands):
            risk = ToolRiskLevel.CRITICAL
            notes.append("critical system command detected")
        elif any(command in self.HIGH_COMMANDS for command in commands):
            risk = ToolRiskLevel.HIGH
            notes.append("destructive system command detected")
        return risk, notes

    def _inspect_url(self, value: str) -> tuple[ToolRiskLevel, list[str]]:
        parsed = urlparse(value)
        notes: list[str] = []
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return ToolRiskLevel.HIGH, ["non-http or malformed URL"]
        hostname = parsed.hostname.casefold()
        try:
            ip = ipaddress.ip_address(hostname)
        except ValueError:
            ip = None
        if hostname in {"localhost"} or (ip and (ip.is_private or ip.is_loopback or ip.is_link_local)):
            return ToolRiskLevel.CRITICAL, ["local/private URL target detected"]
        return ToolRiskLevel.LOW, notes

    def _inspect_python_code(self, value: str) -> tuple[ToolRiskLevel, list[str]]:
        try:
            tree = ast.parse(value)
        except SyntaxError:
            return ToolRiskLevel.HIGH, ["python code does not parse"]
        risk = ToolRiskLevel.LOW
        notes: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                roots = [alias.name.split(".", 1)[0] for alias in getattr(node, "names", [])]
                if isinstance(node, ast.ImportFrom) and node.module:
                    roots.append(node.module.split(".", 1)[0])
                if any(root in self.HIGH_PYTHON_ROOTS for root in roots):
                    risk = ToolRiskLevel.HIGH
                    notes.append("forbidden import detected")
            elif isinstance(node, ast.Call):
                name = self._call_name(node.func)
                if name in self.CRITICAL_PYTHON_CALLS:
                    return ToolRiskLevel.CRITICAL, ["critical python dynamic execution detected"]
                if name and any(name == root or name.startswith(f"{root}.") for root in self.HIGH_PYTHON_ROOTS):
                    risk = ToolRiskLevel.HIGH
                    notes.append("high-risk python call detected")
        return risk, notes

    def _call_name(self, node: ast.AST) -> str | None:
        if isinstance(node, ast.Name):
            return node.id
        if isinstance(node, ast.Attribute):
            parent = self._call_name(node.value)
            return f"{parent}.{node.attr}" if parent else node.attr
        return None

    def _command_name(self, token: str) -> str:
        return token.strip('"\'').split("/", 1)[-1].split("\\")[-1].casefold()
