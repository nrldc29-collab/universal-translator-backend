"""Curriculum learning implementation for NAIA training."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from datasets import Dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def calculate_example_difficulty(example: dict[str, str]) -> float:
    """Calculate difficulty score for a training example."""
    instruction = example.get("instruction", "")
    output = example.get("output", "")
    
    # Simple difficulty metrics
    instruction_length = len(instruction.split())
    output_length = len(output.split())
    total_length = instruction_length + output_length
    
    # Complexity based on length and structure
    complexity = 0.6 * (total_length / 1000) + 0.4 * (output_length / 500)
    
    return min(complexity, 1.0)  # Normalize to 0-1


def create_curriculum_dataset(
    dataset_path: str,
    num_stages: int = 3,
    output_dir: str = "dataset/curriculum",
) -> dict[str, Any]:
    """Create curriculum learning dataset with multiple difficulty stages."""
    logger.info(f"Loading dataset from {dataset_path}")
    
    with open(dataset_path, encoding="utf-8") as f:
        train_data = json.load(f)
    
    logger.info(f"Loaded {len(train_data)} examples")
    
    # Calculate difficulty for each example
    examples_with_difficulty = []
    for example in train_data:
        difficulty = calculate_example_difficulty(example)
        examples_with_difficulty.append({
            "example": example,
            "difficulty": difficulty,
        })
    
    # Sort by difficulty
    examples_with_difficulty.sort(key=lambda x: x["difficulty"])
    
    # Create curriculum stages
    stage_size = len(examples_with_difficulty) // num_stages
    curriculum_stages = []
    
    for i in range(num_stages):
        start_idx = i * stage_size
        end_idx = (i + 1) * stage_size if i < num_stages - 1 else len(examples_with_difficulty)
        
        stage_examples = examples_with_difficulty[start_idx:end_idx]
        stage_data = [item["example"] for item in stage_examples]
        
        stage_info = {
            "stage": i + 1,
            "num_examples": len(stage_data),
            "avg_difficulty": np.mean([item["difficulty"] for item in stage_examples]),
            "min_difficulty": min([item["difficulty"] for item in stage_examples]),
            "max_difficulty": max([item["difficulty"] for item in stage_examples]),
        }
        
        logger.info(f"Stage {i + 1}: {stage_info}")
        
        # Save stage dataset
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        stage_file = output_path / f"stage_{i + 1}.json"
        with open(stage_file, "w", encoding="utf-8") as f:
            json.dump(stage_data, f, indent=2)
        
        curriculum_stages.append({
            "stage": i + 1,
            "file": str(stage_file),
            "info": stage_info,
        })
    
    # Save curriculum metadata
    metadata = {
        "num_stages": num_stages,
        "total_examples": len(train_data),
        "stages": curriculum_stages,
    }
    
    metadata_file = output_path / "curriculum_metadata.json"
    with open(metadata_file, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)
    
    logger.info(f"Curriculum learning dataset created at {output_dir}")
    
    return metadata


def get_curriculum_stage(stage: int, output_dir: str = "dataset/curriculum") -> list[dict[str, str]]:
    """Get training examples for a specific curriculum stage."""
    stage_file = Path(output_dir) / f"stage_{stage}.json"
    
    if not stage_file.exists():
        raise FileNotFoundError(f"Stage {stage} not found at {stage_file}")
    
    with open(stage_file, encoding="utf-8") as f:
        stage_data = json.load(f)
    
    logger.info(f"Loaded {len(stage_data)} examples for stage {stage}")
    
    return stage_data


if __name__ == "__main__":
    metadata = create_curriculum_dataset(
        dataset_path="dataset/output/train_set.json",
        num_stages=3,
        output_dir="dataset/curriculum",
    )
    
    print("\n=== Curriculum Learning Dataset Created ===")
    print(json.dumps(metadata, indent=2))
