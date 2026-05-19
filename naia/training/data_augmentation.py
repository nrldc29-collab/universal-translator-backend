"""Data augmentation techniques for faster and better training."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

import numpy as np
from datasets import Dataset

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TextAugmentation:
    """Text augmentation techniques for training data."""
    
    def __init__(self, seed: int = 42):
        self.seed = seed
        random.seed(seed)
        np.random.seed(seed)
    
    def synonym_replacement(self, text: str, n: int = 1) -> str:
        """Replace words with synonyms."""
        words = text.split()
        new_words = words.copy()
        
        # Simplified synonym replacement
        # In production, use WordNet or similar
        for _ in range(n):
            if len(new_words) > 0:
                idx = random.randint(0, len(new_words) - 1)
                # Placeholder for actual synonym lookup
                pass
        
        return " ".join(new_words)
    
    def random_insertion(self, text: str, n: int = 1) -> str:
        """Randomly insert words."""
        words = text.split()
        
        for _ in range(n):
            if len(words) > 0:
                idx = random.randint(0, len(words))
                # Placeholder for random word insertion
                pass
        
        return " ".join(words)
    
    def random_swap(self, text: str, n: int = 1) -> str:
        """Randomly swap words."""
        words = text.split()
        
        for _ in range(n):
            if len(words) > 1:
                idx1, idx2 = random.sample(range(len(words)), 2)
                words[idx1], words[idx2] = words[idx2], words[idx1]
        
        return " ".join(words)
    
    def random_deletion(self, text: str, p: float = 0.1) -> str:
        """Randomly delete words."""
        words = text.split()
        new_words = [word for word in words if random.random() > p]
        
        if len(new_words) == 0:
            return text
        
        return " ".join(new_words)
    
    def back_translation(self, text: str) -> str:
        """Back translation augmentation."""
        # Placeholder for back translation
        # Would require translation API
        return text
    
    def apply_augmentation(
        self,
        text: str,
        augmentation_type: str = "synonym_replacement",
        **kwargs,
    ) -> str:
        """Apply specific augmentation."""
        if augmentation_type == "synonym_replacement":
            return self.synonym_replacement(text, **kwargs)
        elif augmentation_type == "random_insertion":
            return self.random_insertion(text, **kwargs)
        elif augmentation_type == "random_swap":
            return self.random_swap(text, **kwargs)
        elif augmentation_type == "random_deletion":
            return self.random_deletion(text, **kwargs)
        elif augmentation_type == "back_translation":
            return self.back_translation(text)
        else:
            return text


class InstructionAugmentation:
    """Instruction-specific augmentation techniques."""
    
    def __init__(self):
        self.augmenter = TextAugmentation()
    
    def augment_instruction(self, instruction: str) -> str:
        """Augment instruction while preserving meaning."""
        # Try different augmentation strategies
        strategies = ["synonym_replacement", "random_swap", "random_deletion"]
        strategy = random.choice(strategies)
        
        augmented = self.augmenter.apply_augmentation(
            instruction,
            augmentation_type=strategy,
        )
        
        return augmented
    
    def augment_output(self, output: str) -> str:
        """Augment output while preserving correctness."""
        # Be more conservative with output augmentation
        augmented = self.augmenter.apply_augmentation(
            output,
            augmentation_type="synonym_replacement",
            n=1,
        )
        
        return augmented


class DatasetAugmentation:
    """Dataset-level augmentation."""
    
    def __init__(self, augmentation_factor: int = 2):
        self.augmentation_factor = augmentation_factor
        self.instruction_augmenter = InstructionAugmentation()
    
    def augment_dataset(
        self,
        examples: list[dict[str, str]],
    ) -> list[dict[str, str]]:
        """Augment entire dataset."""
        logger.info(f"Augmenting dataset with factor {self.augmentation_factor}")
        
        augmented_examples = examples.copy()
        
        for example in examples:
            for _ in range(self.augmentation_factor - 1):
                augmented_example = {
                    "instruction": self.instruction_augmenter.augment_instruction(
                        example.get("input", example.get("instruction", ""))
                    ),
                    "output": example.get("output", ""),  # Keep output unchanged for correctness
                }
                augmented_examples.append(augmented_example)
        
        logger.info(f"Dataset augmented: {len(examples)} -> {len(augmented_examples)} examples")
        
        return augmented_examples


class MixupAugmentation:
    """Mixup augmentation for training."""
    
    def __init__(self, alpha: float = 0.2):
        self.alpha = alpha
    
    def mixup_examples(
        self,
        example1: dict[str, str],
        example2: dict[str, str],
    ) -> dict[str, str]:
        """Mix two examples."""
        lam = np.random.beta(self.alpha, self.alpha)
        
        # Simple text mixing (would require more sophisticated approach)
        instruction1 = example1.get("input", example1.get("instruction", ""))
        instruction2 = example2.get("input", example2.get("instruction", ""))
        
        # Split and mix
        words1 = instruction1.split()
        words2 = instruction2.split()
        
        # Mix at token level
        mixed_words = []
        for i in range(max(len(words1), len(words2))):
            if i < len(words1) and i < len(words2):
                mixed_words.append(words1[i] if random.random() < lam else words2[i])
            elif i < len(words1):
                mixed_words.append(words1[i])
            else:
                mixed_words.append(words2[i])
        
        mixed_example = {
            "instruction": " ".join(mixed_words),
            "output": example1.get("output", ""),  # Keep first output
        }
        
        return mixed_example


class CutMixAugmentation:
    """CutMix augmentation for training."""
    
    def __init__(self, beta: float = 1.0):
        self.beta = beta
    
    def cutmix_examples(
        self,
        example1: dict[str, str],
        example2: dict[str, str],
    ) -> dict[str, str]:
        """CutMix two examples."""
        lam = np.random.beta(self.beta, self.beta)
        
        instruction1 = example1.get("input", example1.get("instruction", ""))
        instruction2 = example2.get("input", example2.get("instruction", ""))
        
        words1 = instruction1.split()
        words2 = instruction2.split()
        
        # Cut and paste segments
        cut_point = int(len(words1) * lam)
        mixed_words = words1[:cut_point] + words2[cut_point:]
        
        mixed_example = {
            "instruction": " ".join(mixed_words),
            "output": example1.get("output", ""),
        }
        
        return mixed_example


class AdaptiveAugmentation:
    """Adaptive augmentation based on example difficulty."""
    
    def __init__(self):
        self.augmenter = TextAugmentation()
    
    def calculate_difficulty(self, example: dict[str, str]) -> float:
        """Calculate example difficulty."""
        instruction = example.get("input", example.get("instruction", ""))
        output = example.get("output", "")
        
        # Simple difficulty metric
        difficulty = len(instruction.split()) + len(output.split())
        
        return min(difficulty / 1000, 1.0)
    
    def adaptive_augment(
        self,
        example: dict[str, str],
        max_augmentations: int = 3,
    ) -> list[dict[str, str]]:
        """Adaptively augment based on difficulty."""
        difficulty = self.calculate_difficulty(example)
        
        # More augmentations for difficult examples
        num_augmentations = int(difficulty * max_augmentations)
        
        augmented_examples = [example]
        
        for _ in range(num_augmentations):
            augmented_example = {
                "instruction": self.augmenter.apply_augmentation(
                    example.get("input", example.get("instruction", "")),
                    augmentation_type="synonym_replacement",
                ),
                "output": example.get("output", ""),
            }
            augmented_examples.append(augmented_example)
        
        return augmented_examples


def apply_data_augmentation(
    dataset_path: str,
    output_path: str,
    augmentation_factor: int = 2,
    augmentation_type: str = "standard",
) -> dict[str, Any]:
    """Apply data augmentation to dataset."""
    logger.info(f"Applying {augmentation_type} augmentation to {dataset_path}")
    
    with open(dataset_path, encoding="utf-8") as f:
        examples = json.load(f)
    
    if augmentation_type == "standard":
        augmenter = DatasetAugmentation(augmentation_factor=augmentation_factor)
        augmented_examples = augmenter.augment_dataset(examples)
    elif augmentation_type == "adaptive":
        augmenter = AdaptiveAugmentation()
        augmented_examples = []
        for example in examples:
            augmented_examples.extend(augmenter.adaptive_augment(example))
    else:
        augmented_examples = examples
    
    # Save augmented dataset
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(augmented_examples, f, indent=2)
    
    logger.info(f"Augmented dataset saved to {output_path}")
    
    return {
        "original_count": len(examples),
        "augmented_count": len(augmented_examples),
        "augmentation_factor": len(augmented_examples) / len(examples),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Apply data augmentation
    result = apply_data_augmentation(
        dataset_path="dataset/output/train_set.json",
        output_path="dataset/output/train_set_augmented.json",
        augmentation_factor=2,
        augmentation_type="standard",
    )
    
    print("\n=== Data Augmentation Complete ===")
    print(json.dumps(result, indent=2))
