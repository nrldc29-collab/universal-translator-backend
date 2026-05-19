"""NAIA assistant integration for the Anai Translator backend.

Wraps a singleton :class:`CognitiveRuntimeKernel` from the bundled
``naia/`` package and exposes a small, translator-friendly chat
interface used by ``/api/assistant/chat`` and ``/ws/assistant``.

The naia codebase uses top-level absolute imports (``from runtime.kernel
import ...``) because it was authored as its own project.  Rather than
rewriting every import to ``from naia.runtime.kernel import ...`` we
simply prepend the bundled ``naia/`` directory to ``sys.path`` once at
module import time.  This is contained and reversible: nothing else in
the translator imports from those top-level package names.
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import sys
import threading
from pathlib import Path
from typing import Any

logger = logging.getLogger("anai_translator.assistant")

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------

MAX_MESSAGE_LENGTH = 4000
KERNEL_TIMEOUT_SECONDS = 30.0

# ---------------------------------------------------------------------------
# Bootstrap naia into sys.path
# ---------------------------------------------------------------------------

_NAIA_DIR = Path(__file__).resolve().parent.parent / "naia"
if _NAIA_DIR.is_dir() and str(_NAIA_DIR) not in sys.path:
    sys.path.insert(0, str(_NAIA_DIR))

# These imports rely on the sys.path insertion above.  Failures are
# surfaced lazily so the translator can still boot if naia is missing
# (the /api/assistant/chat endpoint will return HTTP 503 instead).
_IMPORT_ERROR: Exception | None = None
try:
    from runtime.kernel import CognitiveRuntimeKernel, KernelResponse  # type: ignore  # noqa: E402
except (ImportError, ModuleNotFoundError, RuntimeError) as exc:  # pragma: no cover - depends on env
    CognitiveRuntimeKernel = None  # type: ignore[assignment]
    KernelResponse = None  # type: ignore[assignment]
    _IMPORT_ERROR = exc
    logger.warning("naia kernel unavailable: %s", exc)


# ---------------------------------------------------------------------------
# Singleton kernel
# ---------------------------------------------------------------------------

_kernel_lock = threading.Lock()
_kernel: "CognitiveRuntimeKernel | None" = None


def is_available() -> bool:
    """Return True if the naia kernel can be instantiated."""
    return _IMPORT_ERROR is None and CognitiveRuntimeKernel is not None


def import_error() -> str | None:
    """Return the import error message, if any."""
    return None if _IMPORT_ERROR is None else f"{type(_IMPORT_ERROR).__name__}: {_IMPORT_ERROR}"


def get_kernel() -> "CognitiveRuntimePipeline":
    """Return the process-wide kernel singleton, initializing on demand."""
    global _kernel
    if not is_available():
        raise RuntimeError(
            "naia kernel is not available: " + (import_error() or "unknown error")
        )
    with _kernel_lock:
        if _kernel is None:
            logger.info("Initializing naia kernel for translator assistant")
            _kernel = CognitiveRuntimeKernel(instance_id="translator-assistant")
    return _kernel  # type: ignore[return-value]


# ---------------------------------------------------------------------------
# Input validation
# ---------------------------------------------------------------------------

_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


def _sanitize_message(message: str) -> str:
    """Strip control characters and enforce length limit."""
    cleaned = _CONTROL_CHAR_RE.sub("", message).strip()
    if len(cleaned) > MAX_MESSAGE_LENGTH:
        cleaned = cleaned[:MAX_MESSAGE_LENGTH]
        logger.info("assistant_message_truncated to=%d", MAX_MESSAGE_LENGTH)
    return cleaned


# ---------------------------------------------------------------------------
# Chat interface
# ---------------------------------------------------------------------------

async def chat(
    message: str,
    *,
    source: str = "http",
    translation_context: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Send a user message to the naia assistant and return a response dict.

    Parameters
    ----------
    message:
        The user's chat message.
    source:
        Where the message came from (``"http"``, ``"websocket"``, ``"mobile"``).
        Propagated to naia for telemetry.
    translation_context:
        Optional snapshot of what the user just translated.  Expected keys::

            {
              "source_language": "en",
              "target_language": "es",
              "source_text":    "Hello, how are you?",
              "translated_text": "Hola, ¿cómo estás?",
            }

        When present, this is prepended to the user's message as
        contextual framing so naia can answer questions like "what does
        that idiom mean?" or "make it more formal."
    metadata:
        Arbitrary metadata forwarded to naia's pipeline.

    Returns
    -------
    A JSON-serializable dict with at least ``response``, ``session_id``,
    ``confidence``, and ``intent``.
    """
    if not message or not message.strip():
        raise ValueError("message must be non-empty")

    message = _sanitize_message(message)
    kernel = get_kernel()

    framed = _frame_message(message, translation_context)
    meta = dict(metadata or {})
    if translation_context:
        meta["translation_context"] = translation_context

    try:
        response: KernelResponse = await asyncio.wait_for(
            kernel.process_user_input(  # type: ignore[name-defined]
                framed,
                source=source,
                metadata=meta,
            ),
            timeout=KERNEL_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        logger.warning("assistant_timeout source=%s", source)
        raise RuntimeError("Assistant response timed out. Please try again.") from None

    return {
        "session_id": response.session_id,
        "response": response.response,
        "confidence": response.confidence,
        "intent": response.intent,
        "task_type": response.task_type,
        "cognitive_mode": response.cognitive_mode,
    }


def _frame_message(message: str, ctx: dict[str, Any] | None) -> str:
    """Prepend translation context to the user message, if provided."""
    if not ctx:
        return message
    src_lang = ctx.get("source_language") or ctx.get("source_lang") or "?"
    tgt_lang = ctx.get("target_language") or ctx.get("target_lang") or "?"
    src_text = (ctx.get("source_text") or "").strip()
    tgt_text = (ctx.get("translated_text") or "").strip()
    if not src_text and not tgt_text:
        return message
    frame_lines = ["[translation context]"]
    if src_text:
        frame_lines.append(f"  {src_lang}: {src_text}")
    if tgt_text:
        frame_lines.append(f"  {tgt_lang}: {tgt_text}")
    frame_lines.append("")
    frame_lines.append(f"[user] {message}")
    return "\n".join(frame_lines)


__all__ = ["chat", "get_kernel", "is_available", "import_error"]
