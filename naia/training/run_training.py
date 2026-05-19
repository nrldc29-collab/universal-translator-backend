"""Run full training pipeline for NAIA student model."""

from __future__ import annotations

import logging
from pathlib import Path

try:
    from training.prepare_dataset import prepare_combined_dataset, prepare_unsloth_dataset
    from training.preflight import print_training_preflight, require_unsloth_training_ready, run_training_preflight
    from training.run_local_training import run_local_training
except ModuleNotFoundError:
    import sys

    sys.path.append(str(Path(__file__).resolve().parents[1]))
    from training.prepare_dataset import prepare_combined_dataset, prepare_unsloth_dataset
    from training.preflight import print_training_preflight, require_unsloth_training_ready, run_training_preflight
    from training.run_local_training import run_local_training

logger = logging.getLogger(__name__)


def run_full_training_pipeline(
    dataset_dir: str = "dataset/output",
    output_dir: str = "./naia-student-3b-lora",
    base_model: str = "Qwen/Qwen2.5-3B-Instruct",
    lora_r: int = 64,
    lora_alpha: int = 16,
    learning_rate: float = 2e-4,
    num_epochs: int = 3,
    max_seq_length: int = 4096,
    batch_size: int = 4,
    gradient_accumulation_steps: int = 4,
    skip_preflight: bool = False,
    fallback_to_local: bool = False,
    local_output_dir: str = "models/naia-local-student",
) -> None:
    """
    Run the full training pipeline.

    Args:
        dataset_dir: Directory containing generated datasets
        output_dir: Output directory for trained model
        base_model: Base model identifier
        lora_r: LoRA rank
        lora_alpha: LoRA alpha
        learning_rate: Learning rate
        num_epochs: Number of training epochs
        max_seq_length: Maximum sequence length
        batch_size: Per-device batch size
        gradient_accumulation_steps: Gradient accumulation steps
    """
    dataset_path = Path(dataset_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    if fallback_to_local:
        logger.info("Running local CPU student training (default for this environment).")
        training_data_path = _prepare_training_data(dataset_path)
        metadata = run_local_training(str(training_data_path), local_output_dir)
        logger.info(f"Local CPU student artifact saved: {metadata['artifact']}")
        return

    if not skip_preflight:
        result = run_training_preflight(dataset_path)
        if not result.can_train_unsloth:
            require_unsloth_training_ready(dataset_path)

    import torch
    from datasets import load_dataset
    from transformers import TrainingArguments
    from trl import SFTTrainer
    from unsloth import FastLanguageModel

    logger.info("Step 1: Preparing dataset for Unsloth training")
    training_data_path = _prepare_training_data(dataset_path)
    logger.info(f"Training data prepared: {training_data_path}")

    # Step 2: Load base model
    logger.info("Step 2: Loading base model with 4-bit quantization")
    
    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name=base_model,
        max_seq_length=max_seq_length,
        dtype=None,  # Auto-detect
        load_in_4bit=True,
    )

    # Step 3: Configure LoRA
    logger.info("Step 3: Configuring LoRA adapters")
    
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

    # Step 4: Load dataset
    logger.info("Step 4: Loading training dataset")
    
    dataset = load_dataset("json", data_files=str(training_data_path), split="train")
    logger.info(f"Dataset loaded: {len(dataset)} examples")

    # Step 5: Configure training
    logger.info("Step 5: Configuring training arguments")
    
    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
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

    # Step 6: Create trainer
    logger.info("Step 6: Creating trainer")
    
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

    # Step 7: Train
    logger.info("Step 7: Starting training")
    
    trainer.train()

    # Step 8: Save LoRA adapter
    logger.info("Step 8: Saving LoRA adapter weights")
    
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))
    
    logger.info(f"LoRA adapter saved to: {output_dir}")

    # Step 9: Merge LoRA with base model
    logger.info("Step 9: Merging LoRA with base model")
    
    model.save_pretrained_merged(
        str(output_path / "merged"),
        tokenizer,
        save_method="merged_16bit",
    )
    
    logger.info(f"Merged model saved to: {output_path / 'merged'}")

    logger.info("Training pipeline complete!")


def _prepare_training_data(dataset_path: Path) -> Path:
    single_shot_jsonl = dataset_path / "single_shot.jsonl"
    pipeline_aware_jsonl = dataset_path / "pipeline_aware.jsonl"
    combined_json = dataset_path / "combined_unsloth.json"

    if single_shot_jsonl.exists() and pipeline_aware_jsonl.exists():
        prepare_combined_dataset(
            single_shot_jsonl,
            pipeline_aware_jsonl,
            combined_json,
        )
        return combined_json
    if single_shot_jsonl.exists():
        single_shot_unsloth = dataset_path / "single_shot_unsloth.json"
        prepare_unsloth_dataset(single_shot_jsonl, single_shot_unsloth)
        return single_shot_unsloth
    if combined_json.exists():
        return combined_json
    raise FileNotFoundError("No training data found. Please generate dataset first.")


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    run_full_training_pipeline(
        dataset_dir="dataset/output",
        output_dir="./naia-student-3b-lora",
        base_model="Qwen/Qwen2.5-3B-Instruct",
        num_epochs=3,
    )
