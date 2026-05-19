"""Advanced training pipeline with multiple optimization techniques."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
from datasets import Dataset
from training.optimized_gpu_config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedTrainingPipeline:
    """Advanced training pipeline with multiple optimizations."""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.model = None
        self.tokenizer = None
        self.trainer = None
    
    def setup_environment(self) -> None:
        """Setup training environment."""
        os.environ["WANDB_DISABLED"] = "true"
        os.environ["TRANSFORMERS_CACHE"] = self.config.get("cache_dir", "/tmp/.cache")
        os.environ["HF_HOME"] = self.config.get("cache_dir", "/tmp/.cache")
        
        # Enable TF32 on Ampere GPUs
        if torch.cuda.is_available():
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True
        
        logger.info("Environment setup complete")
    
    def load_model_and_tokenizer(self) -> None:
        """Load model and tokenizer with optimizations."""
        logger.info(f"Loading model: {self.config['model_name']}")
        
        self.tokenizer = AutoTokenizer.from_pretrained(self.config["model_name"])
        
        # Load model with quantization if configured
        if self.config.get("load_in_4bit", False):
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.float16,
                bnb_4bit_use_double_quant=self.config.get("bnb_4bit_use_double_quant", True),
                bnb_4bit_quant_type=self.config.get("bnb_4bit_quant_type", "nf4"),
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config["model_name"],
                quantization_config=quantization_config,
                device_map="auto",
            )
        elif self.config.get("load_in_8bit", False):
            from transformers import BitsAndBytesConfig
            quantization_config = BitsAndBytesConfig(
                load_in_8bit=True,
            )
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config["model_name"],
                quantization_config=quantization_config,
                device_map="auto",
                torch_dtype=torch.float16,
            )
        else:
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config["model_name"],
                device_map="auto",
                torch_dtype=torch.float16 if self.config.get("fp16", False) else torch.bfloat16,
            )
        
        # Apply Flash Attention if configured
        if self.config.get("use_flash_attention", False):
            self.model = AutoModelForCausalLM.from_pretrained(
                self.config["model_name"],
                attn_implementation="flash_attention_2",
                device_map=self.model.hf_device_map,
                torch_dtype=torch.float16 if self.config.get("fp16", False) else torch.bfloat16,
            )
        
        # Apply torch.compile if configured
        if self.config.get("use_torch_compile", False):
            try:
                self.model = torch.compile(self.model)
                logger.info("Applied torch.compile")
            except Exception as e:
                logger.warning(f"torch.compile failed: {e}")
        
        # Configure LoRA
        lora_config = LoraConfig(
            r=self.config["lora_r"],
            lora_alpha=self.config["lora_alpha"],
            target_modules=self.config["target_modules"],
            lora_dropout=self.config["lora_dropout"],
            bias=self.config["bias"],
            task_type=self.config["task_type"],
        )
        
        self.model = get_peft_model(self.model, lora_config)
        self.model.print_trainable_parameters()
        
        logger.info("Model and tokenizer loaded")
    
    def prepare_dataset(self, dataset_path: str) -> Dataset:
        """Prepare and optimize dataset for training."""
        logger.info(f"Loading dataset from {dataset_path}")
        
        with open(dataset_path, encoding="utf-8") as f:
            train_data = json.load(f)
        
        train_examples = [{"instruction": ex.get("input", ex.get("instruction", "")), 
                          "output": ex.get("output", "")} for ex in train_data]
        
        train_dataset = Dataset.from_list(train_examples)
        
        def tokenize_function(examples):
            return self.tokenizer(
                examples["instruction"],
                examples["output"],
                truncation=True,
                max_length=self.config["max_seq_length"],
                padding="max_length",
            )
        
        cache_dir = self.config.get("cache_dir", None)
        tokenized_dataset = train_dataset.map(
            tokenize_function,
            batched=True,
            cache_file_name=f"{cache_dir}/tokenized_cache.arrow" if cache_dir else None,
        )
        
        logger.info(f"Dataset prepared: {len(tokenized_dataset)} examples")
        
        return tokenized_dataset
    
    def setup_trainer(self, train_dataset: Dataset, output_dir: str) -> None:
        """Setup trainer with all optimizations."""
        training_args = TrainingArguments(
            output_dir=output_dir,
            num_train_epochs=self.config["num_train_epochs"],
            per_device_train_batch_size=self.config["batch_size"],
            gradient_accumulation_steps=self.config["gradient_accumulation_steps"],
            learning_rate=self.config["learning_rate"],
            warmup_steps=self.config["warmup_steps"],
            logging_steps=self.config["logging_steps"],
            save_steps=self.config["save_steps"],
            eval_steps=self.config.get("eval_steps", self.config["save_steps"]),
            fp16=self.config.get("fp16", False),
            bf16=self.config.get("bf16", False),
            gradient_checkpointing=self.config.get("gradient_checkpointing", False),
            optim=self.config.get("optim", "adamw_torch"),
            max_grad_norm=self.config.get("max_grad_norm", 1.0),
            save_total_limit=3,
            load_best_model_at_end=True,
            dataloader_num_workers=self.config.get("dataloader_num_workers", 2),
            dataloader_pin_memory=True,
            dataloader_prefetch_factor=self.config.get("dataloader_prefetch_factor", 2),
            report_to=[],
            lr_scheduler_type=self.config.get("lr_scheduler_type", "cosine"),
            weight_decay=self.config.get("weight_decay", 0.01),
        )
        
        self.trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=train_dataset,
        )
        
        logger.info("Trainer setup complete")
    
    def train(self) -> dict[str, Any]:
        """Run training with monitoring."""
        logger.info("Starting training...")
        
        # Monitor memory
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
        
        self.trainer.train()
        
        # Get memory stats
        memory_stats = {}
        if torch.cuda.is_available():
            memory_stats = {
                "peak_memory_gb": torch.cuda.max_memory_allocated() / 1024**3,
                "current_memory_gb": torch.cuda.memory_allocated() / 1024**3,
            }
        
        logger.info(f"Training complete. Memory stats: {memory_stats}")
        
        return memory_stats
    
    def save_model(self, output_dir: str) -> None:
        """Save trained model."""
        logger.info(f"Saving model to {output_dir}")
        
        self.trainer.save_model(output_dir)
        self.tokenizer.save_pretrained(output_dir)
        
        # Save training config
        config_path = Path(output_dir) / "training_config.json"
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(self.config, f, indent=2)
        
        logger.info("Model saved successfully")
    
    def run_full_pipeline(
        self,
        dataset_path: str,
        output_dir: str,
    ) -> dict[str, Any]:
        """Run the complete training pipeline."""
        logger.info("Starting advanced training pipeline")
        
        # Setup
        self.setup_environment()
        
        # Load model
        self.load_model_and_tokenizer()
        
        # Prepare dataset
        train_dataset = self.prepare_dataset(dataset_path)
        
        # Setup trainer
        self.setup_trainer(train_dataset, output_dir)
        
        # Train
        memory_stats = self.train()
        
        # Save model
        self.save_model(output_dir)
        
        return {
            "status": "success",
            "output_dir": output_dir,
            "memory_stats": memory_stats,
            "training_config": self.config,
        }


def run_advanced_training(
    dataset_path: str,
    output_dir: str,
    config_profile: str = "optimized",
) -> dict[str, Any]:
    """Run advanced training pipeline."""
    config = get_config(config_profile)
    
    pipeline = AdvancedTrainingPipeline(config)
    
    result = pipeline.run_full_pipeline(dataset_path, output_dir)
    
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    result = run_advanced_training(
        dataset_path="dataset/output/train_set.json",
        output_dir="models/naia-advanced-student",
        config_profile="optimized",
    )
    
    print("\n=== Advanced Training Complete ===")
    print(json.dumps(result, indent=2))
