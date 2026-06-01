"""
True Streaming STT Python SDK.

This package provides a Python client library for interacting with the True Streaming
Speech-to-Text API. It supports streaming transcription via WebSocket connections,
real-time event handling, and configuration management.

Main components:
- StreamingSTTClient: Main client for WebSocket-based streaming transcription
- STTEvent: Event data class for transcription results and status updates

Example usage:
    from true_streaming_stt import StreamingSTTClient, STTEvent

    client = StreamingSTTClient(
        api_key="your-api-key",
        base_url="http://localhost:8000"
    )

    for event in client.transcribe_stream(audio_stream):
        if event.type == "transcript":
            print(event.text)
"""
from backend.stt_client.client import (
    STTError,
    STTConnectionError,
    STTAuthenticationError,
    STTTranscriptionError,
    STTTimeoutError,
    STTEvent,
    StreamingSTTClient,
)

__all__ = [
    "STTError",
    "STTConnectionError",
    "STTAuthenticationError",
    "STTTranscriptionError",
    "STTTimeoutError",
    "STTEvent",
    "StreamingSTTClient",
]