"""Core model infrastructure for NAIA - local model client and prompt templates."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from core.model_client import (
    LocalModelClient,
    ModelUnavailable,
    get_global_client,
    initialize_global_client,
)

_TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


@lru_cache(maxsize=32)
def load_template(name: str) -> str:
    """Load a prompt template from ``core/templates`` by stem or filename."""
    safe_name = name.strip().replace("\\", "/").split("/")[-1]
    if not safe_name:
        raise ValueError("template name is required")
    filename = safe_name if safe_name.endswith(".txt") else f"{safe_name}.txt"
    path = _TEMPLATE_DIR / filename
    if not path.is_file():
        raise FileNotFoundError(f"unknown prompt template: {name}")
    return path.read_text(encoding="utf-8")


__all__ = [
    "LocalModelClient",
    "ModelUnavailable",
    "get_global_client",
    "initialize_global_client",
    "load_template",
]
