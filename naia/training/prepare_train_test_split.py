from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def prepare_train_test_split(
    dataset_path: str = "dataset/output/combined_unsloth.json",
    output_dir: str = "dataset/output",
    test_ratio: float = 0.2,
) -> None:
    """
    Split dataset into training and held-out test sets.

    Args:
        dataset_path: Path to the combined dataset
        output_dir: Directory for output files
        test_ratio: Ratio of data to use for testing
    """
    dataset_path = Path(dataset_path)
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Load combined dataset
    with open(dataset_path, encoding="utf-8") as file:
        examples = json.load(file)

    logger.info(f"Loaded {len(examples)} examples from {dataset_path}")

    # Shuffle and split
    random.seed(42)
    random.shuffle(examples)

    split_index = int(len(examples) * (1 - test_ratio))
    train_examples = examples[:split_index]
    test_examples = examples[split_index:]

    logger.info(f"Training set: {len(train_examples)} examples")
    logger.info(f"Test set: {len(test_examples)} examples")

    # Save training set
    train_path = output_dir / "train_set.json"
    with open(train_path, "w", encoding="utf-8") as file:
        json.dump(train_examples, file, ensure_ascii=False, indent=2)
    logger.info(f"Saved training set to {train_path}")

    # Save test set
    test_path = output_dir / "test_set.json"
    with open(test_path, "w", encoding="utf-8") as file:
        json.dump(test_examples, file, ensure_ascii=False, indent=2)
    logger.info(f"Saved test set to {test_path}")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    prepare_train_test_split(
        dataset_path="dataset/output/combined_unsloth.json",
        output_dir="dataset/output",
        test_ratio=0.2,
    )

    print("\nTrain/test split complete!")
    print(f"Training set: dataset/output/train_set.json")
    print(f"Test set: dataset/output/test_set.json")
