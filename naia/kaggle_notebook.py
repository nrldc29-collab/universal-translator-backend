# Kaggle GPU Training Notebook for NAIA Student Model
# Copy this entire file into a Kaggle notebook with GPU enabled

# Install dependencies
import subprocess
import sys
subprocess.check_call([sys.executable, "-m", "pip", "install", "-q", "transformers", "datasets", "accelerate", "peft", "bitsandbytes", "trl"])

import json
import logging
import os
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use optimized configuration for faster training
CONFIG = {
    "gpu_type": "NVIDIA T4",
    "batch_size": 16,  # Increased from 8 for better GPU utilization
    "gradient_accumulation_steps": 1,  # Reduced since batch size increased
    "max_seq_length": 1024,  # Reduced from 2048 for faster tokenization
    "learning_rate": 3e-4,  # Slightly higher for faster convergence
    "num_train_epochs": 2,  # Reduced from 3 for faster training
    "warmup_steps": 50,  # Reduced from 100
    "logging_steps": 20,
    "save_steps": 1000,  # Save less frequently
    "fp16": True,
    "gradient_checkpointing": True,  # Enable gradient checkpointing
    "optim": "adamw_torch",  # Use PyTorch native AdamW
    "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
    "lora_r": 4,  # Reduced from 8 for faster training
    "lora_alpha": 8,
    "lora_dropout": 0.1,
    "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
    "bias": "none",
    "task_type": "CAUSAL_LM",
    "output_dir": "/kaggle/working/naia-gpu-student",
    "dataloader_num_workers": 4,
    "max_grad_norm": 1.0,
}

# Setup environment
os.environ["WANDB_DISABLED"] = "true"
os.environ["TRANSFORMERS_CACHE"] = "/kaggle/working/.cache"
os.environ["HF_HOME"] = "/kaggle/working/.cache"

# Check GPU
import torch
print(f"GPU available: {torch.cuda.is_available()}")
if torch.cuda.is_available():
    print(f"GPU: {torch.cuda.get_device_name(0)}")
    print(f"GPU memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.2f} GB")

# Load dataset
dataset_path = "/kaggle/input/naia-dataset/train_set.json"
if Path(dataset_path).exists():
    with open(dataset_path, encoding="utf-8") as f:
        train_data = json.load(f)
    print(f"Loaded {len(train_data)} training examples")
else:
    print(f"Dataset not found at {dataset_path}")
    print("Please upload your dataset to Kaggle first")
    train_data = []

if train_data:
    # Prepare data
    train_examples = [{"instruction": ex.get("input", ex.get("instruction", "")), 
                      "output": ex.get("output", "")} for ex in train_data]
    
    # Load model
    from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
    from peft import LoraConfig, get_peft_model
    from datasets import Dataset
    
    print(f"Loading model: {CONFIG['model_name']}")
    tokenizer = AutoTokenizer.from_pretrained(CONFIG["model_name"])
    model = AutoModelForCausalLM.from_pretrained(
        CONFIG["model_name"],
        device_map="auto",
        load_in_8bit=True,
        torch_dtype=torch.float16,
    )
    
    # Configure LoRA
    lora_config = LoraConfig(
        r=CONFIG["lora_r"],
        lora_alpha=CONFIG["lora_alpha"],
        target_modules=CONFIG["target_modules"],
        lora_dropout=CONFIG["lora_dropout"],
        bias=CONFIG["bias"],
        task_type=CONFIG["task_type"],
    )
    
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()
    
    # Tokenize
    train_dataset = Dataset.from_list(train_examples)
    
    def tokenize_function(examples):
        return tokenizer(
            examples["instruction"],
            examples["output"],
            truncation=True,
            max_length=CONFIG["max_seq_length"],
            padding="max_length",
        )
    
    tokenized_dataset = train_dataset.map(tokenize_function, batched=True)
    
    # Training
    training_args = TrainingArguments(
        output_dir=CONFIG["output_dir"],
        num_train_epochs=CONFIG["num_train_epochs"],
        per_device_train_batch_size=CONFIG["batch_size"],
        gradient_accumulation_steps=CONFIG["gradient_accumulation_steps"],
        learning_rate=CONFIG["learning_rate"],
        warmup_steps=CONFIG["warmup_steps"],
        logging_steps=CONFIG["logging_steps"],
        save_steps=CONFIG["save_steps"],
        fp16=CONFIG["fp16"],
        gradient_checkpointing=CONFIG["gradient_checkpointing"],
        optim=CONFIG["optim"],
        max_grad_norm=CONFIG["max_grad_norm"],
        save_total_limit=3,
        report_to=[],
        dataloader_num_workers=CONFIG["dataloader_num_workers"],
    )
    
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=tokenized_dataset,
    )
    
    print("Starting training...")
    trainer.train()
    
    # Save
    print(f"Saving model to {CONFIG['output_dir']}")
    trainer.save_model(CONFIG["output_dir"])
    tokenizer.save_pretrained(CONFIG["output_dir"])
    
    # Save config
    with open(f"{CONFIG['output_dir']}/training_config.json", "w") as f:
        json.dump(CONFIG, f, indent=2)
    
    print("Training complete! Model saved.")
else:
    print("No training data available. Please upload your dataset first.")
