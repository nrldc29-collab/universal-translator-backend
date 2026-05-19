"""GPU training configuration for cloud GPU rental services."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

# GPU training configuration
GPU_TRAINING_CONFIG = {
    "service": "runpod",
    "gpu_type": "NVIDIA A100-SXM4-80GB",  # Recommended for training
    "gpu_count": 1,
    "disk_size": 100,  # GB
    "min_vram": 40,  # GB minimum
    "container_image": "pytorch/pytorch:2.1.0-cuda12.1-cudnn8-runtime",
    "env_vars": {
        "PYTHONPATH": "/workspace",
        "HF_HOME": "/workspace/.cache/huggingface",
        "TRANSFORMERS_CACHE": "/workspace/.cache/huggingface",
    },
    "ports": {
        "8888": "jupyter",
        "22": "ssh",
    },
    "volume_mounts": {
        "/workspace": "rw",
    },
    "docker_args": [
        "--shm-size=16g",
        "--ipc=host",
    ],
}

# Training hyperparameters for GPU
GPU_TRAINING_HYPERPARAMETERS = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 2048,
    "batch_size": 4,
    "gradient_accumulation_steps": 4,
    "learning_rate": 2e-4,
    "num_train_epochs": 3,
    "warmup_steps": 100,
    "logging_steps": 10,
    "save_steps": 500,
    "eval_steps": 500,
    "lora_r": 8,
    "lora_alpha": 16,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
}

# Dataset configuration
GPU_DATASET_CONFIG = {
    "train_path": "dataset/output/train_set.json",
    "test_path": "dataset/output/test_set.json",
    "output_dir": "models/naia-gpu-student",
    "cache_dir": "/workspace/.cache",
}


def get_gpu_config() -> dict[str, Any]:
    """Get GPU training configuration."""
    return GPU_TRAINING_CONFIG


def get_training_hyperparameters() -> dict[str, Any]:
    """Get training hyperparameters."""
    return GPU_TRAINING_HYPERPARAMETERS


def get_dataset_config() -> dict[str, Any]:
    """Get dataset configuration."""
    return GPU_DATASET_CONFIG


def setup_runpod_environment() -> None:
    """Setup environment variables for Runpod."""
    config = get_gpu_config()
    for key, value in config["env_vars"].items():
        os.environ[key] = value


if __name__ == "__main__":
    import json

    print("GPU Training Configuration:")
    print(json.dumps(get_gpu_config(), indent=2))
    print("\nTraining Hyperparameters:")
    print(json.dumps(get_training_hyperparameters(), indent=2))
    print("\nDataset Configuration:")
    print(json.dumps(get_dataset_config(), indent=2))
