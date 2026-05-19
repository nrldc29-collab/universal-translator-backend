"""Multi-GPU training script for NAIA student model."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import torch
import torch.distributed as dist
import torch.multiprocessing as mp
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
from datasets import Dataset
from training.optimized_gpu_config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def setup_distributed(rank: int, world_size: int) -> None:
    """Setup distributed training."""
    os.environ["MASTER_ADDR"] = "localhost"
    os.environ["MASTER_PORT"] = "12355"
    dist.init_process_group("nccl", rank=rank, world_size=world_size)
    torch.cuda.set_device(rank)


def cleanup_distributed() -> None:
    """Cleanup distributed training."""
    dist.destroy_process_group()


def train_worker(rank: int, world_size: int, config: dict[str, Any], dataset_path: str, output_dir: str) -> None:
    """Training worker for distributed training."""
    setup_distributed(rank, world_size)
    
    logger.info(f"Worker {rank} starting")
    
    # Load dataset (only on rank 0 to avoid duplicate loading)
    if rank == 0:
        with open(dataset_path, encoding="utf-8") as f:
            train_data = json.load(f)
        train_examples = [{"instruction": ex.get("input", ex.get("instruction", "")), 
                          "output": ex.get("output", "")} for ex in train_data]
        logger.info(f"Loaded {len(train_examples)} training examples")
    else:
        train_examples = None
    
    # Broadcast dataset to all workers
    if dist.is_initialized():
        train_examples = [train_examples]
        dist.broadcast_object_list(train_examples, src=0)
        train_examples = train_examples[0]
    
    # Load model and tokenizer
    if rank == 0:
        logger.info(f"Loading model: {config['model_name']}")
    
    tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    model = AutoModelForCausalLM.from_pretrained(
        config["model_name"],
        device_map={"": rank},
        torch_dtype=torch.float16 if config.get("fp16", False) else torch.bfloat16,
    )
    
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
    if rank == 0:
        model.print_trainable_parameters()
    
    # Load and tokenize dataset
    train_dataset = Dataset.from_list(train_examples)
    
    def tokenize_function(examples):
        return tokenizer(
            examples["instruction"],
            examples["output"],
            truncation=True,
            max_length=config["max_seq_length"],
            padding="max_length",
        )
    
    tokenized_dataset = train_dataset.map(tokenize_function, batched=True)
    
    # Training arguments with distributed settings
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=config["num_train_epochs"],
        per_device_train_batch_size=config["batch_size"] // world_size,
        gradient_accumulation_steps=config["gradient_accumulation_steps"],
        learning_rate=config["learning_rate"],
        warmup_steps=config["warmup_steps"],
        logging_steps=config["logging_steps"],
        save_steps=config["save_steps"],
        fp16=config.get("fp16", False),
        bf16=config.get("bf16", False),
        gradient_checkpointing=config.get("gradient_checkpointing", False),
        optim=config.get("optim", "adamw_torch"),
        max_grad_norm=config.get("max_grad_norm", 1.0),
        save_total_limit=3,
        dataloader_num_workers=config.get("dataloader_num_workers", 2),
        dataloader_pin_memory=True,
        dataloader_prefetch_factor=2,
        report_to=[],
        lr_scheduler_type="cosine",
        weight_decay=0.01,
        ddp_find_unused_parameters=False,
        local_rank=rank,
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
    )
    
    # Train
    if rank == 0:
        logger.info("Starting distributed training...")
    
    trainer.train()
    
    # Save model (only on rank 0)
    if rank == 0:
        logger.info(f"Saving model to {output_dir}")
        trainer.save_model(output_dir)
        tokenizer.save_pretrained(output_dir)
        
        config_path = Path(output_dir) / "training_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
    
    cleanup_distributed()
    logger.info(f"Worker {rank} finished")


def run_multi_gpu_training(
    dataset_path: str,
    output_dir: str,
    config_profile: str = "optimized",
    num_gpus: int | None = None,
) -> dict[str, Any]:
    """Run multi-GPU training."""
    config = get_config(config_profile)
    
    # Detect number of GPUs
    if num_gpus is None:
        num_gpus = torch.cuda.device_count()
    
    if num_gpus < 2:
        logger.warning(f"Multi-GPU training requires at least 2 GPUs, found {num_gpus}")
        return {"status": "error", "message": "Not enough GPUs"}
    
    logger.info(f"Starting multi-GPU training with {num_gpus} GPUs")
    
    # Launch distributed training
    mp.spawn(
        train_worker,
        args=(num_gpus, config, dataset_path, output_dir),
        nprocs=num_gpus,
        join=True,
    )
    
    return {
        "status": "success",
        "output_dir": output_dir,
        "num_gpus": num_gpus,
        "training_config": config,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    result = run_multi_gpu_training(
        dataset_path="dataset/output/train_set.json",
        output_dir="models/naia-multi-gpu-student",
        config_profile="deepspeed",
    )
    
    print("\n=== Multi-GPU Training Complete ===")
    print(json.dumps(result, indent=2))
