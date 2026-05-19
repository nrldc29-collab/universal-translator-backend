#!/usr/bin/env python3
"""
Automated Load Testing for STT Platform

Performs automated load testing of the STT Platform with configurable
parameters and automated reporting. Tests WebSocket streaming performance
under various load conditions.
"""

import asyncio
import websockets
import json
import logging
import time
import argparse
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
from dataclasses import dataclass
import statistics
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""
    url: str
    api_key: str
    num_clients: int = 10
    duration_seconds: int = 60
    audio_duration_ms: int = 30
    sample_rate: int = 16000
    channels: int = 1
    frame_ms: int = 30


@dataclass
class LoadTestResult:
    """Results from load testing."""
    total_clients: int
    successful_connections: int
    failed_connections: int
    total_transcriptions: int
    p50_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    avg_latency_ms: float
    errors: List[str]
    duration_seconds: int


class AudioGenerator:
    """Generates synthetic audio for load testing."""
    
    @staticmethod
    def generate_sine_wave(duration_ms: int, sample_rate: int = 16000) -> bytes:
        """
        Generate sine wave audio.
        
        Args:
            duration_ms: Duration in milliseconds
            sample_rate: Sample rate in Hz
            
        Returns:
            PCM16 audio bytes
        """
        import math
        import struct
        
        num_samples = int(duration_ms * sample_rate / 1000)
        frequency = 440  # A4 note
        amplitude = 16000  # Max value for int16
        
        audio_data = bytearray()
        for i in range(num_samples):
            t = i / sample_rate
            value = int(amplitude * math.sin(2 * math.pi * frequency * t))
            audio_data.extend(struct.pack('<h', value))
        
        return bytes(audio_data)
    
    @staticmethod
    def generate_chunks(duration_ms: int, frame_ms: int, sample_rate: int = 16000):
        """
        Generate audio chunks for streaming.
        
        Args:
            duration_ms: Total duration in milliseconds
            frame_ms: Frame duration in milliseconds
            sample_rate: Sample rate in Hz
            
        Yields:
            Audio chunks
        """
        frame_samples = int(frame_ms * sample_rate / 1000)
        total_samples = int(duration_ms * sample_rate / 1000)
        
        for offset in range(0, total_samples, frame_samples):
            chunk_duration = min(frame_ms, duration_ms - (offset * 1000 / sample_rate))
            yield AudioGenerator.generate_sine_wave(chunk_duration, sample_rate)


class LoadTestClient:
    """Individual load test client."""
    
    def __init__(self, config: LoadTestConfig, client_id: int):
        """
        Initialize load test client.
        
        Args:
            config: Load test configuration
            client_id: Client identifier
        """
        self.config = config
        self.client_id = client_id
        self.latencies: List[float] = []
        self.errors: List[str] = []
        self.transcription_count = 0
        self.connected = False
    
    async def run(self):
        """Run load test client."""
        try:
            uri = f"{self.config.url}?api_key={self.config.api_key}"
            logger.info(f"Client {self.client_id}: Connecting to {uri}")
            
            async with websockets.connect(uri) as websocket:
                self.connected = True
                logger.info(f"Client {self.client_id}: Connected")
                
                start_time = time.time()
                end_time = start_time + self.config.duration_seconds
                
                # Stream audio
                for chunk in AudioGenerator.generate_chunks(
                    self.config.audio_duration_ms,
                    self.config.frame_ms,
                    self.config.sample_rate
                ):
                    if time.time() > end_time:
                        break
                    
                    chunk_start = time.time()
                    await websocket.send(chunk)
                    
                    # Receive responses
                    try:
                        response = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=5.0
                        )
                        response_data = json.loads(response)
                        latency_ms = (time.time() - chunk_start) * 1000
                        self.latencies.append(latency_ms)
                        
                        if response_data.get("type") == "transcript.final":
                            self.transcription_count += 1
                    except asyncio.TimeoutError:
                        self.errors.append(f"Timeout at {time.time()}")
                
                self.connected = False
                logger.info(f"Client {self.client_id}: Completed")
                
        except Exception as exc:
            self.connected = False
            self.errors.append(str(exc))
            logger.error(f"Client {self.client_id}: Error - {exc}")


class LoadTestRunner:
    """Manages load testing execution."""
    
    def __init__(self, config: LoadTestConfig):
        """
        Initialize load test runner.
        
        Args:
            config: Load test configuration
        """
        self.config = config
        self.clients: List[LoadTestClient] = []
        self.results: Optional[LoadTestResult] = None
    
    async def run_test(self) -> LoadTestResult:
        """
        Run load test.
        
        Returns:
            Load test results
        """
        logger.info(f"Starting load test with {self.config.num_clients} clients")
        
        # Create clients
        self.clients = [
            LoadTestClient(self.config, i)
            for i in range(self.config.num_clients)
        ]
        
        # Run all clients concurrently
        start_time = time.time()
        await asyncio.gather(*[client.run() for client in self.clients])
        duration = time.time() - start_time
        
        # Collect results
        successful_connections = sum(1 for c in self.clients if c.connected)
        failed_connections = len(self.clients) - successful_connections
        total_transcriptions = sum(c.transcription_count for c in self.clients)
        all_latencies = []
        errors = []
        
        for client in self.clients:
            all_latencies.extend(client.latencies)
            errors.extend(client.errors)
        
        # Calculate statistics
        if all_latencies:
            p50_latency = statistics.percentile(all_latencies, 50)
            p95_latency = statistics.percentile(all_latencies, 95)
            p99_latency = statistics.percentile(all_latencies, 99)
            avg_latency = statistics.mean(all_latencies)
        else:
            p50_latency = 0
            p95_latency = 0
            p99_latency = 0
            avg_latency = 0
        
        self.results = LoadTestResult(
            total_clients=self.config.num_clients,
            successful_connections=successful_connections,
            failed_connections=failed_connections,
            total_transcriptions=total_transcriptions,
            p50_latency_ms=p50_latency,
            p95_latency_ms=p95_latency,
            p99_latency_ms=p99_latency,
            avg_latency_ms=avg_latency,
            errors=errors,
            duration_seconds=duration
        )
        
        logger.info("Load test completed")
        return self.results
    
    def print_results(self):
        """Print load test results."""
        if not self.results:
            logger.error("No results to print")
            return
        
        print("\n" + "="*60)
        print("LOAD TEST RESULTS")
        print("="*60)
        print(f"Total Clients: {self.results.total_clients}")
        print(f"Successful Connections: {self.results.successful_connections}")
        print(f"Failed Connections: {self.results.failed_connections}")
        print(f"Total Transcriptions: {self.results.total_transcriptions}")
        print(f"Duration: {self.results.duration_seconds:.2f}s")
        print(f"\nLatency (ms):")
        print(f"  P50: {self.results.p50_latency_ms:.2f}")
        print(f"  P95: {self.results.p95_latency_ms:.2f}")
        print(f"  P99: {self.results.p99_latency_ms:.2f}")
        print(f"  Average: {self.results.avg_latency_ms:.2f}")
        
        if self.results.errors:
            print(f"\nErrors ({len(self.results.errors)}):")
            for error in self.results.errors[:10]:  # Show first 10 errors
                print(f"  - {error}")
            if len(self.results.errors) > 10:
                print(f"  ... and {len(self.results.errors) - 10} more")
        
        print("="*60 + "\n")
    
    def save_results(self, output_file: str):
        """
        Save results to JSON file.
        
        Args:
            output_file: Path to output file
        """
        if not self.results:
            logger.error("No results to save")
            return
        
        results_dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "url": self.config.url,
                "num_clients": self.config.num_clients,
                "duration_seconds": self.config.duration_seconds,
                "audio_duration_ms": self.config.audio_duration_ms
            },
            "results": {
                "total_clients": self.results.total_clients,
                "successful_connections": self.results.successful_connections,
                "failed_connections": self.results.failed_connections,
                "total_transcriptions": self.results.total_transcriptions,
                "p50_latency_ms": self.results.p50_latency_ms,
                "p95_latency_ms": self.results.p95_latency_ms,
                "p99_latency_ms": self.results.p99_latency_ms,
                "avg_latency_ms": self.results.avg_latency_ms,
                "duration_seconds": self.results.duration_seconds,
                "errors": self.results.errors
            }
        }
        
        with open(output_file, 'w') as f:
            json.dump(results_dict, f, indent=2)
        
        logger.info(f"Results saved to {output_file}")


class LoadTestScheduler:
    """Schedules and runs automated load tests."""
    
    def __init__(self):
        """Initialize load test scheduler."""
        self.test_history: List[Dict[str, Any]] = []
    
    async def run_scheduled_test(
        self,
        url: str,
        api_key: str,
        num_clients: int = 10,
        duration_seconds: int = 60
    ) -> LoadTestResult:
        """
        Run a scheduled load test.
        
        Args:
            url: WebSocket URL
            api_key: API key
            num_clients: Number of concurrent clients
            duration_seconds: Test duration
            
        Returns:
            Load test results
        """
        config = LoadTestConfig(
            url=url,
            api_key=api_key,
            num_clients=num_clients,
            duration_seconds=duration_seconds
        )
        
        runner = LoadTestRunner(config)
        results = await runner.run_test()
        
        # Store in history
        self.test_history.append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "config": {
                "num_clients": num_clients,
                "duration_seconds": duration_seconds
            },
            "results": results.__dict__
        })
        
        return results
    
    def get_trend_analysis(self) -> Dict[str, Any]:
        """
        Analyze trends in load test history.
        
        Returns:
            Trend analysis
        """
        if not self.test_history:
            return {"error": "No test history available"}
        
        # Extract P95 latencies
        p95_latencies = [
            test["results"]["p95_latency_ms"]
            for test in self.test_history
        ]
        
        return {
            "total_tests": len(self.test_history),
            "p95_latency_trend": p95_latencies,
            "avg_p95_latency": statistics.mean(p95_latencies),
            "min_p95_latency": min(p95_latencies),
            "max_p95_latency": max(p95_latencies)
        }


async def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Automated Load Testing for STT Platform")
    parser.add_argument("--url", required=True, help="WebSocket URL")
    parser.add_argument("--api-key", required=True, help="API key")
    parser.add_argument("--clients", type=int, default=10, help="Number of concurrent clients")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in seconds")
    parser.add_argument("--audio-duration", type=int, default=30000, help="Audio duration in milliseconds")
    parser.add_argument("--output", help="Output file for results")
    
    args = parser.parse_args()
    
    config = LoadTestConfig(
        url=args.url,
        api_key=args.api_key,
        num_clients=args.clients,
        duration_seconds=args.duration,
        audio_duration_ms=args.audio_duration
    )
    
    runner = LoadTestRunner(config)
    results = await runner.run_test()
    
    runner.print_results()
    
    if args.output:
        runner.save_results(args.output)


if __name__ == "__main__":
    asyncio.run(main())
