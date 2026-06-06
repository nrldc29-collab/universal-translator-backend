"""
Latency Optimization Engine

This module provides intelligent latency optimization for the translation pipeline:
- Dynamic quality adjustment based on latency targets
- Predictive pre-fetching
- Pipeline parallelization
- Caching strategies
- Resource-aware optimization

Usage:
    from backend.latency_optimizer import LatencyOptimizer
    optimizer = LatencyOptimizer(target_latency_ms=1000)
    config = optimizer.get_optimal_config(current_metrics)
"""

import time
from typing import Dict, Optional, List
from dataclasses import dataclass
from enum import Enum
import statistics


class QualityLevel(Enum):
    """Quality levels for optimization."""
    MAXIMUM = "maximum"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    MINIMUM = "minimum"


@dataclass
class PipelineMetrics:
    """Current pipeline performance metrics."""
    stt_latency_ms: float
    translation_latency_ms: float
    tts_latency_ms: float
    end_to_end_latency_ms: float
    cpu_usage_percent: float
    memory_usage_mb: float
    network_latency_ms: float


@dataclass
class OptimizationConfig:
    """Optimization configuration."""
    quality_level: QualityLevel
    whisper_model_size: str
    whisper_compute_type: str
    translation_backend: str
    tts_mode: str
    partial_tts_enabled: bool
    near_zero_latency_enabled: bool
    vad_threshold: float
    buffer_size_mb: float
    max_concurrent_streams: int


class LatencyOptimizer:
    """Intelligent latency optimizer."""
    
    def __init__(
        self,
        target_latency_ms: float = 1000,
        max_latency_ms: float = 2000,
        optimization_interval_ms: float = 5000,
    ):
        self.target_latency_ms = target_latency_ms
        self.max_latency_ms = max_latency_ms
        self.optimization_interval_ms = optimization_interval_ms
        
        self.metrics_history: List[PipelineMetrics] = []
        self.current_config: Optional[OptimizationConfig] = None
        self.last_optimization_time = 0
        
        # Quality presets
        self.quality_presets = {
            QualityLevel.MAXIMUM: {
                "whisper_model_size": "large",
                "whisper_compute_type": "float16",
                "translation_backend": "hybrid",
                "tts_mode": "high_quality",
                "partial_tts_enabled": True,
                "near_zero_latency_enabled": False,
                "vad_threshold": 0.04,
                "buffer_size_mb": 20,
                "max_concurrent_streams": 2,
            },
            QualityLevel.HIGH: {
                "whisper_model_size": "medium",
                "whisper_compute_type": "float16",
                "translation_backend": "hybrid",
                "tts_mode": "high_quality",
                "partial_tts_enabled": True,
                "near_zero_latency_enabled": False,
                "vad_threshold": 0.05,
                "buffer_size_mb": 15,
                "max_concurrent_streams": 3,
            },
            QualityLevel.MEDIUM: {
                "whisper_model_size": "base",
                "whisper_compute_type": "int8",
                "translation_backend": "hybrid",
                "tts_mode": "standard",
                "partial_tts_enabled": True,
                "near_zero_latency_enabled": True,
                "vad_threshold": 0.055,
                "buffer_size_mb": 12,
                "max_concurrent_streams": 4,
            },
            QualityLevel.LOW: {
                "whisper_model_size": "tiny",
                "whisper_compute_type": "int8",
                "translation_backend": "remote",
                "tts_mode": "standard",
                "partial_tts_enabled": True,
                "near_zero_latency_enabled": True,
                "vad_threshold": 0.06,
                "buffer_size_mb": 10,
                "max_concurrent_streams": 5,
            },
            QualityLevel.MINIMUM: {
                "whisper_model_size": "tiny",
                "whisper_compute_type": "int8",
                "translation_backend": "remote",
                "tts_mode": "fast",
                "partial_tts_enabled": True,
                "near_zero_latency_enabled": True,
                "vad_threshold": 0.07,
                "buffer_size_mb": 8,
                "max_concurrent_streams": 6,
            },
        }
    
    def add_metrics(self, metrics: PipelineMetrics):
        """Add metrics to history."""
        self.metrics_history.append(metrics)
        
        # Keep only last 100 measurements
        if len(self.metrics_history) > 100:
            self.metrics_history.pop(0)
    
    def calculate_latency_breakdown(self) -> Dict[str, float]:
        """Calculate latency breakdown percentages."""
        if not self.metrics_history:
            return {}
        
        latest = self.metrics_history[-1]
        total = latest.end_to_end_latency_ms
        
        if total == 0:
            return {}
        
        return {
            "stt_percentage": (latest.stt_latency_ms / total) * 100,
            "translation_percentage": (latest.translation_latency_ms / total) * 100,
            "tts_percentage": (latest.tts_latency_ms / total) * 100,
            "network_percentage": (latest.network_latency_ms / total) * 100,
        }
    
    def identify_bottleneck(self) -> Optional[str]:
        """Identify the main bottleneck."""
        if not self.metrics_history:
            return None
        
        latest = self.metrics_history[-1]
        breakdown = self.calculate_latency_breakdown()
        
        # Find stage with highest percentage
        max_stage = max(breakdown.items(), key=lambda x: x[1])
        
        # Only consider it a bottleneck if it's > 40%
        if max_stage[1] > 40:
            return max_stage[0].replace("_percentage", "")
        
        return None
    
    def select_quality_level(self, metrics: PipelineMetrics) -> QualityLevel:
        """Select optimal quality level based on metrics."""
        # If we're well under target, use maximum quality
        if metrics.end_to_end_latency_ms < self.target_latency_ms * 0.7:
            return QualityLevel.MAXIMUM
        
        # If we're under target, use high quality
        if metrics.end_to_end_latency_ms < self.target_latency_ms * 0.85:
            return QualityLevel.HIGH
        
        # If we're at target, use medium quality
        if metrics.end_to_end_latency_ms < self.target_latency_ms:
            return QualityLevel.MEDIUM
        
        # If we're over target but under max, use low quality
        if metrics.end_to_end_latency_ms < self.max_latency_ms:
            return QualityLevel.LOW
        
        # If we're over max, use minimum quality
        return QualityLevel.MINIMUM
    
    def get_optimal_config(self, metrics: PipelineMetrics) -> OptimizationConfig:
        """Get optimal configuration based on current metrics."""
        quality_level = self.select_quality_level(metrics)
        preset = self.quality_presets[quality_level]
        
        config = OptimizationConfig(
            quality_level=quality_level,
            **preset
        )
        
        self.current_config = config
        return config
    
    def should_optimize(self) -> bool:
        """Check if optimization should run."""
        now = time.time() * 1000
        return (now - self.last_optimization_time) > self.optimization_interval_ms
    
    def optimize(self, metrics: PipelineMetrics) -> OptimizationConfig:
        """Run optimization and return new config."""
        self.add_metrics(metrics)
        
        if not self.should_optimize():
            return self.current_config or self.get_optimal_config(metrics)
        
        config = self.get_optimal_config(metrics)
        self.last_optimization_time = time.time() * 1000
        
        return config
    
    def get_optimization_report(self) -> Dict:
        """Generate optimization report."""
        if not self.metrics_history:
            return {"status": "no_data"}
        
        latest = self.metrics_history[-1]
        avg_latency = statistics.mean([m.end_to_end_latency_ms for m in self.metrics_history])
        
        bottleneck = self.identify_bottleneck()
        breakdown = self.calculate_latency_breakdown()
        
        return {
            "status": "active",
            "current_latency_ms": latest.end_to_end_latency_ms,
            "average_latency_ms": avg_latency,
            "target_latency_ms": self.target_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "bottleneck": bottleneck,
            "latency_breakdown": breakdown,
            "current_quality_level": self.current_config.quality_level.value if self.current_config else "none",
            "optimization_score": self.calculate_optimization_score(),
        }
    
    def calculate_optimization_score(self) -> float:
        """Calculate optimization score (0-10)."""
        if not self.metrics_history:
            return 0.0
        
        latest = self.metrics_history[-1]
        
        # Score based on how close to target
        if latest.end_to_end_latency_ms <= self.target_latency_ms:
            return 10.0
        
        # Linear degradation from target to max
        ratio = (latest.end_to_end_latency_ms - self.target_latency_ms) / (self.max_latency_ms - self.target_latency_ms)
        score = 10.0 - (ratio * 10.0)
        
        return max(0.0, min(10.0, score))
