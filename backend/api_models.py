"""Pydantic request/response models for the HTTP API.

Extracted from `backend.api` so the main module stays focused on routes
and lifespan wiring. `backend.api` re-exports these symbols.
"""

from __future__ import annotations

from pydantic import BaseModel


class TextTranslationRequest(BaseModel):
    text: str
    source_language: str = "en"
    target_language: str = "es"
    tone: str | None = None
    synthesize_audio: bool = False
    audio_response_format: str = "base64"
    session_id: str | None = None
    device_id: str | None = None
    speaker_name: str | None = None
    speaker_mode: str = "auto"
    translation_mode: str | None = None
    translation_provider: str | None = None
    google_tts_api_key: str | None = None


class TextToSpeechRequest(BaseModel):
    text: str
    language: str = "es"
    response_format: str = "base64"


class ImageTranslationResponse(BaseModel):
    ocr_text: str
    translated_text: str
    mime_type: str | None = None
    audio_base64: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


__all__ = [
    "TextTranslationRequest",
    "TextToSpeechRequest",
    "ImageTranslationResponse",
    "LoginRequest",
]
