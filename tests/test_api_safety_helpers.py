import asyncio

from fastapi import HTTPException

from backend.api import _normalize_language, _read_limited_upload, _safe_upload_suffix


class FakeUpload:
    def __init__(self, data: bytes):
        self.data = data

    async def read(self, size: int = -1) -> bytes:
        return self.data if size < 0 else self.data[:size]


def test_safe_upload_suffix_rejects_unknown_extension():
    assert _safe_upload_suffix("payload.exe", "audio.webm", {".webm"}) == ".webm"


def test_normalize_language_rejects_unknown_code():
    try:
        _normalize_language("xx")
    except HTTPException:
        return
    raise AssertionError("Expected HTTPException")


def test_read_limited_upload_rejects_oversized_body():
    try:
        asyncio.run(_read_limited_upload(FakeUpload(b"abcdef"), 5))
    except HTTPException:
        return
    raise AssertionError("Expected HTTPException")
