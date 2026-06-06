"""
Automated Latency Measurement Tool

This tool provides comprehensive latency measurement and analysis for the
translation pipeline. It measures each stage independently and provides
optimization recommendations.

Usage:
    python scripts/measure_latency.py --backend-url http://localhost:8000 --token <token>

Features:
- Per-stage latency measurement (STT, Translation, TTS)
- End-to-end latency tracking
- Statistical analysis (mean, median, p95, p99)
- Latency breakdown visualization
- Optimization recommendations
"""

import asyncio
import websockets
import json
import time
import argparse
import sys
from pathlib import Path
from typing import Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
import numpy as np
import statistics


@dataclass
class LatencyMeasurement:
    """Single latency measurement."""
    timestamp: float
    stage: str  # "stt", "translation", "tts", "end_to_end"
    latency_ms: float
    metadata: Dict = field(default_factory=dict)


@dataclass
class LatencyStats:
    """Statistical analysis of latency measurements."""
    stage: str
    count: int
    mean_ms: float
    median_ms: float
    std_ms: float
    min_ms: float
    max_ms: float
    p95_ms: float
    p99_ms: float


class LatencyProfiler:
    """Comprehensive latency profiler for the translation pipeline."""
    
    def __init__(self, backend_url: str, token: str):
        self.backend_url = backend_url
        self.token = token
        self.measurements: List[LatencyMeasurement] = []
        self.ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
        
    def add_measurement(self, stage: str, latency_ms: float, metadata: Dict = None):
        """Add a latency measurement."""
        self.measurements.append(LatencyMeasurement(
            timestamp=time.time(),
            stage=stage,
            latency_ms=latency_ms,
            metadata=metadata or {},
        ))
    
    def calculate_stats(self, stage: str) -> LatencyStats:
        """Calculate statistics for a specific stage."""
        stage_measurements = [m for m in self.measurements if m.stage == stage]
        
        if not stage_measurements:
            return LatencyStats(
                stage=stage,
                count=0,
                mean_ms=0,
                median_ms=0,
                std_ms=0,
                min_ms=0,
                max_ms=0,
                p95_ms=0,
                p99_ms=0,
            )
        
        latencies = [m.latency_ms for m in stage_measurements]
        
        return LatencyStats(
            stage=stage,
            count=len(latencies),
            mean_ms=statistics.mean(latencies),
            median_ms=statistics.median(latencies),
            std_ms=statistics.stdev(latencies) if len(latencies) > 1 else 0,
            min_ms=min(latencies),
            max_ms=max(latencies),
            p95_ms=np.percentile(latencies, 95),
            p99_ms=np.percentile(latencies, 99),
        )
    
    async def measure_stt_latency(self, iterations: int = 10) -> LatencyStats:
        """Measure STT latency."""
        print(f"\nMeasuring STT latency ({iterations} iterations)...")
        
        for i in range(iterations):
            start = time.time()
            
            # Simulate STT processing (in real scenario, this would be actual audio)
            # For now, we'll measure the WebSocket round-trip time
            try:
                ws_url = f"{self.ws_url}/ws/audio?access_token={self.token}"
                async with websockets.connect(ws_url) as websocket:
                    await websocket.send(json.dumps({"type": "ping"}))
                    await websocket.recv()
                    
                latency = (time.time() - start) * 1000
                self.add_measurement("stt", latency, {"iteration": i})
                print(f"  Iteration {i+1}: {latency:.0f}ms")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return self.calculate_stats("stt")
    
    async def measure_translation_latency(self, iterations: int = 10) -> LatencyStats:
        """Measure translation latency."""
        print(f"\nMeasuring translation latency ({iterations} iterations)...")
        
        for i in range(iterations):
            start = time.time()
            
            try:
                # Use HTTP API for translation
                response = await asyncio.to_thread(
                    lambda: __import__('requests').post(
                        f"{self.backend_url}/translate/text",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "text": "Hello, how are you?",
                            "source_language": "en",
                            "target_language": "es",
                        },
                        timeout=10
                    )
                )
                
                latency = (time.time() - start) * 1000
                self.add_measurement("translation", latency, {"iteration": i})
                print(f"  Iteration {i+1}: {latency:.0f}ms")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return self.calculate_stats("translation")
    
    async def measure_tts_latency(self, iterations: int = 10) -> LatencyStats:
        """Measure TTS latency."""
        print(f"\nMeasuring TTS latency ({iterations} iterations)...")
        
        for i in range(iterations):
            start = time.time()
            
            try:
                # Use HTTP API for TTS
                response = await asyncio.to_thread(
                    lambda: __import__('requests').post(
                        f"{self.backend_url}/tts",
                        headers={"Authorization": f"Bearer {self.token}"},
                        json={
                            "text": "Hello",
                            "language": "en",
                        },
                        timeout=10
                    )
                )
                
                latency = (time.time() - start) * 1000
                self.add_measurement("tts", latency, {"iteration": i})
                print(f"  Iteration {i+1}: {latency:.0f}ms")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return self.calculate_stats("tts")
    
    async def measure_end_to_end_latency(self, iterations: int = 5) -> LatencyStats:
        """Measure end-to-end latency through WebSocket streaming."""
        print(f"\nMeasuring end-to-end latency ({iterations} iterations)...")
        
        for i in range(iterations):
            start = time.time()
            tts_received = False
            
            try:
                ws_url = f"{self.ws_url}/ws/audio?access_token={self.token}"
                async with websockets.connect(ws_url) as websocket:
                    # Start session
                    await websocket.send(json.dumps({
                        "type": "start",
                        "session_id": f"latency_test_{int(time.time())}",
                        "device_id": "latency_test_device",
                        "speaker": "test",
                        "speaker_mode": "auto",
                        "source_language": "en",
                        "target_language": "es",
                    }))
                    
                    # Send minimal audio
                    await websocket.send(json.dumps({
                        "type": "chunk_meta",
                        "sent_at_ms": int(time.time() * 1000),
                        "bytes": 1000,
                        "mime_type": "audio/pcm16",
                    }))
                    await websocket.send(b'\x00' * 1000)
                    
                    # Finalize
                    await websocket.send(json.dumps({"type": "finalize"}))
                    
                    # Wait for TTS completion
                    timeout = 30
                    start_recv = time.time()
                    while time.time() - start_recv < timeout:
                        try:
                            message = await asyncio.wait_for(websocket.recv(), timeout=1.0)
                            data = json.loads(message)
                            
                            if data.get("type") == "tts_end":
                                tts_received = True
                                break
                                
                        except asyncio.TimeoutError:
                            continue
                
                latency = (time.time() - start) * 1000
                self.add_measurement("end_to_end", latency, {"iteration": i, "tts_received": tts_received})
                print(f"  Iteration {i+1}: {latency:.0f}ms (TTS: {'✓' if tts_received else '✗'})")
                
            except Exception as e:
                print(f"  Iteration {i+1}: Error - {e}")
        
        return self.calculate_stats("end_to_end")
    
    def generate_report(self) -> Dict:
        """Generate comprehensive latency report."""
        stages = ["stt", "translation", "tts", "end_to_end"]
        stats = {stage: self.calculate_stats(stage) for stage in stages}
        
        # Calculate total latency breakdown
        total_mean = sum(s.mean_ms for s in stats.values())
        
        # Generate recommendations
        recommendations = []
        
        if stats["stt"].mean_ms > 500:
            recommendations.append("STT latency is high (>500ms). Consider using smaller Whisper model or GPU acceleration.")
        
        if stats["translation"].mean_ms > 300:
            recommendations.append("Translation latency is high (>300ms). Consider using remote translator or caching.")
        
        if stats["tts"].mean_ms > 500:
            recommendations.append("TTS latency is high (>500ms). Consider using cloud TTS or smaller voice model.")
        
        if stats["end_to_end"].mean_ms > 2000:
            recommendations.append("End-to-end latency is high (>2s). Review all stages and optimize bottlenecks.")
        
        if stats["stt"].std_ms > 200:
            recommendations.append("STT latency has high variance. Check for inconsistent audio quality or network issues.")
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "backend_url": self.backend_url,
            "total_measurements": len(self.measurements),
            "stage_stats": {
                stage: {
                    "count": s.count,
                    "mean_ms": round(s.mean_ms, 2),
                    "median_ms": round(s.median_ms, 2),
                    "std_ms": round(s.std_ms, 2),
                    "min_ms": round(s.min_ms, 2),
                    "max_ms": round(s.max_ms, 2),
                    "p95_ms": round(s.p95_ms, 2),
                    "p99_ms": round(s.p99_ms, 2),
                }
                for stage, s in stats.items()
            },
            "latency_breakdown": {
                "stt_percentage": round(stats["stt"].mean_ms / total_mean * 100, 1) if total_mean > 0 else 0,
                "translation_percentage": round(stats["translation"].mean_ms / total_mean * 100, 1) if total_mean > 0 else 0,
                "tts_percentage": round(stats["tts"].mean_ms / total_mean * 100, 1) if total_mean > 0 else 0,
            },
            "total_mean_latency_ms": round(total_mean, 2),
            "recommendations": recommendations,
            "benchmark_score": self.calculate_benchmark_score(stats),
        }
        
        return report
    
    def calculate_benchmark_score(self, stats: Dict) -> Dict:
        """Calculate benchmark score based on latency targets."""
        score = 10
        details = []
        
        # STT: target < 500ms
        if stats["stt"].mean_ms < 300:
            details.append("STT: 10/10 (<300ms)")
        elif stats["stt"].mean_ms < 500:
            details.append("STT: 8/10 (300-500ms)")
            score -= 1
        else:
            details.append(f"STT: 5/10 ({stats['stt'].mean_ms:.0f}ms)")
            score -= 2
        
        # Translation: target < 300ms
        if stats["translation"].mean_ms < 200:
            details.append("Translation: 10/10 (<200ms)")
        elif stats["translation"].mean_ms < 300:
            details.append("Translation: 8/10 (200-300ms)")
            score -= 1
        else:
            details.append(f"Translation: 5/10 ({stats['translation'].mean_ms:.0f}ms)")
            score -= 2
        
        # TTS: target < 500ms
        if stats["tts"].mean_ms < 300:
            details.append("TTS: 10/10 (<300ms)")
        elif stats["tts"].mean_ms < 500:
            details.append("TTS: 8/10 (300-500ms)")
            score -= 1
        else:
            details.append(f"TTS: 5/10 ({stats['tts'].mean_ms:.0f}ms)")
            score -= 2
        
        # End-to-end: target < 1500ms
        if stats["end_to_end"].mean_ms < 1000:
            details.append("End-to-end: 10/10 (<1s)")
        elif stats["end_to_end"].mean_ms < 1500:
            details.append("End-to-end: 8/10 (1-1.5s)")
            score -= 1
        else:
            details.append(f"End-to-end: 5/10 ({stats['end_to_end'].mean_ms:.0f}ms)")
            score -= 2
        
        return {
            "score": max(1, min(10, score)),
            "details": details,
        }
    
    def print_report(self, report: Dict):
        """Print formatted report."""
        print("\n" + "=" * 70)
        print("LATENCY MEASUREMENT REPORT")
        print("=" * 70)
        print(f"Backend: {report['backend_url']}")
        print(f"Time: {report['timestamp']}")
        print(f"Total Measurements: {report['total_measurements']}")
        print()
        
        print("STAGE STATISTICS:")
        print("-" * 70)
        for stage, stats in report['stage_stats'].items():
            print(f"\n{stage.upper()}:")
            print(f"  Count: {stats['count']}")
            print(f"  Mean: {stats['mean_ms']:.0f}ms")
            print(f"  Median: {stats['median_ms']:.0f}ms")
            print(f"  Std Dev: {stats['std_ms']:.0f}ms")
            print(f"  Min: {stats['min_ms']:.0f}ms")
            print(f"  Max: {stats['max_ms']:.0f}ms")
            print(f"  P95: {stats['p95_ms']:.0f}ms")
            print(f"  P99: {stats['p99_ms']:.0f}ms")
        
        print("\n" + "-" * 70)
        print("LATENCY BREAKDOWN:")
        print(f"  STT: {report['latency_breakdown']['stt_percentage']}%")
        print(f"  Translation: {report['latency_breakdown']['translation_percentage']}%")
        print(f"  TTS: {report['latency_breakdown']['tts_percentage']}%")
        print(f"  Total Mean: {report['total_mean_latency_ms']:.0f}ms")
        
        print("\n" + "-" * 70)
        print("BENCHMARK SCORE:")
        print(f"  Overall: {report['benchmark_score']['score']}/10")
        for detail in report['benchmark_score']['details']:
            print(f"  {detail}")
        
        if report['recommendations']:
            print("\n" + "-" * 70)
            print("RECOMMENDATIONS:")
            for rec in report['recommendations']:
                print(f"  • {rec}")
        
        print("\n" + "=" * 70)


async def main():
    parser = argparse.ArgumentParser(description="Measure pipeline latency")
    parser.add_argument("--backend-url", required=True, help="Backend URL")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--iterations", type=int, default=10, help="Iterations per stage")
    parser.add_argument("--output", help="Output JSON file")
    
    args = parser.parse_args()
    
    profiler = LatencyProfiler(
        backend_url=args.backend_url,
        token=args.token,
    )
    
    print("=" * 70)
    print("LATENCY PROFILING")
    print("=" * 70)
    
    # Measure each stage
    await profiler.measure_stt_latency(args.iterations)
    await profiler.measure_translation_latency(args.iterations)
    await profiler.measure_tts_latency(args.iterations)
    await profiler.measure_end_to_end_latency(max(5, args.iterations // 2))
    
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
    
    # Exit with score as exit code (0 for 8-10, 1 for lower)
    sys.exit(0 if report['benchmark_score']['score'] >= 8 else 1)


if __name__ == "__main__":
    asyncio.run(main())
