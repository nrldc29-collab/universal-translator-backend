"""
WebSocket load testing script for STT server.

This script performs load testing on the True Streaming STT WebSocket endpoint
by simulating multiple concurrent clients streaming synthetic audio data. It
generates sine wave PCM16 audio and measures event throughput, error rates,
and overall system performance under load.

Usage:
    python load_test_ws.py --url ws://localhost:8000/stt/stream --clients 10 --seconds 30

Example:
    python load_test_ws.py --url ws://localhost:8000/stt/stream --clients 5 --seconds 60
"""
import argparse
import asyncio
import json
import logging
import math
import struct
import time
from typing import Dict

import websockets

logger = logging.getLogger(__name__)


def make_sine_pcm16(
    duration_seconds: float,
    sample_rate: int = 16000,
    frequency: float = 440.0,
    amplitude: float = 0.2,
) -> bytes:
    """
    Generate PCM16 audio data as a sine wave.
    
    Creates synthetic audio data by generating a sine wave at the specified
    frequency and converting it to 16-bit PCM format. This is used for load
    testing without requiring real audio files.
    
    Args:
        duration_seconds: Duration of the audio in seconds
        sample_rate: Sample rate in Hz (default: 16000)
        frequency: Frequency of the sine wave in Hz (default: 440.0)
        amplitude: Amplitude of the sine wave (0.0 to 1.0, default: 0.2)
        
    Returns:
        Raw PCM16 audio data as bytes
    """
    total_samples = int(duration_seconds * sample_rate)
    frames = bytearray()

    for i in range(total_samples):
        sample = amplitude * math.sin(2 * math.pi * frequency * i / sample_rate)
        pcm = int(max(-1.0, min(1.0, sample)) * 32767)
        frames.extend(struct.pack("<h", pcm))

    logger.debug(
        f"Generated {duration_seconds}s sine wave: {total_samples} samples, "
        f"{len(frames)} bytes"
    )
    return bytes(frames)


async def run_client(client_id: int, url: str, seconds: int) -> Dict:
    """
    Run a single WebSocket load test client.
    
    Connects to the STT WebSocket endpoint, streams synthetic audio chunks,
    and counts received events by type. Returns statistics on events received
    and any errors encountered.
    
    Args:
        client_id: Unique identifier for this client
        url: WebSocket URL to connect to
        seconds: Duration of the test in seconds
        
    Returns:
        Dictionary containing test results with event counts and error status
    """
    started_at = time.time()
    events = 0
    partials = 0
    finals = 0
    errors = 0

    audio_chunk = make_sine_pcm16(duration_seconds=0.03)

    logger.info(f"Client {client_id} starting load test for {seconds} seconds")

    try:
        async with websockets.connect(url, max_size=8 * 1024 * 1024) as ws:
            logger.debug(f"Client {client_id} connected to {url}")
            
            while time.time() - started_at < seconds:
                await ws.send(audio_chunk)

                try:
                    message = await asyncio.wait_for(ws.recv(), timeout=0.01)
                    data = json.loads(message)
                    events += 1

                    if data.get("type") == "transcript.partial":
                        partials += 1
                    elif data.get("type") == "transcript.final":
                        finals += 1
                    elif data.get("type") == "error":
                        errors += 1
                        logger.warning(f"Client {client_id} received error: {data}")

                except asyncio.TimeoutError:
                    pass

                await asyncio.sleep(0.03)

            await ws.send(json.dumps({"type": "flush"}))
            logger.debug(f"Client {client_id} sent flush message")

    except Exception as exc:
        logger.error(f"Client {client_id} failed: {exc}")
        return {
            "client_id": client_id,
            "ok": False,
            "error": str(exc),
            "events": events,
            "partials": partials,
            "finals": finals,
            "structured_errors": errors,
        }

    logger.info(
        f"Client {client_id} completed: events={events}, partials={partials}, "
        f"finals={finals}, errors={errors}"
    )

    return {
        "client_id": client_id,
        "ok": True,
        "events": events,
        "partials": partials,
        "finals": finals,
        "structured_errors": errors,
    }


async def main() -> None:
    """
    Main entry point for the WebSocket load test.
    
    Parses command-line arguments, spawns concurrent clients, runs the load
    test for the specified duration, and prints aggregated results.
    
    Returns:
        None
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(
        description="Load test the STT WebSocket endpoint with multiple concurrent clients."
    )
    parser.add_argument("--url", required=True, help="WebSocket URL to connect to")
    parser.add_argument("--clients", type=int, default=3, help="Number of concurrent clients")
    parser.add_argument("--seconds", type=int, default=10, help="Duration of the test in seconds")
    args = parser.parse_args()

    logger.info(
        f"Starting load test: {args.clients} clients for {args.seconds} seconds at {args.url}"
    )

    results = await asyncio.gather(
        *[
            run_client(
                client_id=i + 1,
                url=args.url,
                seconds=args.seconds,
            )
            for i in range(args.clients)
        ]
    )

    print(json.dumps(results, indent=2))

    ok_count = sum(1 for result in results if result["ok"])
    total_events = sum(result["events"] for result in results)
    total_partials = sum(result["partials"] for result in results)
    total_finals = sum(result["finals"] for result in results)
    total_errors = sum(result["structured_errors"] for result in results)

    logger.info(
        f"Load test completed: {ok_count}/{len(results)} clients ok, "
        f"total_events={total_events}, partials={total_partials}, "
        f"finals={total_finals}, errors={total_errors}"
    )
    print(f"ok_clients={ok_count}/{len(results)}")
    print(f"total_events={total_events}")
    print(f"total_partials={total_partials}")
    print(f"total_finals={total_finals}")
    print(f"total_errors={total_errors}")


if __name__ == "__main__":
    asyncio.run(main())
