"""GPU training script for Kaggle free GPU instances."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from training.optimized_gpu_config import get_config

logger = logging.getLogger(__name__)


# Kaggle-specific GPU training configuration (using optimized profile by default)
KAGGLE_GPU_CONFIG = get_config("optimized")
KAGGLE_GPU_CONFIG["gpu_type"] = "NVIDIA T4"
KAGGLE_GPU_CONFIG["output_dir"] = "/kaggle/working/naia-gpu-student"
KAGGLE_GPU_CONFIG["dataset_path"] = "/kaggle/input/naia-dataset/train_set.json"


def setup_kaggle_environment() -> None:
    """Setup Kaggle environment variables."""
    os.environ["WANDB_DISABLED"] = "true"  # Disable wandb for Kaggle
    os.environ["TRANSFORMERS_CACHE"] = "/kaggle/working/.cache"
    os.environ["HF_HOME"] = "/kaggle/working/.cache"
    logger.info("Kaggle environment setup complete")


def prepare_dataset_for_kaggle(dataset_path: str) -> list[dict[str, str]]:
    """Prepare dataset for Kaggle GPU training."""
    dataset_path = Path(dataset_path)
    
    if not dataset_path.exists():
        logger.warning(f"Dataset not found at {dataset_path}, using sample data")
        return []
    
    with open(dataset_path, encoding="utf-8") as file:
        examples = json.load(file)
    
    # Convert to format suitable for GPU training
    gpu_examples = []
    for example in examples:
        gpu_examples.append({
            "instruction": example.get("input", example.get("instruction", "")),
            "output": example.get("output", ""),
        })
    
    logger.info(f"Prepared {len(gpu_examples)} examples for Kaggle GPU training")
    return gpu_examples


def run_kaggle_gpu_training(
    dataset_path: str = "/kaggle/input/naia-dataset/train_set.json",
    output_dir: str = "/kaggle/working/naia-gpu-student",
    config_profile: str = "optimized",
) -> dict[str, Any]:
    """Run GPU training on Kaggle."""
    config = get_config(config_profile)
    config["gpu_type"] = "NVIDIA T4"
    config["output_dir"] = output_dir
    config["dataset_path"] = dataset_path
    
    logger.info("Starting Kaggle GPU training...")
    logger.info(f"Training config: {json.dumps(config, indent=2)}")
    
    # Setup environment
    setup_kaggle_environment()
    
    # Check GPU availability
    try:
        import torch
        if not torch.cuda.is_available():
            logger.error("GPU not available on Kaggle")
            return {"status": "error", "message": "GPU not available"}
        
        logger.info(f"GPU available: {torch.cuda.get_device_name(0)}")
        logger.info(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")
    except ImportError:
        logger.error("PyTorch not installed")
        return {"status": "error", "message": "PyTorch not installed"}
    
    # Prepare dataset
    train_data = prepare_dataset_for_kaggle(dataset_path)
    if not train_data:
        logger.warning("No training data available")
        return {"status": "error", "message": "No training data"}
    
    # Import training libraries
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
        from peft import LoraConfig, get_peft_model
        from datasets import Dataset
    except ImportError as e:
        logger.error(f"Failed to import training libraries: {e}")
        return {"status": "error", "message": str(e)}
    
    # Load model and tokenizer
    logger.info(f"Loading model: {config['model_name']}")
    try:
        tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
        model = AutoModelForCausalLM.from_pretrained(
            config["model_name"],
            device_map="auto",
            load_in_8bit=True,
            torch_dtype=torch.float16,
            attn_implementation="flash_attention_2" if config.get("use_flash_attention", False) else None,
        )

        # Apply torch.compile if enabled
        if config.get("use_torch_compile", False):
            logger.info("Applying torch.compile for speedup")
            try:
                model = torch.compile(model)
            except Exception as e:
                logger.warning(f"torch.compile failed: {e}, continuing without compilation")
    except Exception as e:
        logger.error(f"Failed to load model: {e}")
        return {"status": "error", "message": str(e)}
    
    # Configure LoRA
    lora_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        target_modules=config["target_modules"],
        lora_dropout=config["lora_dropout"],
        bias=config["bias"],
        task_type=config["task_type"],
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Load dataset
    train_dataset = Dataset.from_list(train_data)

    # Tokenize dataset with caching
    cache_dir = config.get("cache_dir", None)
    def tokenize_function(examples):
        return tokenizer(
            examples["instruction"],
            examples["output"],
            truncation=True,
            max_length=config["max_seq_length"],
            padding="max_length",
        )

    tokenized_dataset = train_dataset.map(
        tokenize_function,
        batched=True,
        cache_file_name=f"{cache_dir}/tokenized_cache.arrow" if cache_dir else None,
    )
    
    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config["num_train_epochs"],
        per_device_train_batch_size=config["batch_size"],
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        learning_rate=config["learning_rate"],
        warmup_steps=config["warmup_steps"],
        logging_steps=config["logging_steps"],
        save_steps=config["save_steps"],
        eval_steps=config.get("eval_steps", config["save_steps"]),
        fp16=config["fp16"],
        bf16=config.get("bf16", False),
        gradient_checkpointing=config.get("gradient_checkpointing", False),
        optim=config.get("optim", "adamw_torch"),
        max_grad_norm=config.get("max_grad_norm", 1.0),
        save_total_limit=3,
        load_best_model_at_end=True,
        dataloader_num_workers=config.get("dataloader_num_workers", 2),
        dataloader_pin_memory=True,  # Pin memory for faster GPU transfer
        dataloader_prefetch_factor=2,  # Prefetch batches
        report_to=[],  # Disable reporting
        lr_scheduler_type="cosine",  # Cosine learning rate schedule
        weight_decay=0.01,  # Weight decay for regularization
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
    )
    
    # Train
    logger.info("Starting training...")
    try:
        trainer.train()
    except Exception as e:
        logger.error(f"Training failed: {e}")
        return {"status": "error", "message": str(e)}
    
    # Save model
    logger.info(f"Saving model to {output_dir}")
    try:
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)
        
        # Save training config
        config_path = Path(output_dir) / "training_config.json"
        with open(config_path, "w", encoding="utf-8") as file:
            json.dump(config, file, indent=2)
        
        logger.info("Model saved successfully")
    except Exception as e:
        logger.error(f"Failed to save model: {e}")
        return {"status": "error", "message": str(e)}
    
    return {
        "status": "success",
        "output_dir": output_dir,
        "model_path": str(Path(output_dir) / "adapter_model.bin"),
        "training_config": config,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    result = run_kaggle_gpu_training()
    
    print("\n=== Kaggle GPU Training Complete ===")
    print(json.dumps(result, indent=2))
