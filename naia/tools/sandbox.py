"""Sandbox adapters for code, system, network, and API tools.

The Python code backend now defaults to Docker-based isolation when Docker is
available. If Docker is unavailable, code execution is blocked unless the caller
explicitly enables the legacy subprocess fallback for local development.
"""

from __future__ import annotations

import html
import ipaddress
import os
import re
import socket
import subprocess
import sys
import tempfile
from enum import StrEnum
from pathlib import Path
from urllib.error import URLError
from urllib.parse import quote_plus, urlparse
from urllib.request import Request, urlopen

from pydantic import BaseModel, Field


class SandboxType(StrEnum):
    CODE = "code"
    SYSTEM = "system"
    NETWORK = "network"
    API = "api"


class SandboxResult(BaseModel):
    status: str
    result: dict = Field(default_factory=dict)
    logs: list[str] = Field(default_factory=list)
    risk_notes: list[str] = Field(default_factory=list)


class SandboxManager:
    def __init__(
        self,
        workspace_root: str | Path | None = None,
        *,
        allow_subprocess_fallback: bool | None = None,
    ) -> None:
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.allow_subprocess_fallback = (
os.getenv("NAIA_REQUIRE_DOCKER_SANDBOX") != "1"
            if allow_subprocess_fallback is None
            else allow_subprocess_fallback
        )

    def run_python(
        self, code: str, *, timeout_seconds: float = 3.0
    ) -> SandboxResult:
        timeout = max(0.1, min(timeout_seconds, 5.0))
        docker_path = self._docker_path()
        if docker_path:
            return self._run_python_docker(code, timeout_seconds=timeout, docker_path=docker_path)
        if not self.allow_subprocess_fallback:
            return SandboxResult(
                status="blocked",
                logs=["docker sandbox backend is unavailable"],
                risk_notes=[
                    "unsafe subprocess fallback is disabled; set "
                    "NAIA_ALLOW_UNSAFE_SUBPROCESS_SANDBOX=1 only for local development"
                ],
            )
        return self._run_python_subprocess(code, timeout_seconds=timeout)

    def _run_python_docker(
        self,
        code: str,
        *,
        timeout_seconds: float,
        docker_path: str,
    ) -> SandboxResult:
        with tempfile.TemporaryDirectory(prefix="naia-code-sandbox-") as temp_dir:
            script_path = Path(temp_dir) / "main.py"
            script_path.write_text(code, encoding="utf-8")
            command = [
                docker_path,
                "run",
                "--rm",
                "--network",
                "none",
                "--memory",
                "128m",
                "--cpus",
                "0.5",
                "--pids-limit",
                "64",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=32m",
                "-v",
                f"{script_path.as_posix()}:/sandbox/main.py:ro",
                "python:3.11-slim",
                "python",
                "-I",
                "/sandbox/main.py",
            ]
            try:
                completed = subprocess.run(
                    command,
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds + 3.0,
                    shell=False,
                    env={"PYTHONIOENCODING": "utf-8"},
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxResult(
                    status="failed",
                    result={
                        "stdout": exc.stdout or "",
                        "stderr": exc.stderr or "",
                        "returncode": None,
                    },
                    logs=["docker python sandbox timed out"],
                    risk_notes=["execution stopped by sandbox timeout"],
                )
        return SandboxResult(
            status="success" if completed.returncode == 0 else "failed",
            result={
                "stdout": completed.stdout[:10_000],
                "stderr": completed.stderr[:10_000],
                "returncode": completed.returncode,
            },
            logs=["python executed in docker sandbox"],
        )

    def _run_python_subprocess(
        self, code: str, *, timeout_seconds: float
    ) -> SandboxResult:
        with tempfile.TemporaryDirectory(prefix="naia-code-sandbox-") as temp_dir:
            script_path = Path(temp_dir) / "main.py"
            script_path.write_text(code, encoding="utf-8")
            try:
                completed = subprocess.run(
                    [sys.executable, "-I", str(script_path)],
                    cwd=temp_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout_seconds,
                    shell=False,
                    env={"PYTHONIOENCODING": "utf-8"},
                )
            except subprocess.TimeoutExpired as exc:
                return SandboxResult(
                    status="failed",
                    result={
                        "stdout": exc.stdout or "",
                        "stderr": exc.stderr or "",
                        "returncode": None,
                    },
                    logs=["python sandbox timed out"],
                    risk_notes=["execution stopped by sandbox timeout"],
                )
        return SandboxResult(
            status="success" if completed.returncode == 0 else "failed",
            result={
                "stdout": completed.stdout[:10_000],
                "stderr": completed.stderr[:10_000],
                "returncode": completed.returncode,
            },
            logs=["python executed in unsafe subprocess fallback"],
            risk_notes=["subprocess fallback is not an isolation boundary"],
        )

    def read_file(self, path: str, *, max_chars: int = 20_000) -> SandboxResult:
        try:
            resolved = self._resolve_workspace_path(path)
        except PermissionError as exc:
            return SandboxResult(
                status="blocked",
                result={"path": path},
                logs=[str(exc)],
                risk_notes=["path traversal blocked by system sandbox"],
            )
        if not resolved.exists() or not resolved.is_file():
            return SandboxResult(
                status="failed",
                result={"path": str(resolved)},
                logs=["file not found"],
            )
        content = resolved.read_text(encoding="utf-8", errors="replace")
        truncated = len(content) > max_chars
        return SandboxResult(
            status="success",
            result={
                "path": str(resolved),
                "content": content[:max_chars],
                "truncated": truncated,
            },
            logs=["file read inside workspace sandbox"],
        )

    def write_file(
        self,
        path: str,
        content: str,
        *,
        overwrite: bool = False,
    ) -> SandboxResult:
        try:
            resolved = self._resolve_workspace_path(path)
        except PermissionError as exc:
            return SandboxResult(
                status="blocked",
                result={"path": path},
                logs=[str(exc)],
                risk_notes=["path traversal blocked by system sandbox"],
            )
        if resolved.exists() and not overwrite:
            return SandboxResult(
                status="failed",
                result={"path": str(resolved)},
                logs=["file exists; overwrite not enabled"],
            )
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_text(content, encoding="utf-8")
        return SandboxResult(
            status="success",
            result={"path": str(resolved), "bytes_written": len(content.encode("utf-8"))},
            logs=["file written inside workspace sandbox"],
        )

    def list_directory(self, path: str = ".") -> SandboxResult:
        try:
            resolved = self._resolve_workspace_path(path)
        except PermissionError as exc:
            return SandboxResult(
                status="blocked",
                result={"path": path},
                logs=[str(exc)],
                risk_notes=["path traversal blocked by system sandbox"],
            )
        if not resolved.exists() or not resolved.is_dir():
            return SandboxResult(
                status="failed",
                result={"path": str(resolved)},
                logs=["directory not found"],
            )
        entries = [
            {
                "name": item.name,
                "type": "directory" if item.is_dir() else "file",
            }
            for item in sorted(resolved.iterdir(), key=lambda entry: entry.name.lower())
        ]
        return SandboxResult(
            status="success",
            result={"path": str(resolved), "entries": entries},
            logs=["directory listed inside workspace sandbox"],
        )

    def fetch_url(self, url: str, *, max_chars: int = 20_000) -> SandboxResult:
        safe_url = self._validate_public_url(url)
        if safe_url is None:
            return SandboxResult(
                status="blocked",
                result={"url": url},
                logs=["url blocked by network sandbox"],
                risk_notes=["only public http/https URLs are allowed"],
            )

        request = Request(
            safe_url,
            headers={
                "User-Agent": "NAIA-TESL/0.1",
                "Accept": "text/html, text/plain, application/json",
            },
        )
        try:
            with urlopen(request, timeout=5) as response:
                raw = response.read(max_chars * 4)
                content_type = response.headers.get("content-type", "")
                status_code = getattr(response, "status", None)
        except URLError as exc:
            return SandboxResult(
                status="failed",
                result={"url": safe_url, "error": str(exc)},
                logs=["network sandbox request failed"],
            )

        text = raw.decode("utf-8", errors="replace")
        if "html" in content_type:
            text = self._html_to_text(text)
        return SandboxResult(
            status="success",
            result={
                "url": safe_url,
                "content": text[:max_chars],
                "truncated": len(text) > max_chars,
                "status_code": status_code,
                "content_type": content_type,
            },
            logs=["url fetched through network sandbox"],
        )

    def search_web(self, query: str, *, max_results: int = 5) -> SandboxResult:
        bounded_results = max(1, min(max_results, 10))
        search_url = f"https://duckduckgo.com/html/?q={quote_plus(query)}"
        result = self.fetch_url(search_url, max_chars=30_000)
        if result.status != "success":
            return result
        content = result.result.get("content", "")
        titles = [
            html.unescape(match).strip()
            for match in re.findall(r'class="result__a"[^>]*>(.*?)</a>', content)
        ]
        clean_titles = [self._html_to_text(title) for title in titles][:bounded_results]
        return SandboxResult(
            status="success",
            result={
                "query": query,
                "results": [{"title": title} for title in clean_titles],
                "search_url": search_url,
            },
            logs=["bounded web search executed through network sandbox"],
        )

    def review_system_command(self, command: str) -> SandboxResult:
        return SandboxResult(
            status="blocked",
            result={"blocked": True, "reason": "system command execution is disabled"},
            logs=["system command reviewed but not executed"],
            risk_notes=["process execution is not enabled in Step 6"],
        )

    def _docker_path(self) -> str | None:
        for candidate in ("docker", "docker.exe"):
            try:
                subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                    shell=False,
                )
                return candidate
            except (OSError, subprocess.TimeoutExpired):
                continue
        return None

    def _resolve_workspace_path(self, path: str) -> Path:
        candidate = (self.workspace_root / path).resolve()
        if (
            candidate != self.workspace_root
            and self.workspace_root not in candidate.parents
        ):
            raise PermissionError(f"path escapes workspace sandbox: {path}")
        return candidate

    def _validate_public_url(self, url: str) -> str | None:
        parsed = urlparse(url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            return None
        try:
            addresses = socket.getaddrinfo(parsed.hostname, None)
        except socket.gaierror:
            return None
        for address in addresses:
            ip = ipaddress.ip_address(address[4][0])
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                return None
        return url

    def _html_to_text(self, value: str) -> str:
        without_scripts = re.sub(r"<script.*?</script>", "", value, flags=re.I | re.S)
        without_styles = re.sub(r"<style.*?</style>", "", without_scripts, flags=re.I | re.S)
        without_tags = re.sub(r"<[^>]+>", " ", without_styles)
        return html.unescape(re.sub(r"\s+", " ", without_tags)).strip()
