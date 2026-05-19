"""Automated hyperparameter tuning for NAIA training."""

from __future__ import annotations

import json
import logging
import random
from pathlib import Path
from typing import Any

import optuna
from training.optimized_gpu_config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def objective(trial: optuna.Trial) -> float:
    """Objective function for hyperparameter optimization."""
    # Suggest hyperparameters
    batch_size = trial.suggest_categorical("batch_size", [8, 16, 24, 32])
    learning_rate = trial.suggest_float("learning_rate", 1e-5, 5e-4, log=True)
    lora_r = trial.suggest_categorical("lora_r", [2, 4, 6, 8])
    lora_alpha = trial.suggest_categorical("lora_alpha", [4, 8, 12, 16])
    lora_dropout = trial.suggest_float("lora_dropout", 0.0, 0.2)
    warmup_steps = trial.suggest_int("warmup_steps", 10, 200)
    gradient_accumulation_steps = trial.suggest_categorical("gradient_accumulation_steps", [1, 2, 4])
    
    # Create trial configuration
    trial_config = {
        "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
        "max_seq_length": 1024,
        "batch_size": batch_size,
        "gradient_accumulation_steps": gradient_accumulation_steps,
        "learning_rate": learning_rate,
        "num_train_epochs": 1,  # Use fewer epochs for tuning
        "warmup_steps": warmup_steps,
        "logging_steps": 20,
        "save_steps": 500,
        "fp16": True,
        "gradient_checkpointing": True,
        "optim": "adamw_torch",
        "lora_r": lora_r,
        "lora_alpha": lora_alpha,
        "lora_dropout": lora_dropout,
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "bias": "none",
        "task_type": "CAUSAL_LM",
        "dataloader_num_workers": 4,
        "max_grad_norm": 1.0,
        "use_flash_attention": True,
        "use_torch_compile": True,
    }
    
    # In a real implementation, this would run training and return validation loss
    # For now, simulate with a synthetic objective
    # Lower values are better
    synthetic_loss = (
        0.3 * (batch_size / 32) +  # Prefer larger batch sizes
        0.2 * (1 / learning_rate) +  # Prefer higher learning rates
        0.2 * (lora_r / 8) +  # Prefer smaller LoRA rank
        0.1 * lora_dropout +  # Prefer lower dropout
        0.1 * (warmup_steps / 200) +  # Prefer fewer warmup steps
        0.1 * gradient_accumulation_steps  # Prefer lower accumulation
    ) + random.uniform(0.0, 0.1)  # Add some noise
    
    logger.info(f"Trial {trial.number}: Loss={synthetic_loss:.4f}, Config={trial_config}")
    
    return synthetic_loss


def run_hyperparameter_tuning(
    n_trials: int = 50,
    output_dir: str = "training/hyperparameter_tuning",
    timeout: int | None = None,
) -> dict[str, Any]:
    """Run automated hyperparameter tuning with Optuna."""
    logger.info(f"Starting hyperparameter tuning with {n_trials} trials")
    
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    # Create study
    study = optuna.create_study(
        direction="minimize",
        study_name="naia_hyperparameter_tuning",
        storage=f"sqlite:///{output_path}/study.db",
    )
    
    # Optimize
    study.optimize(
        objective,
        n_trials=n_trials,
        timeout=timeout,
        show_progress_bar=True,
    )
    
    # Get best trial
    best_trial = study.best_trial
    best_params = best_trial.params
    
    logger.info(f"Best trial: {best_trial.value}")
    logger.info(f"Best params: {best_params}")
    
    # Save results
    results = {
        "best_value": best_trial.value,
        "best_params": best_params,
        "n_trials": len(study.trials),
        "study_name": study.study_name,
    }
    
    results_file = output_path / "tuning_results.json"
    with open(results_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    # Save best configuration
    best_config = {
        "model_name": "Qwen/Qwen2.5-1.5B-Instruct",
        "max_seq_length": 1024,
        **best_params,
        "num_train_epochs": 2,  # Use more epochs for final training
        "logging_steps": 20,
        "save_steps": 1000,
        "fp16": True,
        "gradient_checkpointing": True,
        "optim": "adamw_torch",
        "target_modules": ["q_proj", "k_proj", "v_proj", "o_proj"],
        "bias": "none",
        "task_type": "CAUSAL_LM",
        "dataloader_num_workers": 4,
        "max_grad_norm": 1.0,
        "use_flash_attention": True,
        "use_torch_compile": True,
    }
    
    config_file = output_path / "best_config.json"
    with open(config_file, "w", encoding="utf-8") as f:
        json.dump(best_config, f, indent=2)
    
    logger.info(f"Hyperparameter tuning complete. Results saved to {output_dir}")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    results = run_hyperparameter_tuning(
        n_trials=50,
        output_dir="training/hyperparameter_tuning",
        timeout=None,
    )
    
    print("\n=== Hyperparameter Tuning Complete ===")
    print(json.dumps(results, indent=2))
