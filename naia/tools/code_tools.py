"""Code execution tools."""

from __future__ import annotations

import ast
from typing import Any

from tools.sandbox import SandboxManager, SandboxResult


FORBIDDEN_IMPORTS = {
    "ctypes",
    "ftplib",
    "http",
    "os",
    "pathlib",
    "requests",
    "shutil",
    "socket",
    "subprocess",
    "urllib",
}
FORBIDDEN_CALLS = {
    "__import__",
    "compile",
    "eval",
    "exec",
    "globals",
    "input",
    "locals",
    "open",
}


def run_python(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    code = str(arguments.get("code", ""))
    if not code.strip():
        return SandboxResult(status="failed", logs=["missing code"])
    if len(code) > 20_000:
        return SandboxResult(status="blocked", logs=["code exceeds sandbox size limit"])

    validation = _validate_python_code(code)
    if validation is not None:
        return SandboxResult(
            status="blocked",
            logs=[validation],
            risk_notes=["code sandbox rejected unsafe syntax"],
        )

    timeout = float(arguments.get("timeout_seconds", 3.0))
    return sandbox.run_python(code, timeout_seconds=timeout)


def _validate_python_code(code: str) -> str | None:
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        return f"python syntax error: {exc}"

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root in FORBIDDEN_IMPORTS:
                    return f"forbidden import blocked: {root}"
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".", 1)[0]
            if root in FORBIDDEN_IMPORTS:
                return f"forbidden import blocked: {root}"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
                return f"forbidden call blocked: {node.func.id}"
    return None
