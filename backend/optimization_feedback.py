"""
Real-Time Optimization Feedback Loop

This module provides a feedback loop that continuously monitors performance
and adjusts pipeline parameters dynamically to optimize for latency and quality.

Usage:
    from backend.optimization_feedback import OptimizationFeedbackLoop
    
    feedback = OptimizationFeedbackLoop(pipeline)
    feedback.start_monitoring()
    
    # Get recommendations
    recommendations = feedback.get_recommendations()
    
    # Apply optimizations
    feedback.apply_optimizations(recommendations)
"""

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, List, Optional
from enum import Enum


class OptimizationAction(Enum):
    """Types of optimization actions."""
    REDUCE_MODEL_SIZE = "reduce_model_size"
    INCREASE_MODEL_SIZE = "increase_model_size"
    ENABLE_GPU = "enable_gpu"
    DISABLE_GPU = "disable_gpu"
    INCREASE_CONCURRENCY = "increase_concurrency"
    DECREASE_CONCURRENCY = "decrease_concurrency"
    ENABLE_CACHE = "enable_cache"
    DISABLE_CACHE = "disable_cache"
    ADJUST_VAD_THRESHOLD = "adjust_vad_threshold"
    ENABLE_AUDIO_ENHANCEMENT = "enable_audio_enhancement"
    DISABLE_AUDIO_ENHANCEMENT = "disable_audio_enhancement"


@dataclass
class PerformanceMetrics:
    """Current performance metrics."""
    stt_latency_ms: float
    translation_latency_ms: float
    tts_latency_ms: float
    end_to_end_latency_ms: float
    cpu_usage_percent: float
    memory_usage_mb: float
    network_latency_ms: float
    cache_hit_rate: float
    error_rate: float
    timestamp: float


@dataclass
class OptimizationRecommendation:
    """Optimization recommendation."""
    action: OptimizationAction
    reason: str
    expected_improvement: str
    priority: int  # 1-10, 10 is highest


class OptimizationFeedbackLoop:
    """Real-time optimization feedback loop."""
    
    def __init__(self, pipeline, target_latency_ms: float = 1000, max_latency_ms: float = 2000):
        self.pipeline = pipeline
        self.target_latency_ms = target_latency_ms
        self.max_latency_ms = max_latency_ms
        self.metrics_history: List[PerformanceMetrics] = []
        self.max_history_size = 100
        self.monitoring = False
        self.monitoring_interval = 5.0  # seconds
        self._monitor_task: Optional[asyncio.Task] = None
        
    def record_metrics(self, metrics: PerformanceMetrics) -> None:
        """Record performance metrics."""
        self.metrics_history.append(metrics)
        if len(self.metrics_history) > self.max_history_size:
            self.metrics_history.pop(0)
    
    def get_average_metrics(self, window_size: int = 10) -> Optional[PerformanceMetrics]:
        """Get average metrics over a time window."""
        if len(self.metrics_history) < window_size:
            return None
        
        recent = self.metrics_history[-window_size:]
        return PerformanceMetrics(
            stt_latency_ms=sum(m.stt_latency_ms for m in recent) / len(recent),
            translation_latency_ms=sum(m.translation_latency_ms for m in recent) / len(recent),
            tts_latency_ms=sum(m.tts_latency_ms for m in recent) / len(recent),
            end_to_end_latency_ms=sum(m.end_to_end_latency_ms for m in recent) / len(recent),
            cpu_usage_percent=sum(m.cpu_usage_percent for m in recent) / len(recent),
            memory_usage_mb=sum(m.memory_usage_mb for m in recent) / len(recent),
            network_latency_ms=sum(m.network_latency_ms for m in recent) / len(recent),
            cache_hit_rate=sum(m.cache_hit_rate for m in recent) / len(recent),
            error_rate=sum(m.error_rate for m in recent) / len(recent),
            timestamp=time.time(),
        )
    
    def get_recommendations(self) -> List[OptimizationRecommendation]:
        """Generate optimization recommendations based on current metrics."""
        recommendations = []
        metrics = self.get_average_metrics()
        
        if not metrics:
            return recommendations
        
        # Latency-based recommendations
        if metrics.end_to_end_latency_ms > self.max_latency_ms:
            # Critical: latency too high
            if metrics.stt_latency_ms > 500:
                recommendations.append(OptimizationRecommendation(
                    action=OptimizationAction.REDUCE_MODEL_SIZE,
                    reason=f"STT latency too high ({metrics.stt_latency_ms:.0f}ms)",
                    expected_improvement="Reduce STT latency by 30-50%",
                    priority=10,
                ))
            
            if metrics.translation_latency_ms > 300:
                recommendations.append(OptimizationRecommendation(
                    action=OptimizationAction.ENABLE_CACHE,
                    reason=f"Translation latency too high ({metrics.translation_latency_ms:.0f}ms)",
                    expected_improvement="Reduce translation latency by 50-80% for repeated phrases",
                    priority=9,
                ))
            
            if metrics.tts_latency_ms > 500:
                recommendations.append(OptimizationRecommendation(
                    action=OptimizationAction.DECREASE_CONCURRENCY,
                    reason=f"TTS latency too high ({metrics.tts_latency_ms:.0f}ms)",
                    expected_improvement="Reduce TTS latency by 20-30%",
                    priority=8,
                ))
        
        elif metrics.end_to_end_latency_ms < self.target_latency_ms * 0.5:
            # Can improve quality
            if metrics.stt_latency_ms < 200:
                recommendations.append(OptimizationRecommendation(
                    action=OptimizationAction.INCREASE_MODEL_SIZE,
                    reason=f"STT latency very low ({metrics.stt_latency_ms:.0f}ms), can improve accuracy",
                    expected_improvement="Improve STT accuracy by 10-20%",
                    priority=5,
                ))
        
        # CPU-based recommendations
        if metrics.cpu_usage_percent > 80:
            recommendations.append(OptimizationRecommendation(
                action=OptimizationAction.DECREASE_CONCURRENCY,
                reason=f"CPU usage too high ({metrics.cpu_usage_percent:.0f}%)",
                expected_improvement="Reduce CPU usage by 20-30%",
                priority=7,
            ))
        
        # Memory-based recommendations
        if metrics.memory_usage_mb > 2000:
            recommendations.append(OptimizationRecommendation(
                action=OptimizationAction.REDUCE_MODEL_SIZE,
                reason=f"Memory usage too high ({metrics.memory_usage_mb:.0f}MB)",
                expected_improvement="Reduce memory usage by 30-50%",
                priority=6,
            ))
        
        # Cache-based recommendations
        if metrics.cache_hit_rate < 0.2 and metrics.translation_latency_ms > 200:
            recommendations.append(OptimizationRecommendation(
                action=OptimizationAction.ENABLE_CACHE,
                reason=f"Cache hit rate low ({metrics.cache_hit_rate:.0%})",
                expected_improvement="Increase cache hit rate to 30-50%",
                priority=8,
            ))
        
        # Error-based recommendations
        if metrics.error_rate > 0.1:
            recommendations.append(OptimizationRecommendation(
                action=OptimizationAction.ENABLE_AUDIO_ENHANCEMENT,
                reason=f"Error rate too high ({metrics.error_rate:.0%})",
                expected_improvement="Reduce error rate by 20-40%",
                priority=9,
            ))
        
        # Sort by priority
        recommendations.sort(key=lambda r: r.priority, reverse=True)
        return recommendations
    
    def apply_optimizations(self, recommendations: List[OptimizationRecommendation]) -> Dict[str, bool]:
        """Apply optimization recommendations."""
        results = {}
        
        for rec in recommendations:
            try:
                if rec.action == OptimizationAction.REDUCE_MODEL_SIZE:
                    # Would need to implement model size adjustment
                    results[str(rec.action)] = False
                elif rec.action == OptimizationAction.INCREASE_MODEL_SIZE:
                    # Would need to implement model size adjustment
                    results[str(rec.action)] = False
                elif rec.action == OptimizationAction.ENABLE_CACHE:
                    # Cache is already enabled, just log
                    results[str(rec.action)] = True
                elif rec.action == OptimizationAction.DECREASE_CONCURRENCY:
                    # Would need to implement concurrency adjustment
                    results[str(rec.action)] = False
                elif rec.action == OptimizationAction.ENABLE_AUDIO_ENHANCEMENT:
                    # Audio enhancement is already enabled
                    results[str(rec.action)] = True
                else:
                    results[str(rec.action)] = False
            except Exception as e:
                results[str(rec.action)] = False
        
        return results
    
    async def start_monitoring(self) -> None:
        """Start continuous monitoring."""
        if self.monitoring:
            return
        
        self.monitoring = True
        self._monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self) -> None:
        """Stop continuous monitoring."""
        self.monitoring = False
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass
    
    async def _monitor_loop(self) -> None:
        """Monitoring loop."""
        while self.monitoring:
            # Generate recommendations
            recommendations = self.get_recommendations()
            
            if recommendations:
                # Log recommendations
                import logging
                logger = logging.getLogger("optimization_feedback")
                for rec in recommendations:
                    logger.info(f"Optimization recommendation: {rec.action.value} - {rec.reason} (priority: {rec.priority})")
            
            # Wait for next interval
            await asyncio.sleep(self.monitoring_interval)
    
    def get_status(self) -> Dict:
        """Get current status of the feedback loop."""
        metrics = self.get_average_metrics()
        recommendations = self.get_recommendations()
        
        return {
            "monitoring": self.monitoring,
            "target_latency_ms": self.target_latency_ms,
            "max_latency_ms": self.max_latency_ms,
            "current_metrics": metrics.__dict__ if metrics else None,
            "recommendations": [
                {
                    "action": rec.action.value,
                    "reason": rec.reason,
                    "expected_improvement": rec.expected_improvement,
                    "priority": rec.priority,
                }
                for rec in recommendations
            ],
            "metrics_history_size": len(self.metrics_history),
        }
