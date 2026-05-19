"""TensorBoard and Weights & Biases integration for experiment tracking."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TensorBoardLogger:
    """TensorBoard logger for experiment tracking."""
    
    def __init__(
        self,
        log_dir: str = "runs",
        experiment_name: str = "experiment",
    ):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.experiment_name = experiment_name
        self.writer = None
        self._setup_tensorboard()
    
    def _setup_tensorboard(self) -> None:
        """Setup TensorBoard writer."""
        try:
            from torch.utils.tensorboard import SummaryWriter
            
            log_path = self.log_dir / self.experiment_name
            self.writer = SummaryWriter(log_path)
            
            logger.info(f"TensorBoard writer setup at {log_path}")
        except ImportError:
            logger.warning("TensorBoard not available (tensorboard not installed)")
    
    def log_scalar(
        self,
        tag: str,
        value: float,
        step: int,
    ) -> None:
        """Log a scalar value."""
        if self.writer:
            self.writer.add_scalar(tag, value, step)
    
    def log_scalars(
        self,
        main_tag: str,
        tag_scalar_dict: dict[str, float],
        step: int,
    ) -> None:
        """Log multiple scalar values."""
        if self.writer:
            self.writer.add_scalars(main_tag, tag_scalar_dict, step)
    
    def log_histogram(
        self,
        tag: str,
        values: torch.Tensor,
        step: int,
    ) -> None:
        """Log histogram of values."""
        if self.writer:
            self.writer.add_histogram(tag, values, step)
    
    def log_model_graph(
        self,
        model: nn.Module,
        inputs: torch.Tensor,
    ) -> None:
        """Log model graph."""
        if self.writer:
            self.writer.add_graph(model, inputs)
    
    def log_images(
        self,
        tag: str,
        images: torch.Tensor,
        step: int,
    ) -> None:
        """Log images."""
        if self.writer:
            self.writer.add_images(tag, images, step)
    
    def log_text(
        self,
        tag: str,
        text: str,
        step: int,
    ) -> None:
        """Log text."""
        if self.writer:
            self.writer.add_text(tag, text, step)
    
    def log_hyperparams(
        self,
        hparam_dict: dict[str, Any],
        metric_dict: dict[str, float],
    ) -> None:
        """Log hyperparameters."""
        if self.writer:
            self.writer.add_hparams(hparam_dict, metric_dict)
    
    def close(self) -> None:
        """Close TensorBoard writer."""
        if self.writer:
            self.writer.close()
            logger.info("TensorBoard writer closed")


class WandBLogger:
    """Weights & Biases logger for experiment tracking."""
    
    def __init__(
        self,
        project: str = "naia-training",
        experiment_name: str = "experiment",
        config: dict[str, Any] | None = None,
    ):
        self.project = project
        self.experiment_name = experiment_name
        self.config = config or {}
        self.run = None
        self._setup_wandb()
    
    def _setup_wandb(self) -> None:
        """Setup Weights & Biases run."""
        try:
            import wandb
            
            self.run = wandb.init(
                project=self.project,
                name=self.experiment_name,
                config=self.config,
            )
            
            logger.info(f"W&B run initialized: {self.experiment_name}")
        except ImportError:
            logger.warning("W&B not available (wandb not installed)")
    
    def log_scalar(
        self,
        key: str,
        value: float,
        step: int,
    ) -> None:
        """Log a scalar value."""
        if self.run:
            self.run.log({key: value}, step=step)
    
    def log_scalars(
        self,
        metrics: dict[str, float],
        step: int,
    ) -> None:
        """Log multiple scalar values."""
        if self.run:
            self.run.log(metrics, step=step)
    
    def log_histogram(
        self,
        key: str,
        values: torch.Tensor,
        step: int,
    ) -> None:
        """Log histogram of values."""
        if self.run:
            self.run.log({key: wandb.Histogram(values)}, step=step)
    
    def log_model(
        self,
        model: nn.Module,
        name: str = "model",
    ) -> None:
        """Log model."""
        if self.run:
            wandb.watch(model, name=name)
    
    def log_artifact(
        self,
        path: str,
        name: str,
        type: str = "model",
    ) -> None:
        """Log artifact."""
        if self.run:
            artifact = wandb.Artifact(name, type=type)
            artifact.add_file(path)
            self.run.log_artifact(artifact)
    
    def log_image(
        self,
        key: str,
        image: torch.Tensor,
        step: int,
    ) -> None:
        """Log image."""
        if self.run:
            self.run.log({key: wandb.Image(image)}, step=step)
    
    def log_text(
        self,
        key: str,
        text: str,
    ) -> None:
        """Log text."""
        if self.run:
            self.run.log({key: text})
    
    def save_config(self) -> None:
        """Save configuration."""
        if self.run:
            wandb.config.update(self.config)
    
    def finish(self) -> None:
        """Finish W&B run."""
        if self.run:
            self.run.finish()
            logger.info("W&B run finished")


class ExperimentTracker:
    """Combined experiment tracker with multiple backends."""
    
    def __init__(
        self,
        experiment_name: str,
        use_tensorboard: bool = True,
        use_wandb: bool = True,
        wandb_project: str = "naia-training",
        config: dict[str, Any] | None = None,
    ):
        self.experiment_name = experiment_name
        self.use_tensorboard = use_tensorboard
        self.use_wandb = use_wandb
        
        # Initialize loggers
        if use_tensorboard:
            self.tb_logger = TensorBoardLogger(experiment_name=experiment_name)
        else:
            self.tb_logger = None
        
        if use_wandb:
            self.wandb_logger = WandBLogger(
                project=wandb_project,
                experiment_name=experiment_name,
                config=config,
            )
        else:
            self.wandb_logger = None
        
        self.metrics_history = {}
    
    def log_metric(
        self,
        name: str,
        value: float,
        step: int,
    ) -> None:
        """Log a metric to all backends."""
        if self.tb_logger:
            self.tb_logger.log_scalar(name, value, step)
        
        if self.wandb_logger:
            self.wandb_logger.log_scalar(name, value, step)
        
        # Store in history
        if name not in self.metrics_history:
            self.metrics_history[name] = []
        self.metrics_history[name].append({"step": step, "value": value})
    
    def log_metrics(
        self,
        metrics: dict[str, float],
        step: int,
    ) -> None:
        """Log multiple metrics."""
        for name, value in metrics.items():
            self.log_metric(name, value, step)
    
    def log_model(
        self,
        model: nn.Module,
        inputs: torch.Tensor,
    ) -> None:
        """Log model to all backends."""
        if self.tb_logger:
            self.tb_logger.log_model_graph(model, inputs)
        
        if self.wandb_logger:
            self.wandb_logger.log_model(model)
    
    def log_histogram(
        self,
        name: str,
        values: torch.Tensor,
        step: int,
    ) -> None:
        """Log histogram to all backends."""
        if self.tb_logger:
            self.tb_logger.log_histogram(name, values, step)
        
        if self.wandb_logger:
            self.wandb_logger.log_histogram(name, values, step)
    
    def log_hyperparams(
        self,
        hyperparams: dict[str, Any],
        metrics: dict[str, float],
    ) -> None:
        """Log hyperparameters."""
        if self.tb_logger:
            self.tb_logger.log_hyperparams(hyperparams, metrics)
        
        if self.wandb_logger:
            self.wandb_logger.log_scalars(metrics, step=0)
    
    def save_checkpoint(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        epoch: int,
        path: str,
    ) -> None:
        """Save checkpoint."""
        checkpoint = {
            "epoch": epoch,
            "model_state_dict": model.state_dict(),
            "optimizer_state_dict": optimizer.state_dict(),
        }
        
        torch.save(checkpoint, path)
        
        # Log as artifact
        if self.wandb_logger:
            self.wandb_logger.log_artifact(path, f"checkpoint_epoch_{epoch}")
        
        logger.info(f"Checkpoint saved to {path}")
    
    def load_checkpoint(
        self,
        path: str,
        model: nn.Module,
        optimizer: torch.optim.Optimizer | None = None,
    ) -> dict[str, Any]:
        """Load checkpoint."""
        checkpoint = torch.load(path)
        
        model.load_state_dict(checkpoint["model_state_dict"])
        
        if optimizer and "optimizer_state_dict" in checkpoint:
            optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
        
        logger.info(f"Checkpoint loaded from {path}")
        
        return checkpoint
    
    def get_metrics_history(
        self,
        metric_name: str,
    ) -> list[dict[str, float]]:
        """Get history for a specific metric."""
        return self.metrics_history.get(metric_name, [])
    
    def close(self) -> None:
        """Close all loggers."""
        if self.tb_logger:
            self.tb_logger.close()
        
        if self.wandb_logger:
            self.wandb_logger.finish()
        
        logger.info("Experiment tracker closed")


class PerformanceProfiler:
    """Performance profiler for tracking training speed."""
    
    def __init__(
        self,
        tracker: ExperimentTracker,
    ):
        self.tracker = tracker
        self.start_times = {}
        self.durations = {}
    
    def start_timer(
        self,
        name: str,
    ) -> None:
        """Start a timer."""
        import time
        self.start_times[name] = time.time()
    
    def end_timer(
        self,
        name: str,
        step: int,
    ) -> float:
        """End a timer and log duration."""
        import time
        
        if name not in self.start_times:
            logger.warning(f"Timer {name} was not started")
            return 0.0
        
        duration = time.time() - self.start_times[name]
        
        self.tracker.log_metric(f"timing/{name}", duration, step)
        
        if name not in self.durations:
            self.durations[name] = []
        self.durations[name].append(duration)
        
        del self.start_times[name]
        
        return duration
    
    def get_average_duration(
        self,
        name: str,
    ) -> float:
        """Get average duration for a timer."""
        if name not in self.durations or not self.durations[name]:
            return 0.0
        
        return sum(self.durations[name]) / len(self.durations[name])


def benchmark_experiment_tracking(
    num_steps: int = 100,
) -> dict[str, Any]:
    """Benchmark experiment tracking backends."""
    logger.info(f"Benchmarking experiment tracking for {num_steps} steps")
    
    import time
    
    results = {}
    
    # No tracking
    start = time.time()
    for i in range(num_steps):
        pass
    no_tracking_time = time.time() - start
    
    results["no_tracking"] = {
        "time_ms": no_tracking_time * 1000,
        "overhead": "0x",
    }
    
    # TensorBoard only
    tracker = ExperimentTracker("test_tb", use_tensorboard=True, use_wandb=False)
    start = time.time()
    for i in range(num_steps):
        tracker.log_metric("loss", 1.0 / (i + 1), i)
    tb_time = time.time() - start
    tracker.close()
    
    results["tensorboard"] = {
        "time_ms": tb_time * 1000,
        "overhead": f"{tb_time / no_tracking_time:.2f}x",
    }
    
    # W&B only
    tracker = ExperimentTracker("test_wandb", use_tensorboard=False, use_wandb=True)
    start = time.time()
    for i in range(num_steps):
        tracker.log_metric("loss", 1.0 / (i + 1), i)
    wandb_time = time.time() - start
    tracker.close()
    
    results["wandb"] = {
        "time_ms": wandb_time * 1000,
        "overhead": f"{wandb_time / no_tracking_time:.2f}x",
    }
    
    # Both
    tracker = ExperimentTracker("test_both", use_tensorboard=True, use_wandb=True)
    start = time.time()
    for i in range(num_steps):
        tracker.log_metric("loss", 1.0 / (i + 1), i)
    both_time = time.time() - start
    tracker.close()
    
    results["both"] = {
        "time_ms": both_time * 1000,
        "overhead": f"{both_time / no_tracking_time:.2f}x",
    }
    
    logger.info("Experiment tracking benchmark complete")
    
    return results


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Benchmark experiment tracking
    results = benchmark_experiment_tracking(
        num_steps=100,
    )
    
    print("\n=== Experiment Tracking Benchmark ===")
    print(json.dumps(results, indent=2))
