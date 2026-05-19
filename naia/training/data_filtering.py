"""Data filtering and quality improvement for NAIA training."""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
from datasets import Dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def filter_by_length(
    examples: list[dict[str, str]],
    min_length: int = 10,
    max_length: int = 1000,
) -> list[dict[str, str]]:
    """Filter examples by text length."""
    filtered = []
    for example in examples:
        instruction = example.get("input", example.get("instruction", ""))
        output = example.get("output", "")
        total_length = len(instruction.split()) + len(output.split())
        
        if min_length <= total_length <= max_length:
            filtered.append(example)
    
    logger.info(f"Length filter: {len(examples)} -> {len(filtered)} examples")
    return filtered


def filter_by_quality(
    examples: list[dict[str, str]],
    min_output_length: int = 5,
    max_output_length: int = 500,
) -> list[dict[str, str]]:
    """Filter examples by output quality."""
    filtered = []
    for example in examples:
        output = example.get("output", "")
        output_length = len(output.split())
        
        if min_output_length <= output_length <= max_output_length:
            filtered.append(example)
    
    logger.info(f"Quality filter: {len(examples)} -> {len(filtered)} examples")
    return filtered


def filter_by_diversity(
    examples: list[dict[str, str]],
    similarity_threshold: float = 0.9,
) -> list[dict[str, str]]:
    """Filter out near-duplicate examples based on instruction similarity."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity
    
    instructions = [ex.get("input", ex.get("instruction", "")) for ex in examples]
    
    if len(instructions) < 2:
        return examples
    
    # Calculate similarity matrix
    vectorizer = TfidfVectorizer()
    tfidf_matrix = vectorizer.fit_transform(instructions)
    similarity_matrix = cosine_similarity(tfidf_matrix)
    
    # Filter duplicates
    to_keep = []
    seen = set()
    
    for i in range(len(examples)):
        if i in seen:
            continue
        
        to_keep.append(i)
        
        # Mark similar examples as duplicates
        for j in range(i + 1, len(examples)):
            if similarity_matrix[i, j] > similarity_threshold:
                seen.add(j)
    
    filtered = [examples[i] for i in to_keep]
    logger.info(f"Diversity filter: {len(examples)} -> {len(filtered)} examples")
    return filtered


def filter_by_special_characters(
    examples: list[dict[str, str]],
    max_special_char_ratio: float = 0.3,
) -> list[dict[str, str]]:
    """Filter examples with too many special characters."""
    filtered = []
    
    for example in examples:
        instruction = example.get("input", example.get("instruction", ""))
        output = example.get("output", "")
        text = instruction + " " + output
        
        # Calculate special character ratio
        special_chars = len(re.findall(r'[^a-zA-Z0-9\s\.,!?]', text))
        total_chars = len(text)
        ratio = special_chars / total_chars if total_chars > 0 else 0
        
        if ratio <= max_special_char_ratio:
            filtered.append(example)
    
    logger.info(f"Special character filter: {len(examples)} -> {len(filtered)} examples")
    return filtered


def filter_by_language(
    examples: list[dict[str, str]],
    min_english_ratio: float = 0.8,
) -> list[dict[str, str]]:
    """Filter examples to ensure they are primarily in English."""
    filtered = []
    
    for example in examples:
        instruction = example.get("input", example.get("instruction", ""))
        output = example.get("output", "")
        text = instruction + " " + output
        
        # Calculate English character ratio
        english_chars = len(re.findall(r'[a-zA-Z]', text))
        total_chars = len(re.findall(r'[a-zA-Z]', text)) + len(re.findall(r'[^a-zA-Z\s]', text))
        ratio = english_chars / total_chars if total_chars > 0 else 1.0
        
        if ratio >= min_english_ratio:
            filtered.append(example)
    
    logger.info(f"Language filter: {len(examples)} -> {len(filtered)} examples")
    return filtered


def apply_all_filters(
    dataset_path: str,
    output_path: str,
    filters: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply all data filters to dataset."""
    if filters is None:
        filters = {
            "min_length": 10,
            "max_length": 1000,
            "min_output_length": 5,
            "max_output_length": 500,
            "similarity_threshold": 0.9,
            "max_special_char_ratio": 0.3,
            "min_english_ratio": 0.8,
        }
    
    logger.info(f"Loading dataset from {dataset_path}")
    with open(dataset_path, encoding="utf-8") as f:
        examples = json.load(f)
    
    logger.info(f"Starting with {len(examples)} examples")
    
    # Apply filters
    examples = filter_by_length(
        examples,
        min_length=filters["min_length"],
        max_length=filters["max_length"],
    )
    
    examples = filter_by_quality(
        examples,
        min_output_length=filters["min_output_length"],
        max_output_length=filters["max_output_length"],
    )
    
    examples = filter_by_diversity(
        examples,
        similarity_threshold=filters["similarity_threshold"],
    )
    
    examples = filter_by_special_characters(
        examples,
        max_special_char_ratio=filters["max_special_char_ratio"],
    )
    
    examples = filter_by_language(
        examples,
        min_english_ratio=filters["min_english_ratio"],
    )
    
    # Save filtered dataset
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(examples, f, indent=2)
    
    logger.info(f"Filtered dataset saved to {output_path}")
    
    return {
        "original_count": len(examples),
        "filtered_count": len(examples),
        "retention_rate": len(examples) / len(examples),
        "filters_applied": filters,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    result = apply_all_filters(
        dataset_path="dataset/output/train_set.json",
        output_path="dataset/output/train_set_filtered.json",
    )
    
    print("\n=== Data Filtering Complete ===")
    print(json.dumps(result, indent=2))
