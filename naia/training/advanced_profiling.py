"""Advanced profiling tools for training optimization."""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from torch.profiler import profile, record_function, ProfilerActivity

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TrainingProfiler:
    """Comprehensive training profiler."""
    
    def __init__(self, model: nn.Module):
        self.model = model
        self.timings = {}
        self.memory_stats = {}
    
    def profile_forward_pass(
        self,
        inputs: dict[str, torch.Tensor],
        num_iterations: int = 100,
    ) -> dict[str, Any]:
        """Profile forward pass performance."""
        logger.info("Profiling forward pass...")
        
        # Warmup
        with torch.no_grad():
            for _ in range(10):
                _ = self.model(**inputs)
        
        # Profile
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        start_time = time.time()
        
        with torch.no_grad():
            for _ in range(num_iterations):
                _ = self.model(**inputs)
        
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        end_time = time.time()
        
        avg_time = (end_time - start_time) / num_iterations
        throughput = num_iterations / (end_time - start_time)
        
        return {
            "avg_time_ms": avg_time * 1000,
            "throughput_samples_per_sec": throughput,
        }
    
    def profile_backward_pass(
        self,
        inputs: dict[str, torch.Tensor],
        num_iterations: int = 100,
    ) -> dict[str, Any]:
        """Profile backward pass performance."""
        logger.info("Profiling backward pass...")
        
        # Warmup
        for _ in range(10):
            outputs = self.model(**inputs)
            loss = outputs.loss if hasattr(outputs, 'loss') else outputs.logits.sum()
            loss.backward()
            self.model.zero_grad()
        
        # Profile
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        start_time = time.time()
        
        for _ in range(num_iterations):
            outputs = self.model(**inputs)
            loss = outputs.loss if hasattr(outputs, 'loss') else outputs.logits.sum()
            loss.backward()
            self.model.zero_grad()
        
        torch.cuda.synchronize() if torch.cuda.is_available() else None
        end_time = time.time()
        
        avg_time = (end_time - start_time) / num_iterations
        throughput = num_iterations / (end_time - start_time)
        
        return {
            "avg_time_ms": avg_time * 1000,
            "throughput_samples_per_sec": throughput,
        }
    
    def profile_memory_usage(
        self,
        inputs: dict[str, torch.Tensor],
    ) -> dict[str, Any]:
        """Profile memory usage."""
        logger.info("Profiling memory usage...")
        
        if not torch.cuda.is_available():
            return {"error": "CUDA not available"}
        
        torch.cuda.reset_peak_memory_stats()
        torch.cuda.empty_cache()
        
        # Forward pass
        with torch.no_grad():
            outputs = self.model(**inputs)
        
        forward_memory = torch.cuda.max_memory_allocated() / 1024**3
        
        # Backward pass
        outputs = self.model(**inputs)
        loss = outputs.loss if hasattr(outputs, 'loss') else outputs.logits.sum()
        loss.backward()
        
        backward_memory = torch.cuda.max_memory_allocated() / 1024**3
        
        return {
            "forward_memory_gb": forward_memory,
            "backward_memory_gb": backward_memory,
            "peak_memory_gb": backward_memory,
        }
    
    def profile_layer_wise(
        self,
        inputs: dict[str, torch.Tensor],
    ) -> dict[str, Any]:
        """Profile each layer individually."""
        logger.info("Profiling layer-wise performance...")
        
        layer_timings = {}
        
        for name, module in self.model.named_modules():
            if isinstance(module, nn.Linear) or isinstance(module, nn.Conv2d):
                # Warmup
                for _ in range(10):
                    with torch.no_grad():
                        _ = module(inputs.get('input_ids', torch.randn(1, 512)))
                
                # Profile
                torch.cuda.synchronize() if torch.cuda.is_available() else None
                start = time.time()
                
                for _ in range(100):
                    with torch.no_grad():
                        _ = module(inputs.get('input_ids', torch.randn(1, 512)))
                
                torch.cuda.synchronize() if torch.cuda.is_available() else None
                end = time.time()
                
                layer_timings[name] = (end - start) / 100 * 1000  # ms
        
        return layer_timings


class GPUProfiler:
    """GPU-specific profiling."""
    
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    
    def profile_gpu_utilization(self) -> dict[str, Any]:
        """Profile GPU utilization."""
        if not torch.cuda.is_available():
            return {"error": "CUDA not available"}
        
        try:
            import pynvml
            pynvml.nvmlInit()
            
            handle = pynvml.nvmlDeviceGetHandleByIndex(0)
            info = pynvml.nvmlDeviceGetMemoryInfo(handle)
            
            return {
                "total_memory_gb": info.total / 1024**3,
                "free_memory_gb": info.free / 1024**3,
                "used_memory_gb": info.used / 1024**3,
                "utilization_percent": (info.used / info.total) * 100,
            }
        except ImportError:
            return {"error": "pynvml not available"}
    
    def profile_tensor_cores(self) -> dict[str, Any]:
        """Profile Tensor Core utilization."""
        if not torch.cuda.is_available():
            return {"error": "CUDA not available"}
        
        props = torch.cuda.get_device_properties(0)
        
        return {
            "tensor_cores": props.major >= 7,
            "compute_capability": f"{props.major}.{props.minor}",
            "multi_processor_count": props.multi_processor_count,
        }


class DataLoadingProfiler:
    """Data loading profiler."""
    
    def profile_dataloader(
        self,
        dataloader: torch.utils.data.DataLoader,
        num_batches: int = 100,
    ) -> dict[str, Any]:
        """Profile data loading performance."""
        logger.info("Profiling data loading...")
        
        timings = []
        
        for i, batch in enumerate(dataloader):
            if i >= num_batches:
                break
            
            start = time.time()
            # Process batch
            _ = batch
            end = time.time()
            
            timings.append(end - start)
        
        avg_time = sum(timings) / len(timings)
        throughput = 1 / avg_time
        
        return {
            "avg_time_ms": avg_time * 1000,
            "throughput_batches_per_sec": throughput,
        }


class ComprehensiveProfiler:
    """Comprehensive profiler combining all techniques."""
    
    def __init__(self, model: nn.Module):
        self.model = model
        self.training_profiler = TrainingProfiler(model)
        self.gpu_profiler = GPUProfiler()
    
    def profile_all(
        self,
        inputs: dict[str, torch.Tensor],
        dataloader: torch.utils.data.DataLoader | None = None,
    ) -> dict[str, Any]:
        """Run comprehensive profiling."""
        logger.info("Running comprehensive profiling...")
        
        results = {
            "forward_pass": self.training_profiler.profile_forward_pass(inputs),
            "backward_pass": self.training_profiler.profile_backward_pass(inputs),
            "memory": self.training_profiler.profile_memory_usage(inputs),
            "gpu": self.gpu_profiler.profile_gpu_utilization(),
            "tensor_cores": self.gpu_profiler.profile_tensor_cores(),
        }
        
        if dataloader is not None:
            data_loading_profiler = DataLoadingProfiler()
            results["data_loading"] = data_loading_profiler.profile_dataloader(dataloader)
        
        return results
    
    def profile_with_torch_profiler(
        self,
        inputs: dict[str, torch.Tensor],
        output_dir: str = "training/profiler_output",
    ) -> str:
        """Profile with PyTorch profiler."""
        logger.info("Profiling with PyTorch profiler...")
        
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        activities = [ProfilerActivity.CPU]
        if torch.cuda.is_available():
            activities.append(ProfilerActivity.CUDA)
        
        with profile(
            activities=activities,
            record_shapes=True,
            profile_memory=True,
            with_stack=True,
        ) as prof:
            with record_function("model_inference"):
                for _ in range(100):
                    with torch.no_grad():
                        _ = self.model(**inputs)
        
        # Save results
        prof_table = prof.key_averages().table(sort_by="cuda_time_total" if torch.cuda.is_available() else "cpu_time_total")
        prof_output = output_path / "profiler_output.txt"
        with open(prof_output, "w", encoding="utf-8") as f:
            f.write(prof_table)
        
        # Save Chrome trace
        prof_output_chrome = output_path / "profiler_trace.json"
        prof.export_chrome_trace(str(prof_output_chrome))
        
        logger.info(f"Profiler output saved to {output_path}")
        
        return str(output_path)


def optimize_based_on_profile(
    profile_results: dict[str, Any],
) -> dict[str, Any]:
    """Suggest optimizations based on profile results."""
    logger.info("Analyzing profile results for optimization suggestions...")
    
    suggestions = []
    
    # Check memory usage
    memory = profile_results.get("memory", {})
    if "peak_memory_gb" in memory:
        if memory["peak_memory_gb"] > 16:
            suggestions.append({
                "issue": "High memory usage",
                "suggestion": "Enable gradient checkpointing or reduce batch size",
                "priority": "high",
            })
    
    # Check forward pass time
    forward = profile_results.get("forward_pass", {})
    if "avg_time_ms" in forward:
        if forward["avg_time_ms"] > 100:
            suggestions.append({
                "issue": "Slow forward pass",
                "suggestion": "Enable Flash Attention or torch.compile",
                "priority": "high",
            })
    
    # Check GPU utilization
    gpu = profile_results.get("gpu", {})
    if "utilization_percent" in gpu:
        if gpu["utilization_percent"] < 50:
            suggestions.append({
                "issue": "Low GPU utilization",
                "suggestion": "Increase batch size or enable mixed precision",
                "priority": "medium",
            })
    
    # Check Tensor Cores
    tensor_cores = profile_results.get("tensor_cores", {})
    if tensor_cores.get("tensor_cores", False):
        suggestions.append({
            "issue": "Tensor Cores available",
            "suggestion": "Enable TF32 and mixed precision for better performance",
            "priority": "medium",
        })
    
    return {
        "suggestions": suggestions,
        "num_suggestions": len(suggestions),
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Example usage would require a model and inputs
    logger.info("Advanced profiling tools ready")
    logger.info("Use with: profiler = ComprehensiveProfiler(model)")
    logger.info("results = profiler.profile_all(inputs)")
