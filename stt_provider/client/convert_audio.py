"""
Audio conversion utility for converting to PCM16 WAV format.

This module provides a command-line utility for converting various audio file formats
to 16 kHz mono PCM WAV format suitable for speech-to-text transcription. It uses
FFmpeg for the conversion process.

Usage:
    python convert_audio.py input_file.mp3 output_file.wav
"""
import argparse
import logging
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def convert_to_pcm16_wav(input_path: str, output_path: str) -> None:
    """
    Convert an audio file to 16 kHz mono PCM WAV format.
    
    Uses FFmpeg to convert the input audio file to the required format for
    speech-to-text transcription: 16 kHz sample rate, mono channel, 16-bit PCM.
    
    Args:
        input_path: Path to the input audio file (any FFmpeg-supported format)
        output_path: Path where the output PCM WAV file will be saved
        
    Raises:
        FileNotFoundError: If the input file does not exist
        subprocess.CalledProcessError: If FFmpeg conversion fails
    """
    source = Path(input_path)
    target = Path(output_path)

    logger.info(f"Converting audio: {source} -> {target}")

    if not source.exists():
        logger.error(f"Input file not found: {input_path}")
        raise FileNotFoundError(f"Input file not found: {input_path}")

    target.parent.mkdir(parents=True, exist_ok=True)
    logger.debug(f"Created output directory: {target.parent}")

    command = [
        "ffmpeg",
        "-y",  # Overwrite output file if it exists
        "-i",
        str(source),
        "-ac",  # Set number of audio channels
        "1",  # Mono
        "-ar",  # Set audio sampling frequency
        "16000",  # 16 kHz
        "-sample_fmt",  # Set sample format
        "s16",  # 16-bit PCM
        str(target),
    ]

    logger.debug(f"Running FFmpeg command: {' '.join(command)}")

    try:
        subprocess.run(command, check=True, capture_output=True, text=True)
        logger.info(f"Successfully converted audio to: {target}")
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg conversion failed: {e.stderr}")
        raise


def main() -> int:
    """
    Main entry point for the audio conversion utility.
    
    Parses command-line arguments and performs the audio conversion.
    
    Returns:
        Exit code (0 for success, non-zero for failure)
    """
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    
    parser = argparse.ArgumentParser(
        description="Convert common audio files to 16 kHz mono PCM WAV."
    )
    parser.add_argument("input_path", help="Path to input audio file")
    parser.add_argument("output_path", help="Path to output PCM WAV file")
    args = parser.parse_args()

    try:
        convert_to_pcm16_wav(args.input_path, args.output_path)
        print(f"Converted: {args.output_path}")
        return 0
    except Exception as e:
        logger.error(f"Conversion failed: {e}")
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
