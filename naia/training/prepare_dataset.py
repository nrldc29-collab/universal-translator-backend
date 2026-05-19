"""Prepare dataset for Unsloth training from generated JSONL files."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def prepare_unsloth_dataset(
    input_jsonl: str | Path,
    output_json: str | Path,
    format_type: str = "single_shot",
) -> None:
    """
    Convert generated JSONL dataset to Unsloth format.

    Args:
        input_jsonl: Path to input JSONL file
        output_json: Path to output JSON file for Unsloth
        format_type: "single_shot" or "pipeline_aware"
    """
    input_path = Path(input_jsonl)
    output_path = Path(output_json)

    if not input_path.exists():
        logger.error(f"Input file not found: {input_path}")
        return

    dataset = []
    with open(input_path) as f:
        for line in f:
            example = json.loads(line)
            
            if format_type == "single_shot":
                # Single-shot: input -> output
                # Unsloth expects format with "text" field
                instruction = example["input"]
                output = example["output"]
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
                dataset.append({"text": text})
            elif format_type == "pipeline_aware":
                # Pipeline-aware: input -> structured output
                instruction = example["input"]
                output = json.dumps(example["output"], ensure_ascii=False)
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
                dataset.append({"text": text})

    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)

    logger.info(f"Prepared {len(dataset)} examples for Unsloth training")
    logger.info(f"Output saved to: {output_path}")


def prepare_combined_dataset(
    single_shot_jsonl: str | Path,
    pipeline_aware_jsonl: str | Path,
    output_json: str | Path,
    ratio: float = 0.5,
) -> None:
    """
    Combine single-shot and pipeline-aware datasets.

    Args:
        single_shot_jsonl: Path to single-shot JSONL
        pipeline_aware_jsonl: Path to pipeline-aware JSONL
        output_json: Path to combined output JSON
        ratio: Ratio of single-shot to pipeline-aware (0.5 = equal mix)
    """
    single_shot_path = Path(single_shot_jsonl)
    pipeline_aware_path = Path(pipeline_aware_jsonl)
    output_path = Path(output_json)

    dataset = []

    # Load single-shot examples
    if single_shot_path.exists():
        with open(single_shot_path) as f:
            for line in f:
                example = json.loads(line)
                instruction = example["input"]
                output = example["output"]
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
                dataset.append({"text": text})

    # Load pipeline-aware examples
    if pipeline_aware_path.exists():
        with open(pipeline_aware_path) as f:
            for line in f:
                example = json.loads(line)
                instruction = example["input"]
                output = json.dumps(example["output"], ensure_ascii=False)
                text = f"### Instruction:\n{instruction}\n\n### Response:\n{output}"
                dataset.append({"text": text})

    with open(output_path, "w") as f:
        json.dump(dataset, f, indent=2)

    logger.info(f"Combined dataset: {len(dataset)} examples")
    logger.info(f"Output saved to: {output_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    # Prepare datasets
    output_dir = Path("dataset/output")
    
    if (output_dir / "single_shot.jsonl").exists():
        prepare_unsloth_dataset(
            output_dir / "single_shot.jsonl",
            output_dir / "single_shot_unsloth.json",
            format_type="single_shot",
        )
    
    if (output_dir / "pipeline_aware.jsonl").exists():
        prepare_unsloth_dataset(
            output_dir / "pipeline_aware.jsonl",
            output_dir / "pipeline_aware_unsloth.json",
            format_type="pipeline_aware",
        )
    
    # Combine
    if (output_dir / "single_shot_unsloth.json").exists() and (output_dir / "pipeline_aware_unsloth.json").exists():
        prepare_combined_dataset(
            output_dir / "single_shot.jsonl",
            output_dir / "pipeline_aware.jsonl",
            output_dir / "combined_unsloth.json",
        )
