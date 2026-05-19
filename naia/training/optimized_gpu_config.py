"""Optimized GPU training configuration for faster training."""

from __future__ import annotations

import torch
from typing import Any

# Optimized training hyperparameters for speed
OPTIMIZED_TRAINING_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,  # Reduced from 2048 for faster tokenization
    "batch_size": 16,  # Increased from 8 for better GPU utilization
    "gradient_accumulation_steps": 1,  # Reduced from 2 since batch size increased
    "learning_rate": 3e-4,  # Slightly higher for faster convergence
    "num_train_epochs": 2,  # Reduced from 3 for faster training
    "warmup_steps": 50,  # Reduced from 100
    "logging_steps": 20,  # Reduced logging frequency
    "save_steps": 1000,  # Increased to save less frequently
    "fp16": True,
    "bf16": False,  # Use fp16 on T4, bf16 on newer GPUs
    "gradient_checkpointing": True,  # Enable gradient checkpointing for memory efficiency
    "optim": "adamw_torch",  # Use PyTorch native AdamW
    "lora_r": 4,  # Reduced from 8 for faster training
    "lora_alpha": 8,  # Reduced from 16
    "lora_dropout": 0.1,  # Slightly higher for regularization
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,  # Increased from 2 for faster data loading
    "max_grad_norm": 1.0,  # Gradient clipping for stability
    "use_flash_attention": True,  # Flash Attention for faster attention computation
    "use_torch_compile": True,  # PyTorch 2.0 compilation for speedup
    "cache_dir": "/kaggle/working/.cache",  # Cache tokenized dataset
}

# Ultra-fast configuration for quick iteration
ULTRA_FAST_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 512,  # Further reduced for speed
    "batch_size": 32,  # Maximum batch size
    "gradient_accumulation_steps": 1,
    "learning_rate": 5e-4,  # Higher learning rate
    "num_train_epochs": 1,  # Single epoch for quick testing
    "warmup_steps": 20,
    "logging_steps": 50,
    "save_steps": 500,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 2,  # Minimal LoRA rank
    "lora_alpha": 4,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_torch_compile": True,
    "cache_dir": "/kaggle/working/.cache",
}

# Balanced configuration for quality/speed tradeoff
BALANCED_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 12,
    "gradient_accumulation_steps": 1,
    "learning_rate": 2e-4,
    "num_train_epochs": 2,
    "warmup_steps": 75,
    "logging_steps": 15,
    "save_steps": 750,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 6,
    "lora_alpha": 12,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_torch_compile": True,
    "cache_dir": "/kaggle/working/.cache",
}

# DeepSpeed configuration for multi-GPU training
DEEPSPEED_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 32,
    "gradient_accumulation_steps": 1,
    "learning_rate": 2e-4,
    "num_train_epochs": 2,
    "warmup_steps": 100,
    "logging_steps": 20,
    "save_steps": 1000,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 4,
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_deepspeed": True,  # Enable DeepSpeed for memory optimization
    "deepspeed_stage": 2,  # ZeRO Stage 2 for memory efficiency
    "cache_dir": "/kaggle/working/.cache",
}

# Maximum speed configuration with smallest model
MAX_SPEED_CONFIG = {
    "model_name": "Qwen/Qwen2.5-0.5B-Instruct",  # Smallest model for maximum speed
    "max_seq_length": 512,
    "batch_size": 64,  # Maximum batch size
    "gradient_accumulation_steps": 1,
    "learning_rate": 5e-4,
    "num_train_epochs": 1,
    "warmup_steps": 10,
    "logging_steps": 100,
    "save_steps": 1000,
    "fp16": True,
    "gradient_checkpointing": False,  # Not needed for small model
    "optim": "adamw_torch",
    "lora_r": 2,  # Minimal LoRA
    "lora_alpha": 4,
    "lora_dropout": 0.05,
    "target_modules": ["q_proj", "k_proj"],  # Minimal target modules
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_torch_compile": True,
    "cache_dir": "/kaggle/working/.cache",
}

# Aggressive LoRA configuration
AGGRESSIVE_LORA_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 24,
    "gradient_accumulation_steps": 1,
    "learning_rate": 4e-4,
    "num_train_epochs": 1,
    "warmup_steps": 30,
    "logging_steps": 25,
    "save_steps": 500,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch_fused",  # Fused AdamW for speed
    "lora_r": 2,  # Very aggressive LoRA
    "lora_alpha": 4,
    "lora_dropout": 0.15,
    "target_modules": ["q_proj", "k_proj"],  # Fewer modules
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_torch_compile": True,
    "cache_dir": "/kaggle/working/.cache",
}

# FSDP configuration for multi-GPU training
FSDP_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 32,
    "gradient_accumulation_steps": 1,
    "learning_rate": 2e-4,
    "num_train_epochs": 2,
    "warmup_steps": 100,
    "logging_steps": 20,
    "save_steps": 1000,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 4,
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_fsdp": True,  # Enable Fully Sharded Data Parallel
    "fsdp_sharding_strategy": "FULL_SHARD",  # Full sharding for max memory efficiency
    "fsdp_offload_params": True,  # Offload params to CPU if needed
    "fsdp_min_num_params": 1e6,  # Minimum parameters for FSDP
    "fsdp_transformer_layer_cls_to_wrap": "Qwen2DecoderLayer",
    "cache_dir": "/kaggle/working/.cache",
}

# 4-bit quantization configuration for maximum speed
QUANTIZED_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 32,
    "gradient_accumulation_steps": 1,
    "learning_rate": 2e-4,
    "num_train_epochs": 2,
    "warmup_steps": 50,
    "logging_steps": 20,
    "save_steps": 1000,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 4,
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "load_in_4bit": True,  # 4-bit quantization
    "bnb_4bit_compute_dtype": torch.float16,
    "bnb_4bit_use_double_quant": True,
    "bnb_4bit_quant_type": "nf4",
    "cache_dir": "/kaggle/working/.cache",
}

# Progressive training configuration
PROGRESSIVE_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 512,  # Start small
    "target_seq_length": 1024,  # Gradually increase
    "batch_size": 24,
    "gradient_accumulation_steps": 1,
    "learning_rate": 3e-4,
    "num_train_epochs": 2,
    "warmup_steps": 50,
    "logging_steps": 20,
    "save_steps": 1000,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 4,
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_progressive_training": True,
    "progressive_steps": 500,  # Increase seq length every 500 steps
    "cache_dir": "/kaggle/working/.cache",
}

# Early stopping configuration
EARLY_STOPPING_CONFIG = {
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "max_seq_length": 1024,
    "batch_size": 16,
    "gradient_accumulation_steps": 1,
    "learning_rate": 3e-4,
    "num_train_epochs": 5,  # Max epochs, but will stop early
    "warmup_steps": 50,
    "logging_steps": 20,
    "save_steps": 500,
    "fp16": True,
    "gradient_checkpointing": True,
    "optim": "adamw_torch",
    "lora_r": 4,
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
    "use_flash_attention": True,
    "use_early_stopping": True,
    "early_stopping_patience": 3,  # Stop if no improvement for 3 evals
    "early_stopping_threshold": 0.001,  # Minimum improvement
    "cache_dir": "/kaggle/working/.cache",
}


def get_config(profile: str = "optimized") -> dict[str, Any]:
    """Get training configuration by profile."""
    configs = {
        "optimized": OPTIMIZED_TRAINING_CONFIG,
        "ultra_fast": ULTRA_FAST_CONFIG,
        "balanced": BALANCED_CONFIG,
        "deepspeed": DEEPSPEED_CONFIG,
        "max_speed": MAX_SPEED_CONFIG,
        "aggressive_lora": AGGRESSIVE_LORA_CONFIG,
        "fsdp": FSDP_CONFIG,
        "quantized": QUANTIZED_CONFIG,
        "progressive": PROGRESSIVE_CONFIG,
        "early_stopping": EARLY_STOPPING_CONFIG,
    }
    return configs.get(profile, OPTIMIZED_TRAINING_CONFIG)


if __name__ == "__main__":
    import json

    print("Optimized Training Config:")
    print(json.dumps(OPTIMIZED_TRAINING_CONFIG, indent=2))
    print("\nUltra Fast Config:")
    print(json.dumps(ULTRA_FAST_CONFIG, indent=2))
    print("\nBalanced Config:")
    print(json.dumps(BALANCED_CONFIG, indent=2))
