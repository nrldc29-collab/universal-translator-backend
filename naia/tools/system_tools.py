"""Restricted system tools."""

from __future__ import annotations

from typing import Any

from tools.sandbox import SandboxManager, SandboxResult


def read_file(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    path = str(arguments.get("path", ""))
    max_chars = int(arguments.get("max_chars", 20_000))
    if not path:
        return SandboxResult(status="failed", logs=["missing path"])
    return sandbox.read_file(path, max_chars=max_chars)


def write_file(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    path = str(arguments.get("path", ""))
    content = str(arguments.get("content", ""))
    overwrite = bool(arguments.get("overwrite", False))
    if not path:
        return SandboxResult(status="failed", logs=["missing path"])
    return sandbox.write_file(path, content, overwrite=overwrite)


def list_directory(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    path = str(arguments.get("path", "."))
    return sandbox.list_directory(path)


def run_system_command_review(
    arguments: dict[str, Any], sandbox: SandboxManager
) -> SandboxResult:
    command = str(arguments.get("command", ""))
    return sandbox.review_system_command(command)
