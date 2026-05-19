"""
Example script for streaming PCM16 audio from a WAV file.

This script demonstrates how to use the True Streaming STT SDK to transcribe
a WAV file by reading it in chunks and streaming the PCM16 audio data via
WebSocket. The file must be 16 kHz mono 16-bit PCM format.

Usage:
    python stream_pcm_file.py audio.wav --api-key YOUR_KEY

Example:
    python stream_pcm_file.py test.wav --api-key sk-12345 --language en
"""
import argparse
import asyncio
import logging
import wave
from pathlib import Path

from true_streaming_stt import StreamingSTTClient

logger = logging.getLogger(__name__)


async def pcm16_chunks_from_wav(path: str, chunk_ms: int = 30):
    """
    Generator that yields PCM16 audio chunks from a WAV file.
    
    Reads a WAV file in chunks and yields the raw PCM16 audio data. The file
    must be 16 kHz mono 16-bit PCM format. Includes a sleep to simulate
    real-time streaming at the appropriate rate.
    
    Args:
        path: Path to the WAV file
        chunk_ms: Duration of each chunk in milliseconds (default: 30)
        
    Yields:
        Raw PCM16 audio data as bytes
        
    Raises:
        ValueError: If the WAV file is not mono, 16 kHz, or 16-bit PCM
        FileNotFoundError: If the WAV file does not exist
    """
    wav_path = Path(path)

    logger.info(f"Opening WAV file: {wav_path}")

    with wave.open(str(wav_path), "rb") as wav_file:
        channels = wav_file.getnchannels()
        sample_rate = wav_file.getframerate()
        sample_width = wav_file.getsampwidth()

        logger.debug(
            f"WAV properties: channels={channels}, sample_rate={sample_rate}, "
            f"sample_width={sample_width}"
        )

        if channels != 1:
            logger.error(f"WAV must be mono, got {channels} channels")
            raise ValueError("WAV must be mono.")
        if sample_rate != 16000:
            logger.error(f"WAV must be 16000 Hz, got {sample_rate} Hz")
            raise ValueError("WAV must be 16000 Hz.")
        if sample_width != 2:
            logger.error(f"WAV must be 16-bit PCM, got {sample_width * 8}-bit")
            raise ValueError("WAV must be 16-bit PCM.")

        frames_per_chunk = int(sample_rate * chunk_ms / 1000)
        logger.debug(f"Frames per chunk: {frames_per_chunk}")

        chunk_count = 0
        while True:
            chunk = wav_file.readframes(frames_per_chunk)

            if not chunk:
                logger.info(f"Reached end of file after {chunk_count} chunks")
                break

            chunk_count += 1
            logger.debug(f"Yielding chunk {chunk_count} with {len(chunk)} bytes")
            yield chunk
            await asyncio.sleep(chunk_ms / 1000)


async def main() -> None:
    """
    Main entry point for the streaming PCM16 example.
    
    Parses command-line arguments, creates a streaming client, and processes
    the WAV file by streaming audio chunks and printing transcription results.
    
    Returns:
        None
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(
        description="Stream a WAV file for transcription using the True Streaming STT SDK."
    )
    parser.add_argument("wav_path", help="Path to the WAV file (must be 16 kHz mono 16-bit PCM)")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument("--url", default="ws://localhost:8000/stt/stream", help="WebSocket URL")
    parser.add_argument("--language", default="en", help="Language code for transcription")
    args = parser.parse_args()

    logger.info(f"Starting transcription for: {args.wav_path}")
    logger.info(f"WebSocket URL: {args.url}, Language: {args.language}")

    client = StreamingSTTClient(
        api_key=args.api_key,
        websocket_url=args.url,
        language=args.language,
    )

    try:
        async for event in client.stream_pcm16(pcm16_chunks_from_wav(args.wav_path)):
            if event.type == "transcript.partial":
                print(f"PARTIAL: {event.data['text']}")
            elif event.type == "transcript.final":
                print(f"FINAL: {event.data['text']}")
            elif event.type == "error":
                print(f"ERROR: {event.data}")
                logger.error(f"Transcription error: {event.data}")
            else:
                print(f"{event.type}: {event.data}")
                logger.debug(f"Event: {event.type}, Data: {event.data}")
    except Exception as e:
        logger.error(f"Streaming failed: {e}")
        print(f"Error: {e}")
    else:
        logger.info("Transcription completed successfully")


if __name__ == "__main__":
    asyncio.run(main())
