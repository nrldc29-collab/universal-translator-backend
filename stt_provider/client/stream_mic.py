"""
Microphone streaming client for STT transcription.

This script captures audio from the microphone and streams it to the STT service
for real-time transcription. It includes automatic retry logic and proper signal handling.
"""
import argparse
import asyncio
import json
import logging
import queue
import sys
from typing import Optional

import websockets
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

try:
    import sounddevice as sd
except ImportError:
    print("Missing dependency: sounddevice")
    print("Install it with: pip install sounddevice")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Audio configuration
SAMPLE_RATE = 16000
CHANNELS = 1
BLOCK_MS = 30
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_MS / 1000)


def redact_url(url: str) -> str:
    """
    Redact sensitive parameters from a URL for logging.
    
    Args:
        url: URL to redact
        
    Returns:
        URL with sensitive parameters (api_key, token, etc.) redacted
    """
    parts = urlsplit(url)
    pairs = parse_qsl(parts.query, keep_blank_values=True)
    redacted = []

    for key, value in pairs:
        if key.lower() in {"api_key", "token", "access_token", "key"}:
            redacted.append((key, value[:4] + "***" if value else "***"))
        else:
            redacted.append((key, value))

    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(redacted), parts.fragment))


async def receive_events(ws) -> None:
    """
    Receive and display transcription events from the WebSocket.
    
    Args:
        ws: WebSocket connection
    """
    async for message in ws:
        try:
            data = json.loads(message)
            event_type = data.get("type")

            if event_type == "session.started":
                print("Session started")
                print(json.dumps(data, indent=2))
                logger.info("Session started")

            elif event_type == "transcript.partial":
                print(f"\rPARTIAL: {data.get('text', '')}", end="", flush=True)

            elif event_type == "transcript.final":
                print()
                print(f"FINAL: {data.get('text', '')}")
                logger.info(f"Final transcript: {data.get('text', '')}")

            elif event_type == "error":
                print()
                print(f"ERROR [{data.get('code')}]: {data.get('message')}")
                logger.error(f"Server error [{data.get('code')}]: {data.get('message')}")

            else:
                print()
                print(json.dumps(data, indent=2))
                logger.debug(f"Unknown event type: {event_type}")

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON message: {e}")


async def send_microphone(ws, audio_queue: queue.Queue) -> None:
    """
    Send audio chunks from the queue to the WebSocket.
    
    Args:
        ws: WebSocket connection
        audio_queue: Queue containing audio chunks
    """
    while True:
        audio_chunk = await asyncio.to_thread(audio_queue.get)

        if audio_chunk is None:
            logger.info("Sending flush command")
            await ws.send(json.dumps({"type": "flush"}))
            return

        await ws.send(audio_chunk)


async def stream_microphone(
    url: str,
    max_retries: int = 3,
    retry_delay: float = 1.0,
) -> None:
    """
    Stream microphone audio to the STT service with automatic retry logic.
    
    Args:
        url: WebSocket URL with authentication parameters
        max_retries: Maximum number of connection retry attempts
        retry_delay: Base delay between retry attempts in seconds
        
    Raises:
        Exception: If all retry attempts are exhausted
    """
    audio_queue: queue.Queue[Optional[bytes]] = queue.Queue()

    def audio_callback(indata, frames, time_info, status):
        """
        Callback for audio stream from microphone.
        
        Args:
            indata: Audio data
            frames: Number of frames
            time_info: Timing information
            status: PortAudio status
        """
        if status:
            logger.warning(f"Audio warning: {status}")
            print(f"Audio warning: {status}", file=sys.stderr)

        audio_queue.put(bytes(indata))

    last_error = None
    
    for attempt in range(max_retries + 1):
        try:
            logger.info(f"Connection attempt {attempt + 1}/{max_retries + 1}")
            async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
                print(f"Connected to {redact_url(url)}")
                logger.info(f"Connected to {redact_url(url)}")
                print("Speak into your microphone.")
                print("Press Ctrl+C to stop.")

                receiver = asyncio.create_task(receive_events(ws))
                sender = asyncio.create_task(send_microphone(ws, audio_queue))

                try:
                    with sd.RawInputStream(
                        samplerate=SAMPLE_RATE,
                        blocksize=BLOCK_SIZE,
                        channels=CHANNELS,
                        dtype="int16",
                        callback=audio_callback,
                    ):
                        await sender
                except asyncio.CancelledError:
                    logger.info("Streaming cancelled by user")
                    pass
                finally:
                    receiver.cancel()
                    logger.info("Stopped streaming")
                return  # Success, exit retry loop
                
        except (websockets.exceptions.WebSocketException, OSError) as e:
            last_error = e
            logger.warning(f"Connection attempt {attempt + 1} failed: {e}")
            
            if attempt < max_retries:
                print(f"Connection attempt {attempt + 1} failed: {e}")
                print(f"Retrying in {retry_delay * (attempt + 1):.1f} seconds...")
                await asyncio.sleep(retry_delay * (attempt + 1))
            else:
                print(f"Failed after {max_retries + 1} attempts: {e}")
                logger.error(f"Failed after {max_retries + 1} attempts: {e}")
                raise


def main() -> int:
    """
    Main entry point for the microphone streaming client.
    
    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(description="Stream microphone audio to the STT provider.")
    parser.add_argument("--url", default="ws://localhost:8000/stt/stream")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument("--language", default=None, help="Language code (e.g., 'en', 'es')")
    parser.add_argument("--max-retries", type=int, default=3, help="Maximum connection retry attempts")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Delay between retries in seconds")
    args = parser.parse_args()

    # Build WebSocket URL with parameters
    separator = "&" if "?" in args.url else "?"
    url = f"{args.url}{separator}api_key={args.api_key}"

    if args.language:
        url += f"&language={args.language}"

    try:
        logger.info(f"Starting microphone streaming to {redact_url(url)}")
        asyncio.run(
            stream_microphone(
                url,
                max_retries=args.max_retries,
                retry_delay=args.retry_delay
            )
        )
    except KeyboardInterrupt:
        print()
        print("Stopped.")
        logger.info("Stopped by user (KeyboardInterrupt)")
        return 0
    except Exception as e:
        print(f"\nError: {e}", file=sys.stderr)
        logger.error(f"Error: {e}", exc_info=True)
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
