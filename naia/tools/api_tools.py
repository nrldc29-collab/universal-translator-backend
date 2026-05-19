"""External API tools."""

from __future__ import annotations

from typing import Any

from tools.sandbox import SandboxManager, SandboxResult


def api_get(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    url = str(arguments.get("url", "")).strip()
    allow_external = bool(arguments.get("allow_external", False))
    if not url:
        return SandboxResult(status="failed", logs=["missing api url"])
    if not allow_external:
        return SandboxResult(
            status="blocked",
            result={"url": url},
            logs=["api request requires explicit allow_external=true"],
            risk_notes=["external API calls are restricted by default"],
        )
    return sandbox.fetch_url(url, max_chars=int(arguments.get("max_chars", 20_000)))
