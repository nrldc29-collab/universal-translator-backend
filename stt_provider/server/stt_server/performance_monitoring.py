"""
Performance monitoring for backend services.

This module provides performance monitoring capabilities for backend services,
tracking request latency, success/failure rates, and error information. It
supports calculating percentile-based statistics (p50, p95, p99) and detecting
backend degradation based on configurable thresholds.

Classes:
    PerformanceMetric: Data class representing a single performance metric sample.
    BackendPerformanceStats: Data class for aggregated backend performance statistics.
    PerformanceMonitor: Main class for monitoring and analyzing backend performance.

Functions:
    get_performance_monitor: Get the global performance monitor instance.
    record_backend_call: Record a backend call for performance monitoring.

Usage:
    Use PerformanceMonitor to track backend call performance and detect degradation.
    Use the global monitor instance via get_performance_monitor() for application-wide monitoring.
"""
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """
    Single performance metric sample.
    
    Represents a single measurement of backend performance including timestamp,
    duration, success status, and optional error information.
    
    Attributes:
        timestamp: Unix timestamp when the metric was recorded.
        duration_ms: Request duration in milliseconds.
        success: Whether the request was successful.
        backend: Name of the backend that handled the request.
        error: Optional error message if the request failed.
    """
    timestamp: float
    duration_ms: float
    success: bool
    backend: str
    error: Optional[str] = None


@dataclass
class BackendPerformanceStats:
    """
    Performance statistics for a backend.
    
    Aggregated performance statistics calculated from metric samples within
    the configured time window, including request counts, latency percentiles,
    and error rates.
    
    Attributes:
        total_requests: Total number of requests in the time window.
        successful_requests: Number of successful requests.
        failed_requests: Number of failed requests.
        total_duration_ms: Cumulative duration of all requests.
        avg_duration_ms: Average request duration.
        p50_duration_ms: 50th percentile duration (median).
        p95_duration_ms: 95th percentile duration.
        p99_duration_ms: 99th percentile duration.
        error_rate: Fraction of requests that failed (0.0 to 1.0).
        last_error: Most recent error message.
        last_error_time: Unix timestamp of the most recent error.
    """
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_duration_ms: float = 0.0
    avg_duration_ms: float = 0.0
    p50_duration_ms: float = 0.0
    p95_duration_ms: float = 0.0
    p99_duration_ms: float = 0.0
    error_rate: float = 0.0
    last_error: Optional[str] = None
    last_error_time: Optional[float] = None


class PerformanceMonitor:
    """
    Monitor backend performance metrics.
    
    Tracks performance metrics for multiple backends, calculates aggregated
    statistics within a sliding time window, and provides methods to detect
    backend degradation based on error rate and latency thresholds.
    
    Attributes:
        max_samples: Maximum number of metric samples to retain per backend.
        window_seconds: Time window in seconds for metric aggregation.
    """
    
    def __init__(
        self,
        max_samples: int = 1000,
        window_seconds: int = 300,  # 5 minutes
    ):
        """
        Initialize the performance monitor.
        
        Args:
            max_samples: Maximum number of metric samples to retain per backend.
            window_seconds: Time window in seconds for metric aggregation.
        """
        self.max_samples = max_samples
        self.window_seconds = window_seconds
        self._metrics: Dict[str, deque] = {}
        self._backend_stats: Dict[str, BackendPerformanceStats] = {}
        
        logger.info(f"PerformanceMonitor initialized: max_samples={max_samples}, window_seconds={window_seconds}")
    
    def record_metric(
        self,
        backend: str,
        duration_ms: float,
        success: bool,
        error: Optional[str] = None,
    ) -> None:
        """
        Record a performance metric.
        
        Adds a new metric sample for the specified backend and updates the
        aggregated statistics.
        
        Args:
            backend: Name of the backend that handled the request.
            duration_ms: Request duration in milliseconds.
            success: Whether the request was successful.
            error: Optional error message if the request failed.
        """
        metric = PerformanceMetric(
            timestamp=time.time(),
            duration_ms=duration_ms,
            success=success,
            backend=backend,
            error=error,
        )
        
        # Initialize deque for backend if not exists
        if backend not in self._metrics:
            self._metrics[backend] = deque(maxlen=self.max_samples)
        
        self._metrics[backend].append(metric)
        
        # Update stats
        self._update_backend_stats(backend)
        
        logger.debug(f"Metric recorded: backend={backend}, duration_ms={duration_ms:.2f}, success={success}")
    
    def _update_backend_stats(self, backend: str) -> None:
        """
        Update performance statistics for a backend.
        
        Recalculates aggregated statistics for the specified backend based on
        metrics within the configured time window.
        
        Args:
            backend: Name of the backend to update statistics for.
        """
        metrics = self._metrics.get(backend, deque())
        
        # Filter metrics within time window
        cutoff_time = time.time() - self.window_seconds
        recent_metrics = [m for m in metrics if m.timestamp >= cutoff_time]
        
        if not recent_metrics:
            return
        
        stats = BackendPerformanceStats()
        stats.total_requests = len(recent_metrics)
        stats.successful_requests = sum(1 for m in recent_metrics if m.success)
        stats.failed_requests = sum(1 for m in recent_metrics if not m.success)
        
        # Calculate duration statistics
        durations = [m.duration_ms for m in recent_metrics]
        stats.total_duration_ms = sum(durations)
        stats.avg_duration_ms = stats.total_duration_ms / len(durations)
        
        # Calculate percentiles
        sorted_durations = sorted(durations)
        n = len(sorted_durations)
        stats.p50_duration_ms = sorted_durations[int(n * 0.5)]
        stats.p95_duration_ms = sorted_durations[int(n * 0.95)]
        stats.p99_duration_ms = sorted_durations[int(n * 0.99)]
        
        # Calculate error rate
        stats.error_rate = stats.failed_requests / stats.total_requests if stats.total_requests > 0 else 0.0
        
        # Get last error
        for m in reversed(recent_metrics):
            if not m.success and m.error:
                stats.last_error = m.error
                stats.last_error_time = m.timestamp
                break
        
        self._backend_stats[backend] = stats
    
    def get_backend_stats(self, backend: str) -> Optional[BackendPerformanceStats]:
        """
        Get performance statistics for a specific backend.
        
        Args:
            backend: Name of the backend to get statistics for.
            
        Returns:
            BackendPerformanceStats for the backend, or None if no stats available.
        """
        return self._backend_stats.get(backend)
    
    def get_all_stats(self) -> Dict[str, BackendPerformanceStats]:
        """
        Get performance statistics for all backends.
        
        Returns:
            Dictionary mapping backend names to their BackendPerformanceStats.
        """
        return self._backend_stats.copy()
    
    def cleanup_old_metrics(self) -> int:
        """
        Remove metrics older than the time window.
        
        Removes metric samples that fall outside the configured time window
        and recalculates statistics for all backends.
        
        Returns:
            Number of metric samples removed.
        """
        cutoff_time = time.time() - self.window_seconds
        removed = 0
        
        for backend, metrics in self._metrics.items():
            original_len = len(metrics)
            # Keep only recent metrics
            while metrics and metrics[0].timestamp < cutoff_time:
                metrics.popleft()
                removed += (original_len - len(metrics))
        
        # Recalculate stats after cleanup
        for backend in self._metrics:
            self._update_backend_stats(backend)
        
        if removed > 0:
            logger.debug(f"Cleaned up {removed} old metrics")
        
        return removed
    
    def is_backend_degraded(self, backend: str, error_threshold: float = 0.1, latency_threshold_ms: float = 1000.0) -> Tuple[bool, str]:
        """
        Check if a backend is degraded based on performance metrics.
        
        Evaluates backend health by comparing error rate and p95 latency
        against configurable thresholds.
        
        Args:
            backend: Backend name to check.
            error_threshold: Error rate threshold (default 10%).
            latency_threshold_ms: Latency threshold in milliseconds (default 1000ms).
            
        Returns:
            Tuple of (is_degraded, reason) where is_degraded is True if the
            backend exceeds thresholds, and reason is a string explaining why.
        """
        stats = self.get_backend_stats(backend)
        
        if not stats or stats.total_requests < 10:
            # Not enough data to determine
            return False, "insufficient_data"
        
        # Check error rate
        if stats.error_rate > error_threshold:
            return True, f"error_rate_exceeded: {stats.error_rate:.2%} > {error_threshold:.2%}"
        
        # Check latency
        if stats.p95_duration_ms > latency_threshold_ms:
            return True, f"latency_exceeded: p95={stats.p95_duration_ms:.2f}ms > {latency_threshold_ms}ms"
        
        return False, "healthy"
    
    def get_performance_summary(self) -> dict:
        """
        Get a summary of all backend performance.
        
        Returns a dictionary containing performance statistics for all backends
        in a format suitable for API responses or monitoring dashboards.
        
        Returns:
            Dictionary with timestamp, window configuration, and backend statistics.
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "window_seconds": self.window_seconds,
            "backends": {},
        }
        
        for backend, stats in self._backend_stats.items():
            summary["backends"][backend] = {
                "total_requests": stats.total_requests,
                "success_rate": (stats.successful_requests / stats.total_requests) if stats.total_requests > 0 else 0.0,
                "error_rate": stats.error_rate,
                "avg_duration_ms": stats.avg_duration_ms,
                "p50_duration_ms": stats.p50_duration_ms,
                "p95_duration_ms": stats.p95_duration_ms,
                "p99_duration_ms": stats.p99_duration_ms,
                "last_error": stats.last_error,
                "last_error_time": datetime.fromtimestamp(stats.last_error_time).isoformat() if stats.last_error_time else None,
            }
        
        return summary


# Global performance monitor instance
_global_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """
    Get the global performance monitor instance.
    
    Returns a singleton PerformanceMonitor instance, creating it on first call.
    
    Returns:
        The global PerformanceMonitor instance.
    """
    global _global_monitor
    
    if _global_monitor is None:
        _global_monitor = PerformanceMonitor()
    
    return _global_monitor


async def record_backend_call(
    backend: str,
    duration_ms: float,
    success: bool,
    error: Optional[str] = None,
) -> None:
    """
    Record a backend call for performance monitoring.
    
    Convenience function to record a backend call using the global monitor instance.
    
    Args:
        backend: Name of the backend that handled the request.
        duration_ms: Request duration in milliseconds.
        success: Whether the request was successful.
        error: Optional error message if the request failed.
    """
    monitor = get_performance_monitor()
    monitor.record_metric(backend, duration_ms, success, error)
