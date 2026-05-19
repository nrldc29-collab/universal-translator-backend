"""Small, route-agnostic helpers used by the HTTP API.

Extracted from `backend.api` so the main module stays focused on routing.
`backend.api` re-exports these private helpers under their original names
so existing tests and consumers keep working.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import HTTPException, UploadFile

from backend.config import LANGUAGES


HOP_BY_HOP_HEADERS = {
    "connection",
    "content-length",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}


def safe_upload_suffix(filename: str | None, default: str, allowed_suffixes: set[str]) -> str:
    """Return a safe file extension for an uploaded file.

    Falls back to the default suffix if the supplied filename has an
    extension outside the allow-list, which prevents callers from passing
    arbitrary paths into Path operations.
    """

    suffix = Path(filename or default).suffix.lower()
    return suffix if suffix in allowed_suffixes else Path(default).suffix


def normalize_language(value: str | None, default: str = "en", allow_auto: bool = False) -> str:
    """Normalize a user-supplied language code or raise HTTP 400."""

    language = (value or default).strip().lower()
    if allow_auto and language == "auto":
        return language
    if language not in LANGUAGES:
        raise HTTPException(status_code=400, detail=f"Unsupported language: {language}")
    return language


async def read_limited_upload(upload: UploadFile, max_bytes: int) -> bytes:
    """Read an upload into memory, raising HTTP 413 if it exceeds the cap."""

    data = await upload.read(max_bytes + 1)
    if len(data) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds {round(max_bytes / 1024 / 1024, 1)} MB limit.",
        )
    return data


__all__ = [
    "HOP_BY_HOP_HEADERS",
    "safe_upload_suffix",
    "normalize_language",
    "read_limited_upload",
]
