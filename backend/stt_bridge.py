"""STT bridge — unified transcription interface for local and streaming backends.

When ``STT_PROVIDER=local`` (default), delegates to the existing
:class:`WhisperSpeechToText` which loads faster-whisper directly in-process.

When ``STT_PROVIDER=streaming``, routes transcription requests through the
embedded True Streaming STT Provider via its HTTP and WebSocket APIs using
the bundled :class:`StreamingSTTClient` SDK.
"""

from __future__ import annotations

import logging
from typing import Optional

from backend.config import (
    get_stt_provider,
    get_stt_provider_api_key,
    get_stt_provider_url,
    get_stt_provider_ws_url,
    get_whisper_compute_type,
    get_whisper_device,
    get_whisper_model_size,
)

logger = logging.getLogger("anai_translator.stt_bridge")


class STTBridge:
    """Unified speech-to-text interface.

    Selects the active backend based on the ``STT_PROVIDER`` env var and
    exposes a common ``transcribe()`` method so callers don't need to know
    which engine is in use.
    """

    def __init__(self) -> None:
        self._provider = get_stt_provider()
        self._local_stt: Optional[object] = None
        self._streaming_client: Optional[object] = None
        logger.info("STT bridge initialized: provider=%s", self._provider)

    # ------------------------------------------------------------------
    # Lazy accessors
    # ------------------------------------------------------------------

    @property
    def provider(self) -> str:
        return self._provider

    @property
    def is_streaming(self) -> bool:
        return self._provider == "streaming"

    def _get_local_stt(self):
        """Lazily instantiate the in-process Whisper engine."""
        if self._local_stt is None:
            from speech import WhisperSpeechToText

            self._local_stt = WhisperSpeechToText(
                model_size=get_whisper_model_size(),
                device=get_whisper_device(),
                compute_type=get_whisper_compute_type(),
            )
        return self._local_stt

    def _get_streaming_client(self):
        """Lazily instantiate the streaming STT client."""
        if self._streaming_client is None:
            from backend.stt_client import StreamingSTTClient

            api_key = get_stt_provider_api_key()
            base_url = get_stt_provider_url()
            ws_url = get_stt_provider_ws_url()

            self._streaming_client = StreamingSTTClient(
                api_key=api_key,
                websocket_url=ws_url,
                base_url=base_url,
            )
            logger.info(
                "StreamingSTTClient created: base_url=%s, ws_url=%s",
                base_url,
                ws_url,
            )
        return self._streaming_client

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def preload(self) -> bool:
        """Preload the STT model (local mode) or verify connectivity (streaming mode)."""
        if self.is_streaming:
            return self._check_streaming_health()
        return self._get_local_stt().preload()

    def transcribe(self, audio_path: str, source_language: str | None = None) -> str:
        """Transcribe an audio file to text.

        Parameters
        ----------
        audio_path:
            Path to the audio file on disk.
        source_language:
            Optional language hint (e.g. ``"en"``).

        Returns
        -------
        The transcribed text string.
        """
        if self.is_streaming:
            return self._transcribe_streaming(audio_path, source_language)
        return self._get_local_stt().transcribe(audio_path, source_language)

    def queue_snapshot(self) -> dict:
        """Return queue statistics (local mode only)."""
        if not self.is_streaming:
            return self._get_local_stt().queue_snapshot()
        return {
            "provider": "streaming",
            "queued": 0,
            "active": 0,
            "max_depth": 0,
            "rejected": 0,
            "avg_wait_seconds": 0,
            "max_wait_seconds": 0,
        }

    # ------------------------------------------------------------------
    # Streaming backend helpers
    # ------------------------------------------------------------------

    def _transcribe_streaming(self, audio_path: str, source_language: str | None = None) -> str:
        """Transcribe via the streaming STT provider's REST API."""
        client = self._get_streaming_client()
        language = source_language or "en"
        try:
            result = client.transcribe_file(
                audio_path,
                model="base",
                language=language,
            )
            text = result.get("text", "")
            logger.info(
                "Streaming transcription complete: %d chars, model=%s",
                len(text),
                result.get("model", "?"),
            )
            return text
        except (ConnectionError, TimeoutError, RuntimeError, ValueError) as exc:
            logger.error("Streaming STT transcription failed: %s", exc)
            raise RuntimeError(f"Streaming STT provider error: {exc}") from exc

    def _check_streaming_health(self) -> bool:
        """Verify the streaming STT provider is reachable."""
        import urllib.request
        import urllib.error

        url = get_stt_provider_url() + "/health"
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=5) as resp:
                if resp.status == 200:
                    logger.info("Streaming STT provider health check: OK")
                    return True
        except (URLError, TimeoutError, ConnectionError) as exc:
            logger.warning("Streaming STT provider health check failed: %s", exc)
        return False

    def get_streaming_client(self):
        """Return the :class:`StreamingSTTClient` (only valid in streaming mode)."""
        if not self.is_streaming:
            raise RuntimeError("Streaming client not available when STT_PROVIDER=local")
        return self._get_streaming_client()
