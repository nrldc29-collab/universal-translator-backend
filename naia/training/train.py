"""Training script for NAIA student model using unsloth."""

from __future__ import annotations

from pathlib import Path

try:
    from training.preflight import require_unsloth_training_ready
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.preflight import require_unsloth_training_ready


def train_model(
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    dataset_path: str = "dataset/output/combined_unsloth.json",
    output_dir: str = "./naia-student-3b-lora",
    lora_r: int = 64,
    lora_alpha: int = 16,
    learning_rate: float = 2e-4,
    num_epochs: int = 3,
    max_seq_length: int = 4096,
    skip_preflight: bool = False,
) -> None:
    """
    Train the NAIA student model using LoRA fine-tuning.

    Args:
        base_model: Base model identifier
        dataset_path: Path to training dataset
        output_dir: Output directory for trained model
        lora_r: LoRA rank
        lora_alpha: LoRA alpha
        learning_rate: Learning rate
        num_epochs: Number of training epochs
        max_seq_length: Maximum sequence length
    """
    if not skip_preflight:
        require_unsloth_training_ready(Path(dataset_path).parent)

    import torch
    from datasets import load_dataset
    from transformers import TrainingArguments
    from trl import SFTTrainer
    from unsloth import FastLanguageModel

    # Load base model with 4-bit quantization
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=max_seq_length,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Configure LoRA
    model = FastLanguageModel.get_peft_model(
        model,
        r=lora_r,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_alpha=lora_alpha,
        lora_dropout=0.05,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=3407,
        use_rslora=False,
        loftq_config=None,
    )

    # Load dataset
    dataset = load_dataset("json", data_files=dataset_path, split="train")

    # Training arguments
    training_args = TrainingArguments(
        output_dir=output_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=learning_rate,
        weight_decay=0.01,
        warmup_steps=100,
        logging_steps=10,
        save_steps=500,
        save_total_limit=3,
        optim="adamw_torch",
        lr_scheduler_type="cosine",
        max_grad_norm=1.0,
        fp16=False,
        bf16=torch.cuda.is_available() and torch.cuda.is_bf16_supported(),
        gradient_checkpointing=True,
        report_to="none",
    )

    # Trainer
    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=dataset,
        dataset_text_field="text",
        max_seq_length=max_seq_length,
        dataset_num_proc=4,
        packing=False,
        args=training_args,
    )

    # Train
    trainer.train()

    # Save model
    trainer.save_model(output_dir)
    tokenizer.save_pretrained(output_dir)

    print(f"Model saved to {output_dir}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Train NAIA student model")
    parser.add_argument("--base-model", type=str, default="Qwen/Qwen2.5-3B-Instruct")
    parser.add_argument("--dataset-path", type=str, default="dataset/output/combined_unsloth.json")
    parser.add_argument("--output-dir", type=str, default="./naia-student-3b-lora")
    parser.add_argument("--lora-r", type=int, default=64)
    parser.add_argument("--lora-alpha", type=int, default=16)
    parser.add_argument("--learning-rate", type=float, default=2e-4)
    parser.add_argument("--num-epochs", type=int, default=3)
    parser.add_argument("--max-seq-length", type=int, default=4096)
    parser.add_argument("--skip-preflight", action="store_true")

    args = parser.parse_args()

    train_model(
        base_model=args.base_model,
        dataset_path=args.dataset_path,
        output_dir=args.output_dir,
        lora_r=args.lora_r,
        lora_alpha=args.lora_alpha,
        learning_rate=args.learning_rate,
        num_epochs=args.num_epochs,
        max_seq_length=args.max_seq_length,
        skip_preflight=args.skip_preflight,
    )
