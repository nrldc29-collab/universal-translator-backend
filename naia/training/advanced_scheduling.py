"""Advanced scheduling strategies for training optimization."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
from transformers import get_linear_schedule_with_warmup, get_cosine_schedule_with_warmup, get_cosine_with_hard_restarts_schedule_with_warmup

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class AdvancedScheduler:
    """Advanced learning rate scheduling strategies."""
    
    def __init__(self, optimizer: torch.optim.Optimizer, num_training_steps: int):
        self.optimizer = optimizer
        self.num_training_steps = num_training_steps
    
    def get_cosine_schedule(
        self,
        num_warmup_steps: int,
        num_cycles: float = 0.5,
        final_lr_factor: float = 0.01,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get cosine annealing schedule."""
        scheduler = get_cosine_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=self.num_training_steps,
            num_cycles=num_cycles,
        )
        logger.info(f"Cosine schedule: warmup={num_warmup_steps}, cycles={num_cycles}")
        return scheduler
    
    def get_cosine_with_restarts(
        self,
        num_warmup_steps: int,
        num_cycles: int = 3,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get cosine schedule with hard restarts."""
        scheduler = get_cosine_with_hard_restarts_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=self.num_training_steps,
            num_cycles=num_cycles,
        )
        logger.info(f"Cosine with restarts: warmup={num_warmup_steps}, cycles={num_cycles}")
        return scheduler
    
    def get_linear_schedule(
        self,
        num_warmup_steps: int,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get linear warmup schedule."""
        scheduler = get_linear_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=self.num_training_steps,
        )
        logger.info(f"Linear schedule: warmup={num_warmup_steps}")
        return scheduler
    
    def get_polynomial_schedule(
        self,
        num_warmup_steps: int,
        power: float = 1.0,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get polynomial decay schedule."""
        from transformers import get_polynomial_decay_schedule_with_warmup
        
        scheduler = get_polynomial_decay_schedule_with_warmup(
            self.optimizer,
            num_warmup_steps=num_warmup_steps,
            num_training_steps=self.num_training_steps,
            power=power,
        )
        logger.info(f"Polynomial schedule: warmup={num_warmup_steps}, power={power}")
        return scheduler
    
    def get_inverse_sqrt_schedule(
        self,
        num_warmup_steps: int,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get inverse square root schedule (common in NLP)."""
        def lr_lambda(current_step):
            if current_step < num_warmup_steps:
                return float(current_step) / float(max(1, num_warmup_steps))
            return max(0.0, float(num_warmup_steps) ** 0.5 / float(max(1, current_step)) ** 0.5)
        
        scheduler = torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)
        logger.info(f"Inverse sqrt schedule: warmup={num_warmup_steps}")
        return scheduler
    
    def get_one_cycle_schedule(
        self,
        max_lr: float,
        total_steps: int,
        pct_start: float = 0.1,
    ) -> torch.optim.lr_scheduler._LRScheduler:
        """Get one-cycle learning rate schedule."""
        scheduler = torch.optim.lr_scheduler.OneCycleLR(
            self.optimizer,
            max_lr=max_lr,
            total_steps=total_steps,
            pct_start=pct_start,
        )
        logger.info(f"One-cycle schedule: max_lr={max_lr}, pct_start={pct_start}")
        return scheduler


class GradientAccumulationScheduler:
    """Dynamic gradient accumulation scheduling."""
    
    def __init__(self, initial_steps: int, final_steps: int, total_steps: int):
        self.initial_steps = initial_steps
        self.final_steps = final_steps
        self.total_steps = total_steps
    
    def get_accumulation_steps(self, current_step: int) -> int:
        """Get current gradient accumulation steps."""
        if current_step < self.total_steps * 0.1:
            return self.initial_steps
        elif current_step < self.total_steps * 0.5:
            return max(self.initial_steps // 2, self.final_steps)
        else:
            return self.final_steps


class BatchSizeScheduler:
    """Dynamic batch size scheduling."""
    
    def __init__(self, initial_batch_size: int, final_batch_size: int, total_steps: int):
        self.initial_batch_size = initial_batch_size
        self.final_batch_size = final_batch_size
        self.total_steps = total_steps
    
    def get_batch_size(self, current_step: int) -> int:
        """Get current batch size."""
        if current_step < self.total_steps * 0.2:
            return self.initial_batch_size
        elif current_step < self.total_steps * 0.8:
            return (self.initial_batch_size + self.final_batch_size) // 2
        else:
            return self.final_batch_size


class SequenceLengthScheduler:
    """Dynamic sequence length scheduling for progressive training."""
    
    def __init__(self, initial_length: int, final_length: int, total_steps: int):
        self.initial_length = initial_length
        self.final_length = final_length
        self.total_steps = total_steps
    
    def get_sequence_length(self, current_step: int) -> int:
        """Get current sequence length."""
        progress = current_step / self.total_steps
        new_length = int(self.initial_length + (self.final_length - self.initial_length) * progress)
        return min(new_length, self.final_length)


class AdaptiveLearningRateScheduler:
    """Adaptive learning rate based on training metrics."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        initial_lr: float,
        min_lr: float = 1e-6,
        patience: int = 3,
        factor: float = 0.5,
    ):
        self.optimizer = optimizer
        self.initial_lr = initial_lr
        self.min_lr = min_lr
        self.patience = patience
        self.factor = factor
        self.best_loss = float('inf')
        self.wait = 0
        self.current_lr = initial_lr
    
    def step(self, loss: float) -> bool:
        """Step the scheduler based on loss."""
        if loss < self.best_loss:
            self.best_loss = loss
            self.wait = 0
            return False
        else:
            self.wait += 1
            if self.wait >= self.patience:
                new_lr = max(self.current_lr * self.factor, self.min_lr)
                if new_lr < self.current_lr:
                    for param_group in self.optimizer.param_groups:
                        param_group['lr'] = new_lr
                    self.current_lr = new_lr
                    self.wait = 0
                    logger.info(f"Reduced learning rate to {new_lr}")
                    return True
        return False


class WarmupScheduler:
    """Custom warmup scheduler."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        warmup_steps: int,
        total_steps: int,
        min_lr: float = 1e-6,
    ):
        self.optimizer = optimizer
        self.warmup_steps = warmup_steps
        self.total_steps = total_steps
        self.min_lr = min_lr
        self.base_lr = optimizer.param_groups[0]['lr']
    
    def get_lr(self, step: int) -> float:
        """Get learning rate at given step."""
        if step < self.warmup_steps:
            return self.min_lr + (self.base_lr - self.min_lr) * step / self.warmup_steps
        else:
            return self.base_lr
    
    def step(self, step: int) -> None:
        """Update learning rate."""
        lr = self.get_lr(step)
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr


def create_training_schedule(
    optimizer: torch.optim.Optimizer,
    num_training_steps: int,
    schedule_type: str = "cosine",
    **kwargs,
) -> torch.optim.lr_scheduler._LRScheduler:
    """Create training schedule based on type."""
    scheduler = AdvancedScheduler(optimizer, num_training_steps)
    
    if schedule_type == "cosine":
        return scheduler.get_cosine_schedule(**kwargs)
    elif schedule_type == "cosine_restarts":
        return scheduler.get_cosine_with_restarts(**kwargs)
    elif schedule_type == "linear":
        return scheduler.get_linear_schedule(**kwargs)
    elif schedule_type == "polynomial":
        return scheduler.get_polynomial_schedule(**kwargs)
    elif schedule_type == "inverse_sqrt":
        return scheduler.get_inverse_sqrt_schedule(**kwargs)
    else:
        logger.warning(f"Unknown schedule type {schedule_type}, using cosine")
        return scheduler.get_cosine_schedule(**kwargs)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Test scheduler
    model = torch.nn.Linear(10, 10)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-4)
    
    scheduler = create_training_schedule(
        optimizer,
        num_training_steps=1000,
        schedule_type="cosine",
        num_warmup_steps=100,
    )
    
    print("\n=== Scheduler Test ===")
    for step in range(0, 200, 20):
        scheduler.step()
        print(f"Step {step}: LR = {optimizer.param_groups[0]['lr']:.6f}")
