"""Tool selection for explicit tool-like user requests."""

from __future__ import annotations

import re
from pathlib import PurePath

from pydantic import BaseModel

from tools.permissions import PermissionContext, PermissionLevel, ToolPermission
from tools.registry import ToolRequest


class ToolRoute(BaseModel):
    request: ToolRequest | None = None
    reason: str = ""


class ToolRouter:
    def route(self, text: str, *, session_id: str | None = None) -> ToolRoute:
        normalized = text.strip()
        lowered = normalized.lower()

        code = self._extract_python_code(normalized)
        if code is not None:
            return ToolRoute(
                request=ToolRequest(
                    tool_name="run_python",
                    arguments={"code": code},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit python execution request",
            )

        url = self._extract_url(normalized)
        if url and any(term in lowered for term in {"fetch", "open url", "scrape"}):
            return ToolRoute(
                request=ToolRequest(
                    tool_name="fetch_url",
                    arguments={"url": url},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit url fetch request",
            )

        if any(phrase in lowered for phrase in {"search web for", "web search", "search for"}):
            query = re.sub(
                r"(?i)^(please\s+)?(search web for|web search|search for)\s+",
                "",
                normalized,
            ).strip()
            if query:
                return ToolRoute(
                    request=ToolRequest(
                        tool_name="web_search",
                        arguments={"query": query},
                        session_id=session_id,
                        user_intent=text,
                    ),
                    reason="explicit web search request",
                )

        read_match = re.search(r"(?i)\bread file\s+(.+)$", normalized)
        if read_match:
            return ToolRoute(
                request=ToolRequest(
                    tool_name="read_file",
                    arguments={"path": self._clean_path(read_match.group(1))},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit file read request",
            )

        list_match = re.search(r"(?i)\b(list directory|list files)\s*(.*)$", normalized)
        if list_match:
            path = self._clean_path(list_match.group(2) or ".")
            return ToolRoute(
                request=ToolRequest(
                    tool_name="list_directory",
                    arguments={"path": path or "."},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit directory listing request",
            )

        write_match = re.search(
            r"(?i)\bwrite file\s+(.+?)\s+(?:with|content:)\s+(.+)$",
            normalized,
            flags=re.DOTALL,
        )
        if write_match:
            return ToolRoute(
                request=ToolRequest(
                    tool_name="write_file",
                    arguments={
                        "path": self._clean_path(write_match.group(1)),
                        "content": write_match.group(2).strip(),
                        "overwrite": False,
                    },
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit file write request",
            )

        api_match = re.search(r"(?i)\bapi get\s+(\S+)", normalized)
        if api_match:
            return ToolRoute(
                request=ToolRequest(
                    tool_name="api_get",
                    arguments={"url": api_match.group(1), "allow_external": False},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit api get request",
            )

        command_match = re.search(r"(?i)\brun system command\s+(.+)$", normalized)
        if command_match:
            return ToolRoute(
                request=ToolRequest(
                    tool_name="run_system_command",
                    arguments={"command": command_match.group(1).strip()},
                    session_id=session_id,
                    user_intent=text,
                ),
                reason="explicit system command request",
            )

        return ToolRoute(reason="no explicit tool request detected")

    def permission_context_for_route(
        self,
        *,
        tool_access: bool,
        risk_level: str,
        session_id: str | None,
        confirmed: bool = False,
    ) -> PermissionContext:
        if not tool_access or risk_level in {"HIGH", "CRITICAL"}:
            return PermissionContext(
                max_level=PermissionLevel.READ_ONLY,
                allowed_permissions={ToolPermission.FILE_READ, ToolPermission.WEB_ACCESS},
                confirmed=confirmed,
                session_id=session_id,
                reason="tool access reduced by route policy",
            )

        return PermissionContext(
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
            reason="bounded tool access granted by route policy",
        )

    def _extract_python_code(self, text: str) -> str | None:
        lowered = text.lower()
        if not any(
            phrase in lowered
            for phrase in {"run python", "execute python", "python code"}
        ):
            return None

        fenced = re.search(r"```(?:python)?\s*(.*?)```", text, flags=re.DOTALL | re.IGNORECASE)
        if fenced:
            return fenced.group(1).strip()
        colon = re.search(
            r"(?i)(?:run python|execute python|python code)\s*:?\s*(.+)$",
            text,
            flags=re.DOTALL,
        )
        return colon.group(1).strip() if colon else None

    def _extract_url(self, text: str) -> str | None:
        match = re.search(r"https?://\S+", text)
        return match.group(0).rstrip(".,)") if match else None

    def _clean_path(self, path: str) -> str:
        path = path.strip().strip('"').strip("'")
        return str(PurePath(path))
