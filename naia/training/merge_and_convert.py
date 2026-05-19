"""Merge LoRA adapter with base model and convert to GGUF for local inference."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def merge_lora_to_base_model(
    lora_path: str,
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    output_path: str = "./naia-student-3b-merged",
) -> None:
    """
    Merge LoRA adapter with base model.

    Args:
        lora_path: Path to LoRA adapter weights
        base_model: Base model identifier
        output_path: Output path for merged model
    """
    from peft import PeftModel
    from unsloth import FastLanguageModel

    # Load the LoRA-trained model directly. Unsloth's
    # FastLanguageModel.from_pretrained handles both base-model paths and
    # adapter directories that contain an ``adapter_config.json``; passing
    # the LoRA path is the correct way to resume an adapter for merging.
    logger.info(f"Loading LoRA adapter: {lora_path}")
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=lora_path,
        max_seq_length=4096,
        dtype=None,
        load_in_4bit=True,
    )

    logger.info(f"Merging adapter into base weights -> {output_path}")
    model.save_pretrained_merged(
        output_path,
        tokenizer,
        save_method="merged_16bit",
    )

    logger.info(f"Merged model saved to: {output_path}")


def convert_to_gguf(
    model_path: str,
    output_dir: str = "./naia-student-3b-gguf",
    quantization: str = "q4_k_m",
) -> None:
    """
    Convert merged model to GGUF format for local inference.

    Args:
        model_path: Path to merged model
        output_dir: Output directory for GGUF files
        quantization: Quantization method (q4_k_m, q5_k_m, q8_0, etc.)
    """
    model_path = Path(model_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    logger.info(f"Converting {model_path} to GGUF with {quantization}")

    # Use llama.cpp's convert-hf-to-gguf.py
    # This requires llama.cpp to be installed
    cmd = [
        "python",
        "convert-hf-to-gguf.py",
        str(model_path),
        "--outfile",
        str(output_path / f"naia-student-3b-{quantization}.gguf"),
        "--quantize",
        quantization,
    ]

    try:
        subprocess.run(cmd, check=True)
        logger.info(f"GGUF model saved to: {output_path}")
    except FileNotFoundError:
        logger.error("convert-hf-to-gguf.py not found. Please install llama.cpp.")
        logger.info("Instructions: git clone https://github.com/ggerganov/llama.cpp && cd llama.cpp && make")
    except subprocess.CalledProcessError as exc:
        logger.error(f"Conversion failed: {exc}")


def convert_to_gguf_multiple(
    model_path: str,
    output_dir: str = "./naia-student-3b-gguf",
    quantizations: list[str] | None = None,
) -> None:
    """
    Convert model to multiple GGUF quantization levels.

    Args:
        model_path: Path to merged model
        output_dir: Output directory for GGUF files
        quantizations: List of quantization methods
    """
    if quantizations is None:
        quantizations = ["q4_k_m", "q5_k_m", "q8_0"]

    for quant in quantizations:
        logger.info(f"Converting to {quant}...")
        convert_to_gguf(model_path, output_dir, quant)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Merge LoRA
    merge_lora_to_base_model(
        lora_path="./naia-student-3b-lora",
        base_model="Qwen/Qwen2.5-3B-Instruct",
        output_path="./naia-student-3b-merged",
    )

    # Convert to GGUF
    convert_to_gguf_multiple(
        model_path="./naia-student-3b-merged",
        output_dir="./naia-student-3b-gguf",
        quantizations=["q4_k_m", "q5_k_m", "q8_0"],
    )
