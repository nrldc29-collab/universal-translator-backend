"""
Performance Profiling and Optimization Tool

This tool profiles the translation pipeline performance and provides
optimization recommendations based on actual measurements.

Usage:
    python scripts/profile_performance.py --backend-url http://localhost:8000 --token <token>

Features:
- CPU and memory profiling
- Bottleneck identification
- Resource usage tracking
- Optimization recommendations
- Performance regression detection
"""

import asyncio
import psutil
import time
import argparse
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import statistics
import requests


@dataclass
class PerformanceMetric:
    """Single performance metric."""
    timestamp: float
    metric_name: str
    value: float
    unit: str
    metadata: Dict = field(default_factory=dict)


@dataclass
class PerformanceSnapshot:
    """Snapshot of system performance."""
    timestamp: float
    cpu_percent: float
    memory_mb: float
    memory_percent: float
    disk_io_read_mb: float
    disk_io_write_mb: float
    network_sent_mb: float
    network_recv_mb: float
    active_connections: int


class PerformanceProfiler:
    """Comprehensive performance profiler."""
    
    def __init__(self, backend_url: str, token: str):
        self.backend_url = backend_url
        self.token = token
        self.metrics: List[PerformanceMetric] = []
        self.snapshots: List[PerformanceSnapshot] = []
        self.process = psutil.Process()
        
    def take_snapshot(self) -> PerformanceSnapshot:
        """Take a snapshot of system performance."""
        cpu = self.process.cpu_percent(interval=0.1)
        memory_info = self.process.memory_info()
        memory_mb = memory_info.rss / 1024 / 1024
        memory_percent = self.process.memory_percent()
        
        # Disk I/O
        disk_io = self.process.io_counters()
        disk_read_mb = disk_io.read_bytes / 1024 / 1024
        disk_write_mb = disk_io.write_bytes / 1024 / 1024
        
        # Network I/O
        net_io = psutil.net_io_counters()
        net_sent_mb = net_io.bytes_sent / 1024 / 1024
        net_recv_mb = net_io.bytes_recv / 1024 / 1024
        
        # Connections
        connections = len(self.process.connections())
        
        snapshot = PerformanceSnapshot(
            timestamp=time.time(),
            cpu_percent=cpu,
            memory_mb=memory_mb,
            memory_percent=memory_percent,
            disk_io_read_mb=disk_read_mb,
            disk_io_write_mb=disk_write_mb,
            network_sent_mb=net_sent_mb,
            network_recv_mb=net_recv_mb,
            active_connections=connections,
        )
        
        self.snapshots.append(snapshot)
        return snapshot
    
    def add_metric(self, metric_name: str, value: float, unit: str, metadata: Dict = None):
        """Add a performance metric."""
        self.metrics.append(PerformanceMetric(
            timestamp=time.time(),
            metric_name=metric_name,
            value=value,
            unit=unit,
            metadata=metadata or {},
        ))
    
    async def profile_translation_endpoint(self, iterations: int = 10) -> Dict:
        """Profile the translation endpoint."""
        print("\nProfiling translation endpoint...")
        
        latencies = []
        cpu_samples = []
        memory_samples = []
        
        for i in range(iterations):
            start = time.time()
            snapshot_before = self.take_snapshot()
            
            try:
                response = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{self.backend_url}/translate/text",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "text": "Hello, how are you today?",
                            "source_language": "en",
                            "target_language": "es",
                        },
                        timeout=10
                    )
                )
                
                latency = (time.time() - start) * 1000
                latencies.append(latency)
                
                snapshot_after = self.take_snapshot()
                cpu_samples.append(snapshot_after.cpu_percent)
                memory_samples.append(snapshot_after.memory_mb)
                
                self.add_metric("translation_latency", latency, "ms", {"iteration": i})
                self.add_metric("translation_cpu", snapshot_after.cpu_percent, "%", {"iteration": i})
                self.add_metric("translation_memory", snapshot_after.memory_mb, "MB", {"iteration": i})
                
                print(f"  Iteration {i+1}: {latency:.0f}ms, CPU: {snapshot_after.cpu_percent:.1f}%, Memory: {snapshot_after.memory_mb:.1f}MB")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return {
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "median_latency_ms": statistics.median(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "avg_cpu_percent": statistics.mean(cpu_samples) if cpu_samples else 0,
            "avg_memory_mb": statistics.mean(memory_samples) if memory_samples else 0,
        }
    
    async def profile_tts_endpoint(self, iterations: int = 10) -> Dict:
        """Profile the TTS endpoint."""
        print("\nProfiling TTS endpoint...")
        
        latencies = []
        cpu_samples = []
        memory_samples = []
        
        for i in range(iterations):
            start = time.time()
            snapshot_before = self.take_snapshot()
            
            try:
                response = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{self.backend_url}/tts",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "text": "Hello world",
                            "language": "en",
                        },
                        timeout=10
                    )
                )
                
                latency = (time.time() - start) * 1000
                latencies.append(latency)
                
                snapshot_after = self.take_snapshot()
                cpu_samples.append(snapshot_after.cpu_percent)
                memory_samples.append(snapshot_after.memory_mb)
                
                self.add_metric("tts_latency", latency, "ms", {"iteration": i})
                self.add_metric("tts_cpu", snapshot_after.cpu_percent, "%", {"iteration": i})
                self.add_metric("tts_memory", snapshot_after.memory_mb, "MB", {"iteration": i})
                
                print(f"  Iteration {i+1}: {latency:.0f}ms, CPU: {snapshot_after.cpu_percent:.1f}%, Memory: {snapshot_after.memory_mb:.1f}MB")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return {
            "avg_latency_ms": statistics.mean(latencies) if latencies else 0,
            "median_latency_ms": statistics.median(latencies) if latencies else 0,
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if latencies else 0,
            "avg_cpu_percent": statistics.mean(cpu_samples) if cpu_samples else 0,
            "avg_memory_mb": statistics.mean(memory_samples) if memory_samples else 0,
        }
    
    async def profile_concurrent_load(self, concurrent_requests: int = 5) -> Dict:
        """Profile under concurrent load."""
        print(f"\nProfiling under concurrent load ({concurrent_requests} requests)...")
        
        async def make_request():
            start = time.time()
            try:
                response = await asyncio.to_thread(
                    lambda: requests.post(
                        f"{self.backend_url}/translate/text",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "text": "Test message",
                            "source_language": "en",
                            "target_language": "es",
                        },
                        timeout=10
                    )
                )
                return (time.time() - start) * 1000
            except Exception:
                return -1
        
        start = time.time()
        snapshot_before = self.take_snapshot()
        
        tasks = [make_request() for _ in range(concurrent_requests)]
        latencies = await asyncio.gather(*tasks)
        
        snapshot_after = self.take_snapshot()
        total_time = time.time() - start
        
        successful = [l for l in latencies if l > 0]
        
        return {
            "total_time_ms": total_time * 1000,
            "successful_requests": len(successful),
            "failed_requests": len(latencies) - len(successful),
            "avg_latency_ms": statistics.mean(successful) if successful else 0,
            "max_latency_ms": max(successful) if successful else 0,
            "min_latency_ms": min(successful) if successful else 0,
            "cpu_delta_percent": snapshot_after.cpu_percent - snapshot_before.cpu_percent,
            "memory_delta_mb": snapshot_after.memory_mb - snapshot_before.memory_mb,
        }
    
    def analyze_bottlenecks(self) -> List[Dict]:
        """Analyze performance bottlenecks."""
        bottlenecks = []
        
        # Analyze CPU usage
        cpu_metrics = [m for m in self.metrics if "cpu" in m.metric_name]
        if cpu_metrics:
            avg_cpu = statistics.mean([m.value for m in cpu_metrics])
            if avg_cpu > 80:
                bottlenecks.append({
                    "type": "cpu",
                    "severity": "high",
                    "message": f"High CPU usage: {avg_cpu:.1f}%",
                    "recommendation": "Consider using GPU acceleration or reducing model size",
                })
            elif avg_cpu > 60:
                bottlenecks.append({
                    "type": "cpu",
                    "severity": "medium",
                    "message": f"Elevated CPU usage: {avg_cpu:.1f}%",
                    "recommendation": "Monitor CPU usage during peak load",
                })
        
        # Analyze memory usage
        memory_metrics = [m for m in self.metrics if "memory" in m.metric_name]
        if memory_metrics:
            avg_memory = statistics.mean([m.value for m in memory_metrics])
            if avg_memory > 1000:
                bottlenecks.append({
                    "type": "memory",
                    "severity": "high",
                    "message": f"High memory usage: {avg_memory:.1f}MB",
                    "recommendation": "Reduce buffer sizes or enable memory optimization",
                })
            elif avg_memory > 500:
                bottlenecks.append({
                    "type": "memory",
                    "severity": "medium",
                    "message": f"Elevated memory usage: {avg_memory:.1f}MB",
                    "recommendation": "Consider reducing model cache size",
                })
        
        # Analyze latency
        latency_metrics = [m for m in self.metrics if "latency" in m.metric_name]
        if latency_metrics:
            avg_latency = statistics.mean([m.value for m in latency_metrics])
            if avg_latency > 2000:
                bottlenecks.append({
                    "type": "latency",
                    "severity": "high",
                    "message": f"High latency: {avg_latency:.0f}ms",
                    "recommendation": "Optimize pipeline stages or use faster models",
                })
            elif avg_latency > 1000:
                bottlenecks.append({
                    "type": "latency",
                    "severity": "medium",
                    "message": f"Elevated latency: {avg_latency:.0f}ms",
                    "recommendation": "Review translation and TTS optimization",
                })
        
        return bottlenecks
    
    def generate_optimization_recommendations(self) -> List[str]:
        """Generate optimization recommendations."""
        recommendations = []
        
        # Analyze snapshots
        if self.snapshots:
            avg_cpu = statistics.mean([s.cpu_percent for s in self.snapshots])
            avg_memory = statistics.mean([s.memory_mb for s in self.snapshots])
            
            if avg_cpu > 70:
                recommendations.append("Reduce WHISPER_MODEL_SIZE to 'tiny' or 'base'")
                recommendations.append("Enable USE_GPU if available")
                recommendations.append("Reduce WHISPER_CPU_THREADS")
            
            if avg_memory > 500:
                recommendations.append("Reduce MAX_AUDIO_MB")
                recommendations.append("Reduce STREAM_BUFFER_MAX_MB")
                recommendations.append("Reduce STT_MAX_CONCURRENCY")
            
            if avg_cpu > 50 and avg_memory > 300:
                recommendations.append("Consider using remote translation service")
                recommendations.append("Enable HYBRID_ENABLE_MARIAN_FALLBACK=0")
        
        # Check for specific bottlenecks
        bottlenecks = self.analyze_bottlenecks()
        for bottleneck in bottlenecks:
            recommendations.append(bottleneck["recommendation"])
        
        # General recommendations
        recommendations.extend([
            "Monitor /diagnostics endpoint regularly",
            "Use /metrics endpoint for production monitoring",
            "Set up alerts for high CPU/memory usage",
            "Consider horizontal scaling for high traffic",
        ])
        
        return list(set(recommendations))  # Remove duplicates
    
    def generate_report(self) -> Dict:
        """Generate comprehensive performance report."""
        bottlenecks = self.analyze_bottlenecks()
        recommendations = self.generate_optimization_recommendations()
        
        # Calculate performance score
        score = 10
        if any(b["severity"] == "high" for b in bottlenecks):
            score -= 3
        elif any(b["severity"] == "medium" for b in bottlenecks):
            score -= 1
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "backend_url": self.backend_url,
            "total_metrics": len(self.metrics),
            "total_snapshots": len(self.snapshots),
            "bottlenecks": bottlenecks,
            "recommendations": recommendations,
            "performance_score": max(1, min(10, score)),
            "metrics_summary": {
                "cpu_metrics": len([m for m in self.metrics if "cpu" in m.metric_name]),
                "memory_metrics": len([m for m in self.metrics if "memory" in m.metric_name]),
                "latency_metrics": len([m for m in self.metrics if "latency" in m.metric_name]),
            },
        }
        
        return report
    
    def print_report(self, report: Dict):
        """Print formatted report."""
        print("\n" + "=" * 70)
        print("PERFORMANCE PROFILING REPORT")
        print("=" * 70)
        print(f"Backend: {report['backend_url']}")
        print(f"Time: {report['timestamp']}")
        print(f"Total Metrics: {report['total_metrics']}")
        print(f"Total Snapshots: {report['total_snapshots']}")
        print()
        
        print("METRICS SUMMARY:")
        print(f"  CPU metrics: {report['metrics_summary']['cpu_metrics']}")
        print(f"  Memory metrics: {report['metrics_summary']['memory_metrics']}")
        print(f"  Latency metrics: {report['metrics_summary']['latency_metrics']}")
        
        if report['bottlenecks']:
            print("\n" + "-" * 70)
            print("BOTTLENECKS:")
            for bottleneck in report['bottlenecks']:
                print(f"  [{bottleneck['severity'].upper()}] {bottleneck['type']}: {bottleneck['message']}")
                print(f"    → {bottleneck['recommendation']}")
        
        if report['recommendations']:
            print("\n" + "-" * 70)
            print("OPTIMIZATION RECOMMENDATIONS:")
            for i, rec in enumerate(report['recommendations'], 1):
                print(f"  {i}. {rec}")
        
        print("\n" + "-" * 70)
        print(f"PERFORMANCE SCORE: {report['performance_score']}/10")
        print("=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="Profile performance")
    parser.add_argument("--backend-url", required=True, help="Backend URL")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per test")
    parser.add_argument("--concurrent", type=int, default=5, help="Concurrent requests")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    profiler = PerformanceProfiler(
        backend_url=args.backend_url,
        token=args.token,
    )
    
    print("=" * 70)
    print("PERFORMANCE PROFILING")
    print("=" * 70)
    
    # Profile endpoints
    await profiler.profile_translation_endpoint(args.iterations)
    await profiler.profile_tts_endpoint(args.iterations)
    await profiler.profile_concurrent_load(args.concurrent)
    
    # Generate report
    report = profiler.generate_report()
    profiler.print_report(report)
    
    # Save report
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\nReport saved to: {output_path}")
    
    # Exit with score as exit code
    sys.exit(0 if report['performance_score'] >= 8 else 1)


if __name__ == "__main__":
    asyncio.run(main())
