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

from fastapi.concurrency import run_in_threadpool

from backend.cip_client import call_cip_brain as call_cip_brain_sync
from backend.config import (
    get_partial_translation_min_words,
    get_pipeline_step_timeout_seconds,
    get_stream_hot_path_logging,
    get_tts_chunk_chars,
    get_tts_first_chunk_chars,
)


def stream_debug_log(*args) -> None:
    """Print to stdout when STREAM_HOT_PATH_LOGGING=1; otherwise no-op."""

    if get_stream_hot_path_logging():
        print(*args, flush=True)


def chunk_text_for_tts(text: str, max_chars: int | None = None) -> list[str]:
    """Split `text` into TTS-friendly chunks, with a small first chunk.

    The first chunk is intentionally smaller (capped at
    `TTS_FIRST_CHUNK_CHARS`) so the user hears audio sooner.
    """

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


def audio_suffix_for_mime(mime_type: str | None) -> str:
    """Map a MIME type to a sensible audio file suffix."""

    value = (mime_type or "").lower()
    if "mp4" in value or "aac" in value or "m4a" in value:
        return ".m4a"
    if "ogg" in value:
        return ".ogg"
    if "wav" in value:
        return ".wav"
    return ".webm"


# Format hints that mean "already raw little-endian PCM16 samples", which the
# streaming STT provider can consume directly without transcoding.
PCM16_FORMAT_HINTS = {"pcm16", "pcm", "pcm_s16le", "s16le", "raw", "l16", "lpcm"}


def build_streaming_repair(source_text, cip_response_plan, conf_score):
    """Build structured confidence-repair options for a low-confidence final.

    Prefers the CIP brain's repair plan when available (repeat exact terms,
    confirm wording, choose meaning, switch language). Falls back to a local
    plan derived from ambiguous-word detection so repair still works when no
    brain/CIP backend is configured. Returns ``[]`` when no repair is warranted.
    """
    from backend.confidence import AMBIGUOUS_SENSES, detect_ambiguities

    if isinstance(cip_response_plan, dict):
        options = cip_response_plan.get("repair_options")
        if options:
            return options

    if conf_score >= 0.4:
        return []

    repair: list[dict] = []
    for word in detect_ambiguities(source_text)[:3]:
        senses = AMBIGUOUS_SENSES.get(word, [])[:3]
        if senses:
            repair.append({
                "type": "choose_meaning",
                "label": f"Choose meaning for '{word}'",
                "word": word,
                "options": senses,
                "priority": "normal",
            })
    if not repair:
        repair.append({
            "type": "repeat_slowly",
            "label": "Ask speaker to repeat slowly",
            "priority": "normal",
        })
    return repair


def resolve_stream_audio_mode(audio_format=None, mime_type=None):
    """Decide how to treat inbound streaming audio frames.

    Returns ``(is_pcm16, suffix)`` where ``is_pcm16`` means the frames are raw
    PCM16 and can be forwarded to the STT provider as-is, and ``suffix`` is the
    container suffix to use when transcoding compressed/containered audio (e.g.
    mobile ``.m4a`` chunks) to PCM16 first.

    The default (nothing declared) is PCM16, preserving the existing web
    streaming client's behavior. A ``wav`` container is treated as non-PCM so it
    gets re-muxed to raw 16 kHz mono PCM (dropping the header / resampling).
    """
    fmt = (audio_format or "").strip().lower().lstrip(".")
    mime = (mime_type or "").strip().lower()
    if fmt:
        if fmt in PCM16_FORMAT_HINTS:
            return True, ".wav"
        return False, "." + fmt
    if mime:
        if "pcm" in mime or "l16" in mime or "lpcm" in mime:
            return True, ".wav"
        return False, audio_suffix_for_mime(mime)
    return True, ".wav"


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
    "live_translation_delta",
    "is_speakable_live_delta",
    "audio_suffix_for_mime",
    "resolve_stream_audio_mode",
    "PCM16_FORMAT_HINTS",
    "build_streaming_repair",
    "extract_client_voice_active",
    "parse_provider_event",
    "PipelineStepTimeout",
    "run_pipeline_step",
    "call_cip_brain",
]
