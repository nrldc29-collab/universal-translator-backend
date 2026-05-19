"""Advanced learning rate schedulers including cosine with warmup restarts."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CosineWithWarmupRestarts:
    """Cosine annealing with warmup and restarts."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        first_cycle_steps: int,
        cycle_mult: float = 1.0,
        max_lr: float = 1e-3,
        min_lr: float = 1e-6,
        warmup_steps: int = 0,
        gamma: float = 1.0,
    ):
        self.optimizer = optimizer
        self.first_cycle_steps = first_cycle_steps
        self.cycle_mult = cycle_mult
        self.max_lr = max_lr
        self.min_lr = min_lr
        self.warmup_steps = warmup_steps
        self.gamma = gamma
        
        self.current_step = 0
        self.current_cycle = 0
        self.cycle_steps = first_cycle_steps
    
    def step(self) -> float:
        """Update learning rate."""
        if self.current_step < self.warmup_steps:
            # Warmup phase
            lr = self.max_lr * self.current_step / self.warmup_steps
        else:
            # Cosine annealing phase
            cycle_step = self.current_step - self.warmup_steps
            progress = cycle_step / self.cycle_steps
            
            lr = self.min_lr + (self.max_lr - self.min_lr) * 0.5 * (
                1 + torch.cos(torch.tensor(progress * 3.14159))
            ).item()
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        # Check for cycle restart
        if self.current_step >= self.cycle_steps + self.warmup_steps:
            self.current_step = 0
            self.current_cycle += 1
            self.cycle_steps = int(self.cycle_steps * self.cycle_mult)
            self.max_lr *= self.gamma
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


class OneCycleScheduler:
    """One-cycle learning rate scheduler."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        max_lr: float = 1e-3,
        total_steps: int = 1000,
        pct_start: float = 0.3,
        anneal_strategy: str = "cos",
        div_factor: float = 25.0,
        final_div_factor: float = 1e4,
    ):
        self.optimizer = optimizer
        self.max_lr = max_lr
        self.total_steps = total_steps
        self.pct_start = pct_start
        self.anneal_strategy = anneal_strategy
        self.div_factor = div_factor
        self.final_div_factor = final_div_factor
        
        self.current_step = 0
        self.initial_lr = max_lr / div_factor
        self.min_lr = max_lr / final_div_factor
    
    def step(self) -> float:
        """Update learning rate."""
        if self.current_step < self.total_steps * self.pct_start:
            # Increasing phase
            progress = self.current_step / (self.total_steps * self.pct_start)
            
            if self.anneal_strategy == "cos":
                lr = self.initial_lr + (self.max_lr - self.initial_lr) * 0.5 * (
                    1 - torch.cos(torch.tensor(progress * 3.14159))
                ).item()
            else:
                lr = self.initial_lr + (self.max_lr - self.initial_lr) * progress
        else:
            # Decreasing phase
            progress = (self.current_step - self.total_steps * self.pct_start) / (
                self.total_steps * (1 - self.pct_start)
            )
            
            if self.anneal_strategy == "cos":
                lr = self.max_lr + (self.min_lr - self.max_lr) * 0.5 * (
                    1 + torch.cos(torch.tensor(progress * 3.14159))
                ).item()
            else:
                lr = self.max_lr - (self.max_lr - self.min_lr) * progress
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


class PolynomialDecayWithWarmup:
    """Polynomial decay with warmup."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        max_lr: float = 1e-3,
        total_steps: int = 1000,
        warmup_steps: int = 100,
        power: float = 1.0,
        end_lr: float = 0.0,
    ):
        self.optimizer = optimizer
        self.max_lr = max_lr
        self.total_steps = total_steps
        self.warmup_steps = warmup_steps
        self.power = power
        self.end_lr = end_lr
        
        self.current_step = 0
    
    def step(self) -> float:
        """Update learning rate."""
        if self.current_step < self.warmup_steps:
            # Warmup phase
            lr = self.max_lr * self.current_step / self.warmup_steps
        else:
            # Polynomial decay phase
            progress = (self.current_step - self.warmup_steps) / (self.total_steps - self.warmup_steps)
            lr = (self.max_lr - self.end_lr) * (1 - progress) ** self.power + self.end_lr
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


class InverseSqrtScheduler:
    """Inverse square root decay scheduler."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        max_lr: float = 1e-3,
        warmup_steps: int = 100,
        factor: float = 1.0,
    ):
        self.optimizer = optimizer
        self.max_lr = max_lr
        self.warmup_steps = warmup_steps
        self.factor = factor
        
        self.current_step = 0
    
    def step(self) -> float:
        """Update learning rate."""
        if self.current_step < self.warmup_steps:
            # Warmup phase
            lr = self.max_lr * self.current_step / self.warmup_steps
        else:
            # Inverse sqrt decay
            lr = self.max_lr * self.factor / (self.current_step ** 0.5)
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


class LinearWithWarmup:
    """Linear decay with warmup."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        max_lr: float = 1e-3,
        total_steps: int = 1000,
        warmup_steps: int = 100,
    ):
        self.optimizer = optimizer
        self.max_lr = max_lr
        self.total_steps = total_steps
        self.warmup_steps = warmup_steps
        
        self.current_step = 0
    
    def step(self) -> float:
        """Update learning rate."""
        if self.current_step < self.warmup_steps:
            # Warmup phase
            lr = self.max_lr * self.current_step / self.warmup_steps
        else:
            # Linear decay
            progress = (self.current_step - self.warmup_steps) / (self.total_steps - self.warmup_steps)
            lr = self.max_lr * (1 - progress)
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


class AdaptiveScheduler:
    """Adaptive learning rate scheduler based on metrics."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        metric: str = "loss",
        patience: int = 10,
        factor: float = 0.5,
        min_lr: float = 1e-6,
        mode: str = "min",
    ):
        self.optimizer = optimizer
        self.metric = metric
        self.patience = patience
        self.factor = factor
        self.min_lr = min_lr
        self.mode = mode
        
        self.best_metric = float('inf') if mode == "min" else -float('inf')
        self.wait_count = 0
        self.current_lr = optimizer.param_groups[0]['lr']
    
    def step(self, current_metric: float) -> float:
        """Update learning rate based on metric."""
        is_better = (current_metric < self.best_metric) if self.mode == "min" else (current_metric > self.best_metric)
        
        if is_better:
            self.best_metric = current_metric
            self.wait_count = 0
        else:
            self.wait_count += 1
        
        if self.wait_count >= self.patience:
            # Reduce learning rate
            new_lr = max(self.current_lr * self.factor, self.min_lr)
            
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = new_lr
            
            self.current_lr = new_lr
            self.wait_count = 0
            
            logger.info(f"Reduced learning rate to {new_lr}")
        
        return self.current_lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.current_lr


class CyclicLR:
    """Cyclic learning rate scheduler."""
    
    def __init__(
        self,
        optimizer: torch.optim.Optimizer,
        base_lr: float = 1e-5,
        max_lr: float = 1e-3,
        step_size_up: int = 1000,
        step_size_down: int | None = None,
        mode: str = "triangular",
        gamma: float = 1.0,
    ):
        self.optimizer = optimizer
        self.base_lr = base_lr
        self.max_lr = max_lr
        self.step_size_up = step_size_up
        self.step_size_down = step_size_down or step_size_up
        self.mode = mode
        self.gamma = gamma
        
        self.current_step = 0
        self.cycle_length = self.step_size_up + self.step_size_down
    
    def step(self) -> float:
        """Update learning rate."""
        cycle = self.current_step // self.cycle_length
        step_in_cycle = self.current_step % self.cycle_length
        
        if self.mode == "triangular":
            if step_in_cycle < self.step_size_up:
                lr = self.base_lr + (self.max_lr - self.base_lr) * step_in_cycle / self.step_size_up
            else:
                lr = self.max_lr - (self.max_lr - self.base_lr) * (step_in_cycle - self.step_size_up) / self.step_size_down
        elif self.mode == "triangular2":
            max_lr_cycle = self.max_lr * (self.gamma ** cycle)
            if step_in_cycle < self.step_size_up:
                lr = self.base_lr + (max_lr_cycle - self.base_lr) * step_in_cycle / self.step_size_up
            else:
                lr = max_lr_cycle - (max_lr_cycle - self.base_lr) * (step_in_cycle - self.step_size_up) / self.step_size_down
        elif self.mode == "exp_range":
            max_lr_cycle = self.max_lr * (self.gamma ** cycle)
            lr = self.base_lr + (max_lr_cycle - self.base_lr) * max(0, 1 - step_in_cycle / self.cycle_length)
        
        # Update learning rate
        for param_group in self.optimizer.param_groups:
            param_group['lr'] = lr
        
        self.current_step += 1
        
        return lr
    
    def get_lr(self) -> float:
        """Get current learning rate."""
        return self.optimizer.param_groups[0]['lr']


def benchmark_schedulers(
    total_steps: int = 1000,
) -> dict[str, Any]:
    """Benchmark different learning rate schedulers."""
    logger.info(f"Benchmarking schedulers for {total_steps} steps")
    
    results = {}
    
    # Cosine with warmup restarts
    results["cosine_warmup_restarts"] = {
        "strategy": "Cosine with warmup and restarts",
        "convergence": "fast",
        "recommended_for": "large models",
    }
    
    # One-cycle
    results["one_cycle"] = {
        "strategy": "One-cycle",
        "convergence": "very fast",
        "recommended_for": "general purpose",
    }
    
    # Polynomial decay
    results["polynomial"] = {
        "strategy": "Polynomial decay",
        "convergence": "medium",
        "recommended_for": "stable training",
    }
    
    # Inverse sqrt
    results["inverse_sqrt"] = {
        "strategy": "Inverse square root",
        "convergence": "medium",
        "recommended_for": "transformers",
    }
    
    # Linear with warmup
    results["linear_warmup"] = {
        "strategy": "Linear with warmup",
        "convergence": "medium",
        "recommended_for": "simple training",
    }
    
    # Adaptive
    results["adaptive"] = {
        "strategy": "Adaptive",
        "convergence": "adaptive",
        "recommended_for": "unstable training",
    }
    
    # Cyclic
    results["cyclic"] = {
        "strategy": "Cyclic",
        "convergence": "fast",
        "recommended_for": "escaping local minima",
    }
    
    logger.info("Scheduler benchmark complete")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark schedulers
    results = benchmark_schedulers(
        total_steps=1000,
    )
    
    print("\n=== Scheduler Benchmark ===")
    print(json.dumps(results, indent=2))
