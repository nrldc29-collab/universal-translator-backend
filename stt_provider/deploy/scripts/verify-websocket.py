"""
WebSocket verification script for True Streaming STT Provider.

This script verifies that the WebSocket streaming endpoint is functioning correctly
by connecting to the server, sending synthetic audio, and confirming the expected
session lifecycle events are received.

Usage:
    python verify-websocket.py --base-url http://localhost:8000 --api-key your-key

Environment Variables:
    None - uses command-line arguments

Example:
    python verify-websocket.py --base-url http://localhost:8000 --api-key sk-123456
"""
import argparse
import asyncio
import json
import logging
import math
import struct
from urllib.parse import quote

import websockets

logger = logging.getLogger(__name__)


def make_sine_pcm16(duration_seconds: float = 0.5, sample_rate: int = 16000) -> bytes:
    """
    Generate synthetic PCM16 audio data as a sine wave.
    
    Creates a sine wave at 440 Hz (A4 note) with 20% amplitude, encoded as
    16-bit signed little-endian PCM audio.
    
    Args:
        duration_seconds: Duration of audio in seconds
        sample_rate: Sample rate in Hz (default: 16000)
        
    Returns:
        Bytes containing PCM16 audio data
    """
    frames = bytearray()

    for i in range(int(duration_seconds * sample_rate)):
        sample = 0.2 * math.sin(2 * math.pi * 440.0 * i / sample_rate)
        frames.extend(struct.pack("<h", int(sample * 32767)))

    logger.debug(f"Generated {len(frames)} bytes of PCM16 sine wave audio")
    return bytes(frames)


def http_to_ws_url(base_url: str) -> str:
    """
    Convert an HTTP base URL to a WebSocket streaming URL.
    
    Transforms an HTTP/HTTPS base URL into the corresponding WebSocket URL
    for the STT streaming endpoint.
    
    Args:
        base_url: HTTP or HTTPS base URL (e.g., http://localhost:8000)
        
    Returns:
        WebSocket URL for the streaming endpoint (e.g., ws://localhost:8000/stt/stream)
    """
    clean = base_url.rstrip("/")

    if clean.startswith("https://"):
        ws_url = "wss://" + clean.removeprefix("https://") + "/stt/stream"
        logger.debug(f"Converted HTTPS to WSS: {base_url} -> {ws_url}")
        return ws_url

    if clean.startswith("http://"):
        ws_url = "ws://" + clean.removeprefix("http://") + "/stt/stream"
        logger.debug(f"Converted HTTP to WS: {base_url} -> {ws_url}")
        return ws_url

    ws_url = clean + "/stt/stream"
    logger.debug(f"Using provided URL as WebSocket URL: {ws_url}")
    return ws_url


async def verify_websocket(base_url: str, api_key: str) -> None:
    """
    Verify the WebSocket streaming endpoint is working correctly.
    
    Connects to the WebSocket endpoint, sends synthetic audio, and validates
    the session lifecycle events (session.started and session.flushed) are
    received as expected.
    
    Args:
        base_url: Base URL of the STT server
        api_key: API key for authentication
        
    Raises:
        RuntimeError: If session events are not received or an error occurs
        TimeoutError: If connection or response times out
    """
    ws_url = f"{http_to_ws_url(base_url)}?api_key={quote(api_key)}"
    logger.info(f"Connecting to WebSocket: {ws_url}")

    try:
        async with websockets.connect(ws_url, max_size=8 * 1024 * 1024) as ws:
            logger.info("WebSocket connected, waiting for session.started")
            first = json.loads(await asyncio.wait_for(ws.recv(), timeout=10))

            if first.get("type") != "session.started":
                logger.error(f"Expected session.started, got: {first}")
                raise RuntimeError(f"Expected session.started, got: {first}")

            logger.info("Received session.started, sending synthetic audio")
            await ws.send(make_sine_pcm16())
            await ws.send(json.dumps({"type": "flush"}))
            logger.info("Sent flush command")

            saw_flush = False

            while True:
                message = await asyncio.wait_for(ws.recv(), timeout=30)
                data = json.loads(message)
                logger.debug(f"Received event: {data.get('type')}")

                if data.get("type") == "error":
                    logger.error(f"Server returned error: {data}")
                    raise RuntimeError(f"Server returned error: {data}")

                if data.get("type") == "session.flushed":
                    saw_flush = True
                    logger.info("Received session.flushed")
                    break

            if not saw_flush:
                logger.error("Did not receive session.flushed")
                raise RuntimeError("Did not receive session.flushed")

    except asyncio.TimeoutError:
        logger.error("WebSocket operation timed out")
        raise
    except Exception as e:
        logger.error(f"WebSocket verification failed: {e}")
        raise


def main() -> int:
    """
    Main entry point for the WebSocket verification script.
    
    Parses command-line arguments and runs the verification.
    
    Returns:
        0 on success, non-zero on failure
    """
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    parser = argparse.ArgumentParser(
        description="Verify WebSocket streaming endpoint for True Streaming STT Provider"
    )
    parser.add_argument(
        "--base-url",
        required=True,
        help="Base URL of the STT server (e.g., http://localhost:8000)"
    )
    parser.add_argument(
        "--api-key",
        required=True,
        help="API key for authentication"
    )
    args = parser.parse_args()

    logger.info(f"Starting WebSocket verification for {args.base_url}")

    try:
        asyncio.run(verify_websocket(args.base_url, args.api_key))
        print("PASS: WebSocket /stt/stream")
        logger.info("WebSocket verification completed successfully")
        return 0
    except Exception as e:
        print(f"FAIL: {e}")
        logger.error(f"WebSocket verification failed: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
