"""Advanced memory optimization techniques for NAIA training."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

import torch
import torch.nn as nn
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import LoraConfig, get_peft_model
from training.optimized_gpu_config import get_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class MemoryEfficientTrainer:
    """Memory-efficient trainer with advanced optimizations."""
    
    def __init__(self, config: dict[str, Any]):
        self.config = config
        self.model = None
        self.tokenizer = None
    
    def apply_gradient_checkpointing(self, model: nn.Module) -> nn.Module:
        """Apply gradient checkpointing to save memory."""
        if hasattr(model, "gradient_checkpointing_enable"):
            model.gradient_checkpointing_enable()
        return model
    
    def apply_activation_checkpointing(self, model: nn.Module) -> nn.Module:
        """Apply activation checkpointing for deeper models."""
        # For transformer models, checkpoint every few layers
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        return model
    
    def apply_mixed_precision(self, model: nn.Module) -> nn.Module:
        """Apply mixed precision training."""
        if self.config.get("fp16", False):
            model = model.half()
        elif self.config.get("bf16", False):
            model = model.bfloat16()
        return model
    
    def apply_dynamic_quantization(self, model: nn.Module) -> nn.Module:
        """Apply dynamic quantization for inference."""
        quantized_model = torch.quantization.quantize_dynamic(
            model,
            {nn.Linear, nn.Conv2d},
            dtype=torch.qint8,
        )
        return quantized_model
    
    def apply_cpu_offloading(self, model: nn.Module) -> nn.Module:
        """Apply CPU offloading for large models."""
        if hasattr(model, "enable_cpu_offload"):
            model.enable_cpu_offload()
        return model
    
    def optimize_memory_usage(self, model: nn.Module) -> nn.Module:
        """Apply all memory optimizations."""
        logger.info("Applying memory optimizations...")
        
        # Gradient checkpointing
        if self.config.get("gradient_checkpointing", False):
            model = self.apply_gradient_checkpointing(model)
            logger.info("Gradient checkpointing enabled")
        
        # Mixed precision
        if self.config.get("fp16", False) or self.config.get("bf16", False):
            model = self.apply_mixed_precision(model)
            logger.info("Mixed precision enabled")
        
        # CPU offloading if configured
        if self.config.get("cpu_offload", False):
            model = self.apply_cpu_offloading(model)
            logger.info("CPU offloading enabled")
        
        return model
    
    def get_memory_stats(self) -> dict[str, Any]:
        """Get current memory usage statistics."""
        if torch.cuda.is_available():
            allocated = torch.cuda.memory_allocated() / 1024**3
            reserved = torch.cuda.memory_reserved() / 1024**3
            max_allocated = torch.cuda.max_memory_allocated() / 1024**3
            
            return {
                "allocated_gb": allocated,
                "reserved_gb": reserved,
                "max_allocated_gb": max_allocated,
                "device": torch.cuda.get_device_name(0),
            }
        return {"device": "CPU"}


def apply_8bit_quantization(
    model_name: str,
    config: dict[str, Any],
) -> tuple[nn.Module, Any]:
    """Apply 8-bit quantization for memory efficiency."""
    logger.info(f"Applying 8-bit quantization to {model_name}")
    
    from transformers import BitsAndBytesConfig
    
    quantization_config = BitsAndBytesConfig(
        load_in_8bit=True,
        llm_int8_threshold=6.0,
        llm_int8_has_fp16_weight=False,
        llm_int8_fp16_statistics=False,
        llm_int8_enable_fp32_cpu_offload=False,
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map="auto",
        torch_dtype=torch.float16,
    )
    
    return model, quantization_config


def apply_4bit_quantization(
    model_name: str,
    config: dict[str, Any],
) -> tuple[nn.Module, Any]:
    """Apply 4-bit quantization for maximum memory efficiency."""
    logger.info(f"Applying 4-bit quantization to {model_name}")
    
    from transformers import BitsAndBytesConfig
    
    quantization_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=config.get("bnb_4bit_use_double_quant", True),
        bnb_4bit_quant_type=config.get("bnb_4bit_quant_type", "nf4"),
    )
    
    model = AutoModelForCausalLM.from_pretrained(
        model_name,
        quantization_config=quantization_config,
        device_map="auto",
    )
    
    return model, quantization_config


def apply_paged_attention(
    model: nn.Module,
    max_memory: int | None = None,
) -> nn.Module:
    """Apply paged attention for memory efficiency."""
    logger.info("Applying paged attention")
    
    # This requires xformers or similar library
    # Implementation depends on the specific library used
    
    return model


def optimize_for_inference(
    model: nn.Module,
    tokenizer: Any,
) -> tuple[nn.Module, Any]:
    """Optimize model for faster inference."""
    logger.info("Optimizing model for inference")
    
    # Apply optimizations
    model.eval()
    
    # Disable gradients
    for param in model.parameters():
        param.requires_grad = False
    
    # Apply torch.compile if available
    try:
        model = torch.compile(model)
        logger.info("Applied torch.compile")
    except Exception as e:
        logger.warning(f"torch.compile failed: {e}")
    
    return model, tokenizer


def profile_memory_usage(
    model: nn.Module,
    input_text: str,
    tokenizer: Any,
    max_length: int = 1024,
) -> dict[str, Any]:
    """Profile memory usage during inference."""
    logger.info("Profiling memory usage...")
    
    if torch.cuda.is_available():
        torch.cuda.reset_peak_memory_stats()
    
    inputs = tokenizer(input_text, return_tensors="pt", max_length=max_length, truncation=True)
    
    if torch.cuda.is_available():
        inputs = {k: v.cuda() for k, v in inputs.items()}
    
    with torch.no_grad():
        outputs = model(**inputs)
    
    memory_stats = {}
    
    if torch.cuda.is_available():
        memory_stats = {
            "peak_memory_gb": torch.cuda.max_memory_allocated() / 1024**3,
            "current_memory_gb": torch.cuda.memory_allocated() / 1024**3,
            "reserved_memory_gb": torch.cuda.memory_reserved() / 1024**3,
        }
    
    logger.info(f"Memory stats: {memory_stats}")
    
    return memory_stats


def create_memory_optimized_training_config(
    base_config: dict[str, Any],
    available_memory_gb: float,
) -> dict[str, Any]:
    """Create memory-optimized training configuration based on available memory."""
    logger.info(f"Creating memory-optimized config for {available_memory_gb} GB")
    
    optimized_config = base_config.copy()
    
    # Adjust batch size based on available memory
    if available_memory_gb < 8:
        optimized_config["batch_size"] = 4
        optimized_config["gradient_accumulation_steps"] = 4
    elif available_memory_gb < 16:
        optimized_config["batch_size"] = 8
        optimized_config["gradient_accumulation_steps"] = 2
    else:
        optimized_config["batch_size"] = 16
        optimized_config["gradient_accumulation_steps"] = 1
    
    # Enable gradient checkpointing for low memory
    if available_memory_gb < 16:
        optimized_config["gradient_checkpointing"] = True
    
    # Use quantization for very low memory
    if available_memory_gb < 8:
        optimized_config["load_in_8bit"] = True
    
    logger.info(f"Optimized config: batch_size={optimized_config['batch_size']}, "
                f"grad_accum={optimized_config['gradient_accumulation_steps']}")
    
    return optimized_config


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    
    # Example usage
    config = get_config("optimized")
    
    if torch.cuda.is_available():
        available_memory = torch.cuda.get_device_properties(0).total_memory / 1024**3
        logger.info(f"Available GPU memory: {available_memory:.2f} GB")
        
        optimized_config = create_memory_optimized_training_config(config, available_memory)
        
        print("\n=== Memory-Optimized Configuration ===")
        print(json.dumps(optimized_config, indent=2))
    else:
        logger.warning("CUDA not available, using CPU")
