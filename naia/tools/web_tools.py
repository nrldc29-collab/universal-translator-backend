"""Controlled web tools."""

from __future__ import annotations

import re
from typing import Any

from tools.sandbox import SandboxManager, SandboxResult


def fetch_url(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    url = _sanitize_text(str(arguments.get("url", "")), limit=2048)
    max_chars = int(arguments.get("max_chars", 20_000))
    if not url:
        return SandboxResult(status="failed", logs=["missing url"])
    return sandbox.fetch_url(url, max_chars=max_chars)


def web_search(arguments: dict[str, Any], sandbox: SandboxManager) -> SandboxResult:
    query = _sanitize_text(str(arguments.get("query", "")), limit=512)
    max_results = int(arguments.get("max_results", 5))
    if not query:
        return SandboxResult(status="failed", logs=["missing query"])
    return sandbox.search_web(query, max_results=max_results)


def _sanitize_text(text: str, *, limit: int) -> str:
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)
    text = re.sub(r"(?i)ignore previous instructions.*", "", text)
    return text.strip()[:limit]
