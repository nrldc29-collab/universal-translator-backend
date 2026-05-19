"""
Batch transcription client for audio files.

This module provides a command-line utility for transcribing audio files using the
True Streaming STT API. It handles multipart form-data encoding, authentication,
and error handling for batch transcription requests.

Usage:
    python transcribe_file.py audio.wav --api-key YOUR_KEY --model base
"""
import argparse
import json
import logging
from pathlib import Path
from typing import Dict
from urllib import error, request

logger = logging.getLogger(__name__)


def transcribe_file(
    base_url: str,
    api_key: str,
    audio_path: str,
    model: str,
    language: str,
) -> Dict:
    """
    Transcribe an audio file using the True Streaming STT API.
    
    Sends a multipart form-data request to the transcriptions endpoint with
    the audio file, model ID, and language code. Handles authentication via
    Bearer token and returns the transcription result.
    
    Args:
        base_url: Base URL of the STT server (e.g., "http://localhost:8000")
        api_key: API key for authentication
        audio_path: Path to the audio file to transcribe
        model: Model ID to use for transcription (e.g., "base", "small")
        language: Language code for transcription (e.g., "en")
        
    Returns:
        Dictionary containing the transcription result with text and metadata
        
    Raises:
        FileNotFoundError: If the audio file does not exist
        RuntimeError: If the HTTP request fails with an error response
    """
    boundary = "----true-streaming-stt-boundary"
    audio_file = Path(audio_path)

    logger.info(f"Transcribing audio file: {audio_file}")
    logger.debug(f"Using model: {model}, language: {language}")

    if not audio_file.exists():
        logger.error(f"Audio file not found: {audio_path}")
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    file_bytes = audio_file.read_bytes()
    logger.debug(f"Read {len(file_bytes)} bytes from audio file")

    body = bytearray()

    def add_field(name: str, value: str) -> None:
        """Add a form field to the multipart body."""
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.extend(f"{value}\r\n".encode())

    def add_file(name: str, filename: str, content: bytes) -> None:
        """Add a file field to the multipart body."""
        body.extend(f"--{boundary}\r\n".encode())
        body.extend(
            f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode()
        )
        body.extend(b"Content-Type: application/octet-stream\r\n\r\n")
        body.extend(content)
        body.extend(b"\r\n")

    add_file("file", audio_file.name, file_bytes)
    add_field("model", model)
    add_field("language", language)
    body.extend(f"--{boundary}--\r\n".encode())

    logger.debug(f"Built multipart body with {len(body)} bytes")

    req = request.Request(
        url=f"{base_url.rstrip('/')}/v1/audio/transcriptions",
        data=bytes(body),
        method="POST",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
    )

    try:
        logger.info(f"Sending transcription request to {base_url}")
        with request.urlopen(req, timeout=300) as response:
            result = json.loads(response.read().decode("utf-8"))
            logger.info("Transcription completed successfully")
            return result
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8")
        logger.error(f"HTTP error {exc.code}: {detail}")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    except error.URLError as exc:
        logger.error(f"URL error: {exc.reason}")
        raise RuntimeError(f"Connection error: {exc.reason}") from exc
    except Exception as exc:
        logger.error(f"Unexpected error during transcription: {exc}")
        raise


def main() -> int:
    """
    Main entry point for the batch transcription utility.
    
    Parses command-line arguments and performs the audio file transcription.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(description="Batch transcribe an audio file.")
    parser.add_argument("audio_path", help="Path to the audio file to transcribe")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the STT server")
    parser.add_argument("--api-key", required=True, help="API key for authentication")
    parser.add_argument("--model", default="base", help="Model ID to use for transcription")
    parser.add_argument("--language", default="en", help="Language code for transcription")
    args = parser.parse_args()

    try:
        result = transcribe_file(
            base_url=args.base_url,
            api_key=args.api_key,
            audio_path=args.audio_path,
            model=args.model,
            language=args.language,
        )
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 0
    except Exception as e:
        logger.error(f"Transcription failed: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
