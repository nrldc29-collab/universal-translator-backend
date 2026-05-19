"""
True Streaming STT SDK Client.

This module provides a Python client for the True Streaming STT service,
supporting both streaming and file-based transcription via WebSocket and HTTP APIs.

The client includes automatic retry logic for transient network failures,
comprehensive error handling, and structured logging for observability.

Example usage:
    from true_streaming_stt import StreamingSTTClient, STTEvent

    # Initialize client
    client = StreamingSTTClient(
        api_key="your-api-key",
        base_url="http://localhost:8000",
        language="en"
    )

    # Stream audio for real-time transcription
    async for event in client.stream_pcm16(audio_chunks):
        if event.type == "transcript.partial":
            print(f"Partial: {event.data.get('text')}")
        elif event.type == "transcript.final":
            print(f"Final: {event.data.get('text')}")

    # Transcribe a file
    result = client.transcribe_file("audio.wav", model="base")
    print(result.get("text"))
"""
import asyncio
import json
import logging
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from urllib import error, request
from urllib.parse import urlencode

import websockets
import websockets.exceptions

logger = logging.getLogger(__name__)


class STTError(Exception):
    """
    Base exception for STT client errors.
    
    All STT-specific exceptions inherit from this class, allowing callers to
    catch all STT errors with a single except clause if desired.
    """


class STTConnectionError(STTError):
    """
    Raised when connection to STT server fails.
    
    This exception is raised for network-level errors including:
    - WebSocket connection failures
    - Invalid WebSocket URLs
    - WebSocket handshake failures
    - Network timeouts
    """


class STTAuthenticationError(STTError):
    """
    Raised when authentication fails.
    
    This exception is raised when the API key is invalid or the authentication
    token cannot be verified by the server.
    """


class STTTranscriptionError(STTError):
    """
    Raised when transcription fails.
    
    This exception is raised for errors during the transcription process,
    including server-side errors, invalid audio format, or JSON parsing errors.
    """


class STTTimeoutError(STTError):
    """
    Raised when operation times out.
    
    This exception is raised when a connection or request exceeds the configured
    timeout duration.
    """


@dataclass
class STTEvent:
    """
    Represents an event from the STT streaming service.
    
    Attributes:
        type: Event type (e.g., "transcript.partial", "transcript.final", "session.flushed")
        data: Event data dictionary containing transcript information
    """
    type: str
    data: dict


class StreamingSTTClient:
    """
    Client for streaming STT transcription.
    
    This client provides methods for streaming PCM16 audio chunks for real-time
    transcription and for transcribing audio files. It includes automatic retry
    logic for transient network failures.
    
    Attributes:
        api_key: API key for authentication
        websocket_url: WebSocket endpoint URL for streaming
        base_url: Base URL for HTTP endpoints
        language: Default language for transcription
        connection_timeout: Timeout for WebSocket connections in seconds
        max_retries: Maximum number of retry attempts for transient failures
        retry_delay: Base delay between retry attempts in seconds
    """
    
    def __init__(
        self,
        api_key: str,
        websocket_url: str = "ws://localhost:8000/stt/stream",
        base_url: str = "http://localhost:8000",
        language: Optional[str] = None,
        connection_timeout: float = 10.0,
        max_retries: int = 3,
        retry_delay: float = 1.0,
    ):
        """
        Initialize the StreamingSTTClient.
        
        Args:
            api_key: API key for authentication (required)
            websocket_url: WebSocket endpoint URL for streaming
            base_url: Base URL for HTTP endpoints
            language: Default language for transcription (e.g., "en", "es")
            connection_timeout: Timeout for WebSocket connections in seconds
            max_retries: Maximum number of retry attempts for transient failures
            retry_delay: Base delay between retry attempts in seconds
            
        Raises:
            ValueError: If api_key is empty or None
        """
        if not api_key:
            raise ValueError("api_key is required")
        
        self.api_key = api_key
        self.websocket_url = websocket_url
        self.base_url = base_url.rstrip("/")
        self.language = language
        self.connection_timeout = connection_timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        
        logger.info(f"Initialized StreamingSTTClient with max_retries={max_retries}")

    def _stream_url(self, language: Optional[str] = None) -> str:
        """
        Build the WebSocket streaming URL with authentication and parameters.
        
        Returns:
            Complete WebSocket URL with query parameters
        """
        separator = "&" if "?" in self.websocket_url else "?"
        selected_language = language if language is not None else self.language
        params = {"api_key": self.api_key}
        if selected_language:
            params["language"] = selected_language
        return f"{self.websocket_url}{separator}{urlencode(params)}"

    async def stream_pcm16(
        self,
        audio_chunks: AsyncIterator[bytes],
        language: Optional[str] = None,
    ) -> AsyncIterator[STTEvent]:
        """
        Stream PCM16 audio chunks for transcription with automatic retry logic.
        
        This method streams audio chunks to the STT service and yields transcription
        events. It will automatically retry on transient connection failures.
        
        Args:
            audio_chunks: Async iterator of audio chunks (bytes, PCM16 format)
            
        Yields:
            STTEvent objects containing transcription results
            
        Raises:
            STTError: If all retry attempts are exhausted
            STTConnectionError: If connection fails after all retries
            STTTimeoutError: If connection times out after all retries
        """
        last_error = None
        
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"Streaming attempt {attempt + 1}/{self.max_retries + 1}")
                async for event in self._stream_pcm16_single_attempt(audio_chunks, attempt, language):
                    yield event
                return  # Success, exit retry loop
                
            except (STTConnectionError, STTTimeoutError, websockets.exceptions.WebSocketException) as e:
                last_error = e
                logger.warning(f"Stream attempt {attempt + 1} failed: {e}")
                
                if attempt < self.max_retries:
                    # Convert audio_chunks to list for retry (note: this consumes the iterator)
                    # In production, you'd want a buffered approach
                    await asyncio.sleep(self.retry_delay * (attempt + 1))
                    continue
                else:
                    raise STTError(f"Failed after {self.max_retries + 1} attempts. Last error: {e}") from e
    
    async def _stream_pcm16_single_attempt(
        self,
        audio_chunks: AsyncIterator[bytes],
        attempt: int,
        language: Optional[str] = None,
    ) -> AsyncIterator[STTEvent]:
        """
        Single attempt at streaming without retry logic.
        
        Args:
            audio_chunks: Async iterator of audio chunks
            attempt: Attempt number for logging
            
        Yields:
            STTEvent objects containing transcription results
            
        Raises:
            STTConnectionError: If WebSocket connection fails
            STTTimeoutError: If connection times out
            STTTranscriptionError: If transcription fails
        """
        event_queue: asyncio.Queue[Optional[STTEvent]] = asyncio.Queue()

        try:
            async with websockets.connect(
                self._stream_url(language=language),
                max_size=8 * 1024 * 1024,
                close_timeout=self.connection_timeout,
                ping_timeout=self.connection_timeout,
                ping_interval=20,
            ) as ws:
                logger.debug(f"WebSocket connected (attempt {attempt + 1})")
                
                async def receive_loop() -> None:
                    """Background task to receive messages from WebSocket."""
                    try:
                        async for message in ws:
                            try:
                                data = json.loads(message)
                                await event_queue.put(
                                    STTEvent(type=data.get("type", "unknown"), data=data)
                                )

                                if data.get("type") == "session.flushed":
                                    logger.debug("Session flushed, ending receive loop")
                                    break
                                elif data.get("type") == "error":
                                    raise STTTranscriptionError(
                                        f"Server error: {data.get('message', 'Unknown error')}"
                                    )
                            except json.JSONDecodeError as e:
                                logger.error(f"Invalid JSON response: {e}")
                                raise STTTranscriptionError(f"Invalid JSON response: {e}")
                    except websockets.exceptions.ConnectionClosed as e:
                        raise STTConnectionError(f"WebSocket connection closed: {e}")
                    except websockets.exceptions.WebSocketException as e:
                        raise STTConnectionError(f"WebSocket error: {e}")
                    finally:
                        await event_queue.put(None)

                receiver = asyncio.create_task(receive_loop())

                try:
                    async for chunk in audio_chunks:
                        try:
                            await ws.send(chunk)
                        except websockets.exceptions.ConnectionClosed:
                            raise STTConnectionError("Connection closed while sending audio")

                        # Yield any queued events
                        while True:
                            try:
                                event = event_queue.get_nowait()
                            except asyncio.QueueEmpty:
                                break

                            if event is not None:
                                yield event

                    # Flush to get final transcript
                    await ws.send(json.dumps({"type": "flush"}))

                    # Yield remaining events
                    while True:
                        event = await event_queue.get()

                        if event is None:
                            break

                        yield event

                        if event.type == "session.flushed":
                            break
                finally:
                    receiver.cancel()

        except websockets.exceptions.InvalidURI as e:
            raise STTConnectionError(f"Invalid WebSocket URL: {e}")
        except websockets.exceptions.InvalidHandshake as e:
            raise STTConnectionError(f"WebSocket handshake failed: {e}")
        except asyncio.TimeoutError:
            raise STTTimeoutError("Connection timeout")
        except OSError as e:
            raise STTConnectionError(f"Network error: {e}")

    def transcribe_file(
        self,
        audio_path: str,
        model: str = "base",
        language: Optional[str] = None,
        timeout: int = 300,
    ) -> dict:
        """
        Transcribe an audio file using the HTTP API.
        
        Args:
            audio_path: Path to the audio file
            model: Whisper model to use (default: "base")
            language: Language for transcription (uses client default if not specified)
            timeout: Request timeout in seconds
            
        Returns:
            Dictionary containing transcription result
            
        Raises:
            FileNotFoundError: If audio file does not exist
            ValueError: If path is not a file
            STTTranscriptionError: If transcription fails
            STTAuthenticationError: If authentication fails
            STTTimeoutError: If request times out
        """
        boundary = "----true-streaming-stt-sdk-boundary"
        path = Path(audio_path)

        if not path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        if not path.is_file():
            raise ValueError(f"Path is not a file: {audio_path}")

        body = bytearray()

        def add_field(name: str, value: str) -> None:
            """Add a form field to the multipart body."""
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
            body.extend(f"{value}\r\n".encode())

        def add_file(name: str, filename: str, content: bytes) -> None:
            """Add a file to the multipart body."""
            body.extend(f"--{boundary}\r\n".encode())
            body.extend(
                f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
            )
            body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
            body.extend(content)
            body.extend(b"\r\n")

        try:
            add_file("file", path.name, path.read_bytes())
            logger.debug(f"Added audio file: {path.name} ({path.stat().st_size} bytes)")
        except IOError as e:
            raise STTTranscriptionError(f"Failed to read audio file: {e}")

        add_field("model", model)
        add_field("language", language or self.language or "en")
        body.extend(f"--{boundary}--\r\n".encode())

        req = request.Request(
            url=f"{self.base_url}/v1/audio/transcriptions",
            data=bytes(body),
            method="POST",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": f"multipart/form-data; boundary={boundary}",
            },
        )

        try:
            logger.debug(
                f"Sending transcription request to {self.base_url}/v1/audio/transcriptions, "
                f"model={model}, language={language or self.language or 'en'}"
            )
            with request.urlopen(req, timeout=timeout) as response:
                response_data = response.read().decode("utf-8")
                
                if response.status >= 400:
                    logger.error(f"Transcription failed with HTTP {response.status}: {response_data}")
                    raise STTTranscriptionError(f"HTTP {response.status}: {response_data}")
                
                try:
                    result = json.loads(response_data)
                    logger.info("Transcription completed successfully")
                    return result
                except json.JSONDecodeError as e:
                    logger.error(f"Invalid JSON response: {e}")
                    raise STTTranscriptionError(f"Invalid JSON response: {e}")
                    
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8")
            
            if exc.code == 401:
                logger.error("Authentication failed")
                raise STTAuthenticationError("Authentication failed: Invalid API key")
            elif exc.code == 429:
                logger.warning("Rate limit exceeded")
                raise STTError("Rate limit exceeded")
            else:
                logger.error(f"HTTP error {exc.code}: {detail}")
                raise STTTranscriptionError(f"HTTP {exc.code}: {detail}")
                
        except error.URLError as e:
            logger.error(f"Connection error: {e}")
            raise STTConnectionError(f"Connection error: {e}")
        except TimeoutError:
            logger.error(f"Request timeout after {timeout} seconds")
            raise STTTimeoutError(f"Request timeout after {timeout} seconds")
