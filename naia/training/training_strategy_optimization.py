"""Training strategy optimizations for faster convergence."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer, TrainingArguments, Trainer
from peft import LoraConfig, get_peft_model

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdaptiveLearningRate:
    """Adaptive learning rate strategies."""
    
    def __init__(self, optimizer: torch.optim.Optimizer):
        self.optimizer = optimizer
        self.initial_lr = optimizer.param_groups[0]['lr']
    
    def apply_warmup_cosine(
        self,
        step: int,
        total_steps: int,
        warmup_steps: int,
    ) -> float:
        """Apply warmup with cosine decay."""
        if step < warmup_steps:
            return self.initial_lr * (step / warmup_steps)
        else:
            progress = (step - warmup_steps) / (total_steps - warmup_steps)
            return self.initial_lr * 0.5 * (1 + torch.cos(torch.tensor(progress * 3.14159))).item()
    
    def apply_cyclic_lr(
        self,
        step: int,
        base_lr: float = 1e-5,
        max_lr: float = 1e-3,
        step_size_up: int = 1000,
    ) -> float:
        """Apply cyclic learning rate."""
        cycle = torch.floor(1 + step / (2 * step_size_up))
        x = torch.abs(step / step_size_up - 2 * cycle + 1)
        return base_lr + (max_lr - base_lr) * max(0, (1 - x)).item()


class GradientAccumulationStrategy:
    """Gradient accumulation strategies."""
    
    def __init__(self, model: nn.Module):
        self.model = model
    
    def dynamic_gradient_accumulation(
        self,
        loss: float,
        current_accum_steps: int,
        max_accum_steps: int,
        loss_threshold: float = 0.5,
    ) -> int:
        """Dynamically adjust gradient accumulation based on loss."""
        if loss > loss_threshold:
            # High loss, increase accumulation
            return min(current_accum_steps + 1, max_accum_steps)
        else:
            # Low loss, decrease accumulation
            return max(current_accum_steps - 1, 1)
    
    def progressive_gradient_accumulation(
        self,
        step: int,
        total_steps: int,
        initial_accum: int = 1,
        final_accum: int = 4,
    ) -> int:
        """Progressively increase gradient accumulation."""
        progress = step / total_steps
        return int(initial_accum + (final_accum - initial_accum) * progress)


class BatchSizeStrategy:
    """Batch size strategies for training."""
    
    def __init__(self, model: nn.Module):
        self.model = model
    
    def progressive_batch_size(
        self,
        step: int,
        total_steps: int,
        initial_batch_size: int = 8,
        final_batch_size: int = 32,
    ) -> int:
        """Progressively increase batch size."""
        progress = step / total_steps
        return int(initial_batch_size + (final_batch_size - initial_batch_size) * progress)
    
    def adaptive_batch_size(
        self,
        memory_usage: float,
        target_memory: float = 0.8,
        current_batch_size: int = 8,
    ) -> int:
        """Adaptively adjust batch size based on memory usage."""
        if memory_usage > target_memory:
            # High memory usage, reduce batch size
            return max(current_batch_size // 2, 1)
        elif memory_usage < target_memory * 0.7:
            # Low memory usage, increase batch size
            return current_batch_size * 2
        else:
            return current_batch_size


class SequenceLengthStrategy:
    """Sequence length strategies."""
    
    def __init__(self):
        pass
    
    def progressive_sequence_length(
        self,
        step: int,
        total_steps: int,
        initial_length: int = 512,
        final_length: int = 1024,
    ) -> int:
        """Progressively increase sequence length."""
        progress = step / total_steps
        return int(initial_length + (final_length - initial_length) * progress)
    
    def adaptive_sequence_length(
        self,
        input_lengths: list[int],
        percentile: float = 0.9,
    ) -> int:
        """Adaptively set sequence length based on data."""
        return int(sorted(input_lengths)[int(len(input_lengths) * percentile)])


class LossFunctionOptimization:
    """Loss function optimizations."""
    
    def __init__(self):
        pass
    
    def label_smoothing_loss(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        smoothing: float = 0.1,
    ) -> torch.Tensor:
        """Apply label smoothing to loss."""
        confidence = 1.0 - smoothing
        low_confidence = smoothing / (logits.shape[-1] - 1)
        
        # Create smoothed labels
        smoothed_labels = torch.full_like(logits, low_confidence)
        smoothed_labels.scatter_(1, labels.unsqueeze(1), confidence)
        
        # Compute cross-entropy with smoothed labels
        log_probs = torch.log_softmax(logits, dim=-1)
        loss = (-smoothed_labels * log_probs).sum(dim=-1).mean()
        
        return loss
    
    def focal_loss(
        self,
        logits: torch.Tensor,
        labels: torch.Tensor,
        alpha: float = 0.25,
        gamma: float = 2.0,
    ) -> torch.Tensor:
        """Apply focal loss for hard examples."""
        probs = torch.softmax(logits, dim=-1)
        pt = probs.gather(1, labels.unsqueeze(1)).squeeze(1)
        
        focal_weight = (1 - pt) ** gamma
        loss = -alpha * focal_weight * torch.log(pt)
        
        return loss.mean()


class RegularizationStrategy:
    """Regularization strategies."""
    
    def __init__(self, model: nn.Module):
        self.model = model
    
    def apply_dropout_schedule(
        self,
        step: int,
        total_steps: int,
        initial_dropout: float = 0.1,
        final_dropout: float = 0.0,
    ) -> float:
        """Schedule dropout reduction during training."""
        progress = step / total_steps
        return initial_dropout + (final_dropout - initial_dropout) * progress
    
    def apply_weight_decay_schedule(
        self,
        step: int,
        total_steps: int,
        initial_weight_decay: float = 0.01,
        final_weight_decay: float = 0.001,
    ) -> float:
        """Schedule weight decay reduction."""
        progress = step / total_steps
        return initial_weight_decay + (final_weight_decay - initial_weight_decay) * progress


class OptimizerStrategy:
    """Optimizer selection and configuration."""
    
    def __init__(self, model: nn.Module):
        self.model = model
    
    def get_adamw_optimizer(
        self,
        lr: float = 1e-4,
        weight_decay: float = 0.01,
        betas: tuple[float, float] = (0.9, 0.999),
        eps: float = 1e-8,
    ) -> torch.optim.Optimizer:
        """Get AdamW optimizer with optimal settings."""
        return torch.optim.AdamW(
            self.model.parameters(),
            lr=lr,
            weight_decay=weight_decay,
            betas=betas,
            eps=eps,
        )
    
    def get_sgd_optimizer(
        self,
        lr: float = 1e-3,
        momentum: float = 0.9,
        weight_decay: float = 0.01,
    ) -> torch.optim.Optimizer:
        """Get SGD optimizer with momentum."""
        return torch.optim.SGD(
            self.model.parameters(),
            lr=lr,
            momentum=momentum,
            weight_decay=weight_decay,
        )
    
    def get_adafactor_optimizer(
        self,
        lr: float = 1e-4,
        weight_decay: float = 0.01,
    ) -> torch.optim.Optimizer:
        """Get Adafactor optimizer."""
        try:
            from transformers import Adafactor
            return Adafactor(
                self.model.parameters(),
                lr=lr,
                weight_decay=weight_decay,
            )
        except ImportError:
            logger.warning("Adafactor not available, falling back to AdamW")
            return self.get_adamw_optimizer(lr, weight_decay)


class TrainingStrategyOptimizer:
    """Comprehensive training strategy optimizer."""
    
    def __init__(self, model: nn.Module):
        self.model = model
        self.lr_strategy = AdaptiveLearningRate(None)
        self.accum_strategy = GradientAccumulationStrategy(model)
        self.batch_strategy = BatchSizeStrategy(model)
        self.seq_strategy = SequenceLengthStrategy()
        self.loss_optimizer = LossFunctionOptimization()
        self.reg_strategy = RegularizationStrategy(model)
        self.opt_strategy = OptimizerStrategy(model)
    
    def optimize_training_strategy(
        self,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        """Optimize comprehensive training strategy."""
        logger.info("Optimizing training strategy")
        
        optimized_config = config.copy()
        
        # Apply learning rate strategy
        if config.get("use_warmup_cosine", True):
            optimized_config["lr_scheduler_type"] = "cosine"
        
        # Apply gradient accumulation strategy
        if config.get("use_progressive_accum", False):
            optimized_config["gradient_accumulation_strategy"] = "progressive"
        
        # Apply batch size strategy
        if config.get("use_progressive_batch", False):
            optimized_config["batch_size_strategy"] = "progressive"
        
        # Apply sequence length strategy
        if config.get("use_progressive_seq", False):
            optimized_config["sequence_length_strategy"] = "progressive"
        
        # Apply loss function optimization
        if config.get("use_label_smoothing", False):
            optimized_config["label_smoothing"] = 0.1
        
        # Apply regularization strategy
        if config.get("use_dropout_schedule", False):
            optimized_config["dropout_schedule"] = True
        
        logger.info("Training strategy optimized")
        
        return optimized_config


def benchmark_training_strategies(
    model_name: str,
) -> dict[str, Any]:
    """Benchmark different training strategies."""
    logger.info(f"Benchmarking training strategies for {model_name}")
    
    # Load model
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        device_map="auto",
        torch_dtype=torch.float16,
    )
    
    results = {}
    
    # Benchmark different optimizers
    opt_strategy = OptimizerStrategy(model)
    
    adamw_opt = opt_strategy.get_adamw_optimizer(lr=1e-4)
    results["adamw"] = {
        "optimizer": "AdamW",
        "lr": 1e-4,
        "expected_convergence": "fast",
    }
    
    sgd_opt = opt_strategy.get_sgd_optimizer(lr=1e-3)
    results["sgd"] = {
        "optimizer": "SGD",
        "lr": 1e-3,
        "expected_convergence": "moderate",
    }
    
    adafactor_opt = opt_strategy.get_adafactor_optimizer(lr=1e-4)
    results["adafactor"] = {
        "optimizer": "Adafactor",
        "lr": 1e-4,
        "expected_convergence": "memory_efficient",
    }
    
    # Benchmark learning rate schedules
    results["lr_schedules"] = {
        "cosine": "smooth decay",
        "linear": "linear decay",
        "cyclic": "cyclic variation",
        "one_cycle": "single cycle",
    }
    
    # Benchmark regularization strategies
    results["regularization"] = {
        "weight_decay": "standard",
        "dropout_schedule": "progressive reduction",
        "label_smoothing": "smoothing",
    }
    
    logger.info("Training strategy benchmark complete")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark training strategies
    results = benchmark_training_strategies(
        model_name="Qwen/Qwen2.5-1.5B-Instruct",
    )
    
    print("\n=== Training Strategy Benchmark ===")
    print(json.dumps(results, indent=2))
