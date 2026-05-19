"""Knowledge distillation implementation for NAIA training."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model
from datasets import Dataset
from training.optimized_gpu_config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DistillationTrainer(Trainer):
    """Custom trainer for knowledge distillation."""
    
    def __init__(self, teacher_model, *args, temperature=2.0, alpha=0.5, **kwargs):
        super().__init__(*args, **kwargs)
        self.teacher_model = teacher_model
        self.temperature = temperature
        self.alpha = alpha
        
        # Freeze teacher model
        for param in self.teacher_model.parameters():
            param.requires_grad = False
    
    def compute_loss(self, model, inputs, return_outputs=False):
        """Compute distillation loss."""
        # Student forward pass
        outputs = model(**inputs)
        student_logits = outputs.logits
        
        # Teacher forward pass
        with torch.no_grad():
            teacher_outputs = self.teacher_model(**inputs)
            teacher_logits = teacher_outputs.logits
        
        # Distillation loss
        distillation_loss = F.kl_div(
            F.log_softmax(student_logits / self.temperature, dim=-1),
            F.softmax(teacher_logits / self.temperature, dim=-1),
            reduction="batchmean",
        ) * (self.temperature ** 2)
        
        # Standard cross-entropy loss
        labels = inputs.get("labels", inputs.get("input_ids"))
        if labels is not None:
            # Shift labels for causal LM
            shift_logits = student_logits[..., :-1, :].contiguous()
            shift_labels = labels[..., 1:].contiguous()
            loss_fct = nn.CrossEntropyLoss(ignore_index=-100)
            ce_loss = loss_fct(shift_logits.view(-1, shift_logits.size(-1)), shift_labels.view(-1))
        else:
            ce_loss = torch.tensor(0.0, device=student_logits.device)
        
        # Combined loss
        loss = self.alpha * distillation_loss + (1 - self.alpha) * ce_loss
        
        return (loss, outputs) if return_outputs else loss


def run_knowledge_distillation(
    teacher_model_name: str,
    dataset_path: str,
    output_dir: str,
    config_profile: str = "optimized",
    temperature: float = 2.0,
    alpha: float = 0.5,
) -> dict[str, Any]:
    """Run knowledge distillation training."""
    config = get_config(config_profile)
    
    logger.info(f"Loading teacher model: {teacher_model_name}")
    teacher_tokenizer = AutoTokenizer.from_pretrained(teacher_model_name)
    teacher_model = AutoModelForCausalLM.from_pretrained(
        teacher_model_name,
        device_map="auto",
        torch_dtype=torch.float16,
    )
    
    logger.info(f"Loading student model: {config['model_name']}")
    student_tokenizer = AutoTokenizer.from_pretrained(config["model_name"])
    student_model = AutoModelForCausalLM.from_pretrained(
        config["model_name"],
        device_map="auto",
        load_in_8bit=True,
        torch_dtype=torch.float16,
    )
    
    # Configure LoRA for student
    lora_config = LoraConfig(
        r=config["lora_r"],
        lora_alpha=config["lora_alpha"],
        target_modules=config["target_modules"],
        lora_dropout=config["lora_dropout"],
        bias=config["bias"],
        task_type=config["task_type"],
    )
    
    student_model = get_peft_model(student_model, lora_config)
    student_model.print_trainable_parameters()
    
    # Load dataset
    with open(dataset_path, encoding="utf-8") as f:
        train_data = json.load(f)
    
    train_examples = [{"instruction": ex.get("input", ex.get("instruction", "")), 
                      "output": ex.get("output", "")} for ex in train_data]
    
    train_dataset = Dataset.from_list(train_examples)
    
    def tokenize_function(examples):
        return student_tokenizer(
            examples["instruction"],
            examples["output"],
            truncation=True,
            max_length=config["max_seq_length"],
            padding="max_length",
        )
    
    tokenized_dataset = train_dataset.map(tokenize_function, batched=True)
    
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
        fp16=config["fp16"],
        gradient_checkpointing=config.get("gradient_checkpointing", False),
        optim=config.get("optim", "adamw_torch"),
        max_grad_norm=config.get("max_grad_norm", 1.0),
        save_total_limit=3,
        dataloader_num_workers=config.get("dataloader_num_workers", 2),
        dataloader_pin_memory=True,
        report_to=[],
        lr_scheduler_type="cosine",
        weight_decay=0.01,
    )
    
    # Create distillation trainer
    trainer = DistillationTrainer(
        teacher_model=teacher_model,
        model=student_model,
        args=training_args,
        train_dataset=tokenized_dataset,
        temperature=temperature,
        alpha=alpha,
    )
    
    logger.info("Starting knowledge distillation training...")
    trainer.train()
    
    logger.info(f"Saving student model to {output_dir}")
    trainer.save_model(output_dir)
    student_tokenizer.save_pretrained(output_dir)
    
    config_path = Path(output_dir) / "distillation_config.json"
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump({
            "training_config": config,
            "distillation_config": {
                "teacher_model": teacher_model_name,
                "temperature": temperature,
                "alpha": alpha,
            },
        }, f, indent=2)
    
    logger.info("Knowledge distillation complete")
    
    return {
        "status": "success",
        "output_dir": output_dir,
        "teacher_model": teacher_model_name,
        "student_model": config["model_name"],
        "training_config": config,
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    result = run_knowledge_distillation(
        teacher_model_name="Qwen/Qwen2.5-7B-Instruct",
        dataset_path="dataset/output/train_set.json",
        output_dir="models/naia-distilled-student",
        config_profile="optimized",
        temperature=2.0,
        alpha=0.5,
    )
    
    print("\n=== Knowledge Distillation Complete ===")
    print(json.dumps(result, indent=2))
