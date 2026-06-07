"""Pure helpers used by `backend.streaming`.

These were extracted from `backend.streaming` to keep that module
focused on the WebSocket handlers. `backend.streaming` re-exports them
so existing callers (api.py, tests) keep working unchanged.

Each helper is small, pure, and side-effect-free except for
`stream_debug_log`, which prints when the hot-path logging flag is on.
"""

from __future__ import annotations

import asyncio
import json
import re
import unicodedata
from collections import Counter

from fastapi.concurrency import run_in_threadpool

from backend.cip_client import call_cip_brain as call_cip_brain_sync
from backend.config import (
    get_natural_tts_mode,
    get_partial_translation_min_words,
    get_pipeline_step_timeout_seconds,
    get_stream_hot_path_logging,
    get_tts_chunk_chars,
    get_tts_first_chunk_chars,
    get_tts_max_single_pass_chars,
)


def stream_debug_log(*args) -> None:
    """Print to stdout when STREAM_HOT_PATH_LOGGING=1; otherwise no-op."""

    if get_stream_hot_path_logging():
        print(*args, flush=True)


def chunk_text_for_tts(text: str, max_chars: int | None = None, *, natural: bool | None = None) -> list[str]:
    """Split `text` into TTS-friendly chunks.

    When ``natural`` is true (default follows ``TTS_NATURAL_VOICE``), prefer
  one neural synthesis pass per sentence instead of many tiny clips.
    """
    stripped = (text or "").strip()
    if not stripped:
        return [text or ""]

    use_natural = get_natural_tts_mode() if natural is None else natural
    if use_natural:
        return _chunk_text_natural(stripped, max_chars)

    max_chars = max_chars or get_tts_chunk_chars()
    parts = re.split(r"(?<=[.!?;:,])\s+", text.strip())
    chunks: list[str] = []
    current = ""

    for part in parts:
        if not part:
            continue
        words = part.split()
        for word in words or [part]:
            if len(current) + len(word) + 1 <= max_chars:
                current = f"{current} {word}".strip()
                continue
            if current:
                chunks.append(current)
            current = word

    if current:
        chunks.append(current)

    if chunks:
        first_max = max(6, min(get_tts_first_chunk_chars(), max_chars))
        if len(chunks[0]) > first_max:
            first = chunks[0][:first_max].rstrip()
            rest = chunks[0][first_max:].lstrip()
            new_chunks = [first]
            if rest:
                new_chunks.extend(chunk_text_for_tts(rest, max_chars))
            chunks = new_chunks + chunks[1:]

    return chunks or [text]


def _chunk_text_natural(text: str, max_chars: int | None = None) -> list[str]:
    """Sentence-level chunks — avoids robotic micro-clips between words."""
    max_pass = get_tts_max_single_pass_chars()
    if len(text) <= max_pass:
        return [text]

    sentences = [part.strip() for part in re.split(r"(?<=[.!?])\s+", text) if part.strip()]
    if not sentences:
        return [text]

    chunks: list[str] = []
    current = ""
    for sentence in sentences:
        if len(sentence) > max_pass:
            if current:
                chunks.append(current)
                current = ""
            chunks.extend(chunk_text_for_tts(sentence, max_chars=max_pass, natural=False))
            continue
        candidate = f"{current} {sentence}".strip() if current else sentence
        if current and len(candidate) > max_pass:
            chunks.append(current)
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current)
    return chunks or [text]


def should_translate_partial(text: str) -> bool:
    """Return True when a partial transcript is worth translating live."""

    normalized = text.strip()
    if not normalized:
        return False
    return (
        bool(re.search(r"[.!?;:,]\s*$", normalized))
        or len(normalized.split()) >= get_partial_translation_min_words()
    )


def normalize_live_text(text: str) -> str:
    """Collapse whitespace in a live caption string."""

    return re.sub(r"\s+", " ", (text or "").strip())


def normalized_word(value: str) -> str:
    """Strip diacritics and surrounding punctuation, lowercase."""

    folded = unicodedata.normalize("NFKD", value or "")
    folded = "".join(char for char in folded if not unicodedata.combining(char))
    return re.sub(r"^[^\w]+|[^\w]+$", "", folded).lower()


def folded_live_text(value: str) -> str:
    return " ".join(normalized_word(word) for word in normalize_live_text(value).split())


def live_translation_redundant(previous: str, current: str) -> bool:
    """Return True when `current` is already covered by spoken `previous` text."""

    current_tokens = [token for token in folded_live_text(current).split() if token]
    if not current_tokens:
        return True
    previous_tokens = [token for token in folded_live_text(previous).split() if token]
    if not previous_tokens:
        return False

    previous_counts = Counter(previous_tokens)
    current_counts = Counter(current_tokens)
    covered = sum(min(previous_counts[token], count) for token, count in current_counts.items())
    return covered == sum(current_counts.values())


def is_internal_translation_artifact(text: str) -> bool:
    """Return True for debug/model prompt text that must never reach users."""

    value = normalize_live_text(text)
    if not value:
        return True
    if re.match(r"^\[(?:AI|AI_ERROR|plugin-ai):", value, re.IGNORECASE):
        return True
    lowered = value.lower()
    if "ensure this " in lowered and "keep meaning:" in lowered:
        return True
    if re.search(r"\[[a-z]{2,}(?:-[a-z0-9]+)?->none\]", value, re.IGNORECASE):
        return True
    if re.match(r"^\[[a-z]{2,}(?:-[a-z0-9]+)?->[a-z]{2,}(?:-[a-z0-9]+)?\]\s+", value, re.IGNORECASE):
        return True
    return False


def live_translation_delta(previous: str, current: str) -> str:
    """Return only the newly translated words that are safe to speak live."""

    previous = normalize_live_text(previous)
    current = normalize_live_text(current)
    if not current:
        return ""
    if not previous:
        return current
    if current.lower().startswith(previous.lower()):
        return current[len(previous):].lstrip(" \t\r\n,;:.!?")

    previous_words = previous.split()
    current_words = current.split()
    common = 0
    for previous_word, current_word in zip(previous_words, current_words):
        if normalized_word(previous_word) != normalized_word(current_word):
            break
        common += 1
    if common >= len(previous_words):
        return " ".join(current_words[common:]).lstrip(" \t\r\n,;:.!?")
    return ""


def is_speakable_live_delta(text: str) -> bool:
    normalized = normalize_live_text(text)
    return len(normalized) >= 2 and bool(re.search(r"\w", normalized))


def looks_like_container_audio(data: bytes) -> bool:
    """True when bytes look like WebM/WAV/MP4 container audio, not raw PCM16."""

    if len(data) < 4:
        return False
    if data[:4] == b"\x1aE\xdf\xa3":
        return True
    if data[:4] == b"RIFF":
        return True
    if len(data) >= 8 and data[4:8] == b"ftyp":
        return True
    if data[:4] == b"OggS":
        return True
    return False


def audio_suffix_for_mime(mime_type: str | None) -> str:
    """Map a MIME type to a sensible audio file suffix."""

    value = (mime_type or "").lower()
    if "mpeg" in value or "mp3" in value:
        return ".mp3"
    if "mp4" in value or "aac" in value or "m4a" in value:
        return ".m4a"
    if "ogg" in value:
        return ".ogg"
    if "wav" in value:
        return ".wav"
    return ".webm"


def audio_suffix_for_bytes(audio_bytes: bytes | bytearray | memoryview | None, mime_type: str | None = None) -> str:
    """Infer audio suffix from container magic bytes, falling back to MIME."""

    if not audio_bytes:
        return audio_suffix_for_mime(mime_type)
    header = bytes(audio_bytes[:64])
    if len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WAVE":
        return ".wav"
    if header.startswith(b"\x1a\x45\xdf\xa3"):
        return ".webm"
    if header.startswith(b"OggS"):
        return ".ogg"
    if len(header) >= 12 and header[4:8] == b"ftyp":
        return ".m4a"
    if header.startswith(b"ID3") or header[:2] in {b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"}:
        return ".mp3"
    return audio_suffix_for_mime(mime_type)


def extract_client_voice_active(payload: dict):
    """Return the client-side VAD signal from a stream payload."""

    return payload.get("voice_active", payload.get("client_voice_active"))


def parse_provider_event(raw_message) -> dict | None:
    """Parse a raw STT provider WebSocket message into a normalised event dict.

    Bytes are decoded to UTF-8. The ``type`` field is normalised:
    ``transcript`` events are promoted to ``transcript.final`` or
    ``transcript.partial`` based on their ``is_final`` flag so that callers
    can use a simple string match without re-implementing that logic.

    Returns ``None`` for messages that cannot be decoded or parsed.
    """

    if isinstance(raw_message, bytes):
        raw_message = raw_message.decode("utf-8", errors="ignore")
    try:
        event = json.loads(raw_message)
    except (TypeError, json.JSONDecodeError, ValueError):
        return None
    if not isinstance(event, dict):
        return None
    event_type = event.get("type", "unknown")
    if event_type == "transcript":
        if event.get("is_final") is True:
            event["type"] = "transcript.final"
        else:
            event["type"] = "transcript.partial"
    return event


class PipelineStepTimeout(RuntimeError):
    """Raised when a single pipeline step exceeds its budget."""


async def run_pipeline_step(label: str, call, *args):
    """Run `call(*args)` in a threadpool with the configured timeout."""

    timeout = get_pipeline_step_timeout_seconds()
    try:
        return await asyncio.wait_for(run_in_threadpool(call, *args), timeout=timeout)
    except asyncio.TimeoutError as exc:
        raise PipelineStepTimeout(f"{label} timed out after {timeout:g}s.") from exc


async def call_cip_brain(text: str, target_language: str, session_id: str, **kwargs) -> dict | None:
    """Async wrapper around the synchronous CIP brain client."""

    return await run_in_threadpool(call_cip_brain_sync, text, target_language, session_id, **kwargs)


__all__ = [
    "stream_debug_log",
    "chunk_text_for_tts",
    "should_translate_partial",
    "normalize_live_text",
    "normalized_word",
    "folded_live_text",
    "live_translation_redundant",
    "is_internal_translation_artifact",
    "live_translation_delta",
    "is_speakable_live_delta",
    "looks_like_container_audio",
    "audio_suffix_for_mime",
    "audio_suffix_for_bytes",
    "extract_client_voice_active",
    "parse_provider_event",
    "PipelineStepTimeout",
    "run_pipeline_step",
    "call_cip_brain",
]
