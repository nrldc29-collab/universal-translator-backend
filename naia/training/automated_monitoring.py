"""Automated monitoring and alerting for training optimization."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrainingMonitor:
    """Monitor training metrics and performance."""
    
    def __init__(self, log_dir: str = "training/logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.metrics = {}
        self.start_time = time.time()
    
    def log_metric(
        self,
        name: str,
        value: float,
        step: int,
    ) -> None:
        """Log a training metric."""
        if name not in self.metrics:
            self.metrics[name] = []
        
        self.metrics[name].append({
            "step": step,
            "value": value,
            "timestamp": time.time() - self.start_time,
        })
    
    def log_batch_metrics(
        self,
        loss: float,
        learning_rate: float,
        step: int,
    ) -> None:
        """Log batch-level metrics."""
        self.log_metric("loss", loss, step)
        self.log_metric("learning_rate", learning_rate, step)
    
    def log_epoch_metrics(
        self,
        epoch_loss: float,
        epoch_accuracy: float,
        epoch: int,
    ) -> None:
        """Log epoch-level metrics."""
        self.log_metric("epoch_loss", epoch_loss, epoch)
        self.log_metric("epoch_accuracy", epoch_accuracy, epoch)
    
    def get_metrics(
        self,
        metric_name: str,
    ) -> list[dict[str, Any]]:
        """Get metrics for a specific name."""
        return self.metrics.get(metric_name, [])
    
    def save_metrics(self) -> None:
        """Save metrics to file."""
        metrics_file = self.log_dir / "metrics.json"
        with open(metrics_file, "w", encoding="utf-8") as f:
            json.dump(self.metrics, f, indent=2)
        
        logger.info(f"Metrics saved to {metrics_file}")


class PerformanceMonitor:
    """Monitor system performance during training."""
    
    def __init__(self):
        self.gpu_stats = []
        self.cpu_stats = []
        self.memory_stats = []
    
    def log_gpu_stats(self) -> dict[str, Any]:
        """Log GPU statistics."""
        if not torch.cuda.is_available():
            return {"gpu_available": False}
        
        stats = {
            "gpu_available": True,
            "memory_allocated_gb": torch.cuda.memory_allocated() / 1024**3,
            "memory_reserved_gb": torch.cuda.memory_reserved() / 1024**3,
            "memory_free_gb": (torch.cuda.get_device_properties(0).total_memory - torch.cuda.memory_allocated()) / 1024**3,
            "utilization_percent": (torch.cuda.memory_allocated() / torch.cuda.get_device_properties(0).total_memory) * 100,
        }
        
        self.gpu_stats.append(stats)
        return stats
    
    def log_cpu_stats(self) -> dict[str, Any]:
        """Log CPU statistics."""
        import psutil
        
        stats = {
            "cpu_percent": psutil.cpu_percent(),
            "memory_percent": psutil.virtual_memory().percent,
            "memory_available_gb": psutil.virtual_memory().available / 1024**3,
        }
        
        self.cpu_stats.append(stats)
        return stats
    
    def get_average_gpu_memory(self) -> float:
        """Get average GPU memory usage."""
        if not self.gpu_stats:
            return 0.0
        
        total = sum(stat["memory_allocated_gb"] for stat in self.gpu_stats)
        return total / len(self.gpu_stats)


class AlertManager:
    """Manage alerts and notifications."""
    
    def __init__(
        self,
        alert_config: dict[str, Any] | None = None,
    ):
        self.alert_config = alert_config or self._default_alert_config()
        self.active_alerts = []
    
    def _default_alert_config(self) -> dict[str, Any]:
        """Default alert configuration."""
        return {
            "high_loss_threshold": 5.0,
            "low_accuracy_threshold": 0.5,
            "high_memory_threshold": 0.9,
            "slow_iteration_threshold": 10.0,
        }
    
    def check_loss_alert(
        self,
        loss: float,
    ) -> bool:
        """Check if loss exceeds threshold."""
        if loss > self.alert_config["high_loss_threshold"]:
            self.active_alerts.append({
                "type": "high_loss",
                "value": loss,
                "threshold": self.alert_config["high_loss_threshold"],
                "timestamp": time.time(),
            })
            return True
        return False
    
    def check_accuracy_alert(
        self,
        accuracy: float,
    ) -> bool:
        """Check if accuracy falls below threshold."""
        if accuracy < self.alert_config["low_accuracy_threshold"]:
            self.active_alerts.append({
                "type": "low_accuracy",
                "value": accuracy,
                "threshold": self.alert_config["low_accuracy_threshold"],
                "timestamp": time.time(),
            })
            return True
        return False
    
    def check_memory_alert(
        self,
        memory_usage: float,
    ) -> bool:
        """Check if memory usage exceeds threshold."""
        if memory_usage > self.alert_config["high_memory_threshold"]:
            self.active_alerts.append({
                "type": "high_memory",
                "value": memory_usage,
                "threshold": self.alert_config["high_memory_threshold"],
                "timestamp": time.time(),
            })
            return True
        return False
    
    def check_iteration_time_alert(
        self,
        iteration_time: float,
    ) -> bool:
        """Check if iteration is too slow."""
        if iteration_time > self.alert_config["slow_iteration_threshold"]:
            self.active_alerts.append({
                "type": "slow_iteration",
                "value": iteration_time,
                "threshold": self.alert_config["slow_iteration_threshold"],
                "timestamp": time.time(),
            })
            return True
        return False
    
    def get_active_alerts(self) -> list[dict[str, Any]]:
        """Get active alerts."""
        return self.active_alerts
    
    def clear_alerts(self) -> None:
        """Clear all alerts."""
        self.active_alerts = []


class AutoTuner:
    """Automatically tune hyperparameters based on monitoring."""
    
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
    ):
        self.model = model
        self.optimizer = optimizer
        self.tuning_history = []
    
    def auto_tune_learning_rate(
        self,
        loss_history: list[float],
        current_lr: float,
    ) -> float:
        """Automatically adjust learning rate based on loss."""
        if len(loss_history) < 10:
            return current_lr
        
        recent_losses = loss_history[-10:]
        avg_loss = sum(recent_losses) / len(recent_losses)
        prev_avg_loss = sum(loss_history[-20:-10]) / 10 if len(loss_history) >= 20 else avg_loss
        
        # If loss is increasing, decrease learning rate
        if avg_loss > prev_avg_loss * 1.1:
            new_lr = current_lr * 0.5
            logger.info(f"Decreasing learning rate: {current_lr} -> {new_lr}")
            
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = new_lr
            
            self.tuning_history.append({
                "type": "lr_decrease",
                "old_lr": current_lr,
                "new_lr": new_lr,
                "reason": "loss_increasing",
            })
            
            return new_lr
        
        # If loss is plateauing, increase learning rate
        elif abs(avg_loss - prev_avg_loss) < 0.01 * avg_loss:
            new_lr = current_lr * 1.1
            logger.info(f"Increasing learning rate: {current_lr} -> {new_lr}")
            
            for param_group in self.optimizer.param_groups:
                param_group['lr'] = new_lr
            
            self.tuning_history.append({
                "type": "lr_increase",
                "old_lr": current_lr,
                "new_lr": new_lr,
                "reason": "loss_plateau",
            })
            
            return new_lr
        
        return current_lr
    
    def auto_tune_batch_size(
        self,
        memory_usage: float,
        current_batch_size: int,
    ) -> int:
        """Automatically adjust batch size based on memory."""
        if memory_usage > 0.9:
            new_batch_size = max(current_batch_size // 2, 1)
            logger.info(f"Decreasing batch size: {current_batch_size} -> {new_batch_size}")
            return new_batch_size
        elif memory_usage < 0.7:
            new_batch_size = current_batch_size * 2
            logger.info(f"Increasing batch size: {current_batch_size} -> {new_batch_size}")
            return new_batch_size
        
        return current_batch_size


class EarlyStoppingMonitor:
    """Monitor for early stopping."""
    
    def __init__(
        self,
        patience: int = 5,
        min_delta: float = 0.001,
    ):
        self.patience = patience
        self.min_delta = min_delta
        self.best_loss = float('inf')
        self.counter = 0
        self.should_stop = False
    
    def check_early_stopping(
        self,
        current_loss: float,
    ) -> bool:
        """Check if training should stop early."""
        if current_loss < self.best_loss - self.min_delta:
            self.best_loss = current_loss
            self.counter = 0
        else:
            self.counter += 1
        
        if self.counter >= self.patience:
            self.should_stop = True
            logger.info(f"Early stopping triggered after {self.patience} epochs without improvement")
            return True
        
        return False


class GradientMonitor:
    """Monitor gradients during training."""
    
    def __init__(self, model: nn.Module):
        self.model = model
        self.gradient_stats = []
    
    def log_gradient_stats(self) -> dict[str, Any]:
        """Log gradient statistics."""
        total_norm = 0.0
        param_count = 0
        zero_grad_count = 0
        nan_grad_count = 0
        inf_grad_count = 0
        
        for param in self.model.parameters():
            if param.grad is not None:
                param_norm = param.grad.data.norm(2)
                total_norm += param_norm.item() ** 2
                param_count += 1
                
                # Check for zero gradients
                if param.grad.data.abs().sum() == 0:
                    zero_grad_count += 1
                
                # Check for NaN/Inf gradients
                if torch.isnan(param.grad.data).any():
                    nan_grad_count += 1
                if torch.isinf(param.grad.data).any():
                    inf_grad_count += 1
        
        total_norm = total_norm ** 0.5
        
        stats = {
            "gradient_norm": total_norm,
            "param_count": param_count,
            "zero_grad_count": zero_grad_count,
            "nan_grad_count": nan_grad_count,
            "inf_grad_count": inf_grad_count,
        }
        
        self.gradient_stats.append(stats)
        return stats
    
    def check_gradient_issues(self) -> list[str]:
        """Check for gradient issues."""
        issues = []
        
        if not self.gradient_stats:
            return issues
        
        latest = self.gradient_stats[-1]
        
        if latest["nan_grad_count"] > 0:
            issues.append("NaN gradients detected")
        
        if latest["inf_grad_count"] > 0:
            issues.append("Inf gradients detected")
        
        if latest["gradient_norm"] > 1000:
            issues.append("Gradient explosion detected")
        
        if latest["gradient_norm"] < 1e-7:
            issues.append("Gradient vanishing detected")
        
        return issues


class ComprehensiveMonitoringSystem:
    """Comprehensive monitoring system combining all monitors."""
    
    def __init__(
        self,
        model: nn.Module,
        optimizer: torch.optim.Optimizer,
        log_dir: str = "training/logs",
    ):
        self.model = model
        self.optimizer = optimizer
        self.training_monitor = TrainingMonitor(log_dir)
        self.performance_monitor = PerformanceMonitor()
        self.alert_manager = AlertManager()
        self.auto_tuner = AutoTuner(model, optimizer)
        self.early_stopping = EarlyStoppingMonitor(patience=5)
        self.gradient_monitor = GradientMonitor(model)
    
    def monitor_training_step(
        self,
        loss: float,
        step: int,
        learning_rate: float,
    ) -> dict[str, Any]:
        """Monitor a single training step."""
        # Log metrics
        self.training_monitor.log_batch_metrics(loss, learning_rate, step)
        
        # Log performance
        gpu_stats = self.performance_monitor.log_gpu_stats()
        cpu_stats = self.performance_monitor.log_cpu_stats()
        
        # Check alerts
        self.alert_manager.check_loss_alert(loss)
        self.alert_manager.check_memory_alert(gpu_stats.get("utilization_percent", 0) / 100)
        
        # Log gradient stats
        grad_stats = self.gradient_monitor.log_gradient_stats()
        grad_issues = self.gradient_monitor.check_gradient_issues()
        
        # Auto-tune
        loss_history = [m["value"] for m in self.training_monitor.get_metrics("loss")]
        new_lr = self.auto_tuner.auto_tune_learning_rate(loss_history, learning_rate)
        
        return {
            "loss": loss,
            "learning_rate": new_lr,
            "gpu_stats": gpu_stats,
            "cpu_stats": cpu_stats,
            "gradient_stats": grad_stats,
            "gradient_issues": grad_issues,
            "alerts": self.alert_manager.get_active_alerts(),
        }
    
    def monitor_training_epoch(
        self,
        epoch_loss: float,
        epoch_accuracy: float,
        epoch: int,
    ) -> dict[str, Any]:
        """Monitor a training epoch."""
        # Log epoch metrics
        self.training_monitor.log_epoch_metrics(epoch_loss, epoch_accuracy, epoch)
        
        # Check early stopping
        should_stop = self.early_stopping.check_early_stopping(epoch_loss)
        
        # Check accuracy alert
        self.alert_manager.check_accuracy_alert(epoch_accuracy)
        
        # Save metrics
        self.training_monitor.save_metrics()
        
        return {
            "epoch": epoch,
            "epoch_loss": epoch_loss,
            "epoch_accuracy": epoch_accuracy,
            "should_stop": should_stop,
            "alerts": self.alert_manager.get_active_alerts(),
        }


def run_monitoring_demo() -> dict[str, Any]:
    """Run a demo of the monitoring system."""
    logger.info("Running monitoring system demo")
    
    # Create a simple model
    model = nn.Linear(10, 10)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    
    # Create monitoring system
    monitoring_system = ComprehensiveMonitoringSystem(model, optimizer)
    
    # Simulate training steps
    for step in range(100):
        loss = 1.0 / (step + 1) + 0.1 * torch.randn(1).item()
        step_info = monitoring_system.monitor_training_step(
            loss.item(),
            step,
            1e-3,
        )
    
    # Simulate epoch
    epoch_info = monitoring_system.monitor_training_epoch(0.5, 0.8, 1)
    
    result = {
        "total_steps": 100,
        "final_loss": loss.item(),
        "epoch_info": epoch_info,
        "metrics": monitoring_system.training_monitor.metrics,
    }
    
    logger.info("Monitoring system demo complete")
    
    return result


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Run monitoring demo
    result = run_monitoring_demo()
    
    print("\n=== Monitoring System Demo Results ===")
    print(json.dumps(result, indent=2))
