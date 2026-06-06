"""
Real Device Pipeline Testing Automation

This script automates testing the complete Mic→VAD→STT→Translate→TTS→Speaker pipeline
on a real mobile device. It simulates real-world usage patterns and validates each stage.

Usage:
    python scripts/test_real_device_pipeline.py --backend-url http://localhost:8000 --token <token>

Requirements:
    - Backend running at specified URL
    - Valid authentication token
    - Mobile device connected to same network (or Railway deployment)
"""

import asyncio
import websockets
import json
import time
import argparse
import sys
from pathlib import Path
import wave
import struct
import numpy as np
from typing import Dict, List, Optional
from dataclasses import dataclass
from datetime import datetime


@dataclass
class PipelineTestResult:
    """Results from a single pipeline test."""
    test_name: str
    success: bool
    stt_latency_ms: float
    translation_latency_ms: float
    tts_latency_ms: float
    end_to_end_latency_ms: float
    source_text: str
    translated_text: str
    audio_chunks_received: int
    errors: List[str]


class RealDevicePipelineTester:
    """Automated tester for the real device pipeline."""
    
    def __init__(self, backend_url: str, token: str, test_audio_dir: str = "models"):
        self.backend_url = backend_url
        self.token = token
        self.test_audio_dir = Path(test_audio_dir)
        self.results: List[PipelineTestResult] = []
        self.ws_url = backend_url.replace("http://", "ws://").replace("https://", "wss://")
        
    def create_test_audio(self, text: str, duration: float = 2.0, sample_rate: int = 16000) -> bytes:
        """Create synthetic test audio with speech-like patterns."""
        num_samples = int(sample_rate * duration)
        
        # Generate speech-like waveform (simplified)
        t = np.linspace(0, duration, num_samples)
        # Mix of frequencies to simulate speech
        waveform = (
            0.5 * np.sin(2 * np.pi * 200 * t) +
            0.3 * np.sin(2 * np.pi * 400 * t) +
            0.2 * np.sin(2 * np.pi * 800 * t)
        )
        
        # Add some amplitude variation
        envelope = np.sin(np.pi * t / duration) ** 0.5
        waveform = waveform * envelope
        
        # Convert to 16-bit PCM
        waveform = np.clip(waveframe, -1, 1)
        waveform_int16 = (waveform * 32767).astype(np.int16)
        
        return waveform_int16.tobytes()
    
    async def test_single_phrase(self, phrase: str, language: str = "en") -> PipelineTestResult:
        """Test a single phrase through the complete pipeline."""
        test_name = f"Test phrase: '{phrase}'"
        errors = []
        
        # Timing
        start_time = time.time()
        stt_start = None
        translation_start = None
        tts_start = None
        tts_end = None
        
        source_text = ""
        translated_text = ""
        audio_chunks = 0
        
        try:
            # Connect to WebSocket
            ws_url = f"{self.ws_url}/ws/audio?access_token={self.token}"
            print(f"Connecting to {ws_url}")
            
            async with websockets.connect(ws_url) as websocket:
                # Send start message
                start_msg = {
                    "type": "start",
                    "session_id": f"test_{int(time.time())}",
                    "device_id": "test_device",
                    "speaker": "test_speaker",
                    "speaker_mode": "auto",
                    "source_language": language,
                    "target_language": "es",
                }
                await websocket.send(json.dumps(start_msg))
                
                # Create and send test audio
                audio_data = self.create_test_audio(phrase, duration=2.0)
                
                # Send chunk metadata
                chunk_meta = {
                    "type": "chunk_meta",
                    "sent_at_ms": int(time.time() * 1000),
                    "bytes": len(audio_data),
                    "mime_type": "audio/pcm16",
                }
                await websocket.send(json.dumps(chunk_meta))
                
                # Send audio data
                await websocket.send(audio_data)
                
                # Send finalize
                await websocket.send(json.dumps({"type": "finalize"}))
                
                # Collect responses
                timeout = 30  # seconds
                start_recv = time.time()
                
                while time.time() - start_recv < timeout:
                    try:
                        message = await asyncio.wait_for(
                            websocket.recv(),
                            timeout=1.0
                        )
                        data = json.loads(message)
                        
                        if data.get("type") == "final_transcription":
                            stt_start = stt_start or start_time
                            source_text = data.get("text", "")
                            print(f"STT: {source_text}")
                            
                        elif data.get("type") == "final":
                            translation_start = translation_start or time.time()
                            translated_text = data.get("text", data.get("translated_text", ""))
                            print(f"Translation: {translated_text}")
                            
                        elif data.get("type") == "tts_audio_chunk":
                            tts_start = tts_start or time.time()
                            audio_chunks += 1
                            
                        elif data.get("type") == "tts_end":
                            tts_end = time.time()
                            print(f"TTS complete, {audio_chunks} chunks")
                            break
                            
                        elif data.get("type") == "error":
                            errors.append(data.get("message", data.get("error", "Unknown error")))
                            print(f"Error: {errors[-1]}")
                            
                    except asyncio.TimeoutError:
                        # Check if we have results
                        if source_text and translated_text:
                            break
                        continue
                
                # Calculate latencies
                end_time = time.time()
                stt_latency = (stt_start - start_time) * 1000 if stt_start else 0
                translation_latency = (translation_start - stt_start) * 1000 if translation_start and stt_start else 0
                tts_latency = (tts_end - tts_start) * 1000 if tts_start and tts_end else 0
                end_to_end = (end_time - start_time) * 1000
                
                success = bool(source_text and translated_text and audio_chunks > 0)
                
                return PipelineTestResult(
                    test_name=test_name,
                    success=success,
                    stt_latency_ms=stt_latency,
                    translation_latency_ms=translation_latency,
                    tts_latency_ms=tts_latency,
                    end_to_end_latency_ms=end_to_end,
                    source_text=source_text,
                    translated_text=translated_text,
                    audio_chunks_received=audio_chunks,
                    errors=errors,
                )
                
        except Exception as e:
            errors.append(str(e))
            return PipelineTestResult(
                test_name=test_name,
                success=False,
                stt_latency_ms=0,
                translation_latency_ms=0,
                tts_latency_ms=0,
                end_to_end_latency_ms=0,
                source_text=source_text,
                translated_text=translated_text,
                audio_chunks_received=audio_chunks,
                errors=errors,
            )
    
    async def run_test_suite(self) -> Dict:
        """Run comprehensive test suite."""
        print("=" * 60)
        print("REAL DEVICE PIPELINE TEST SUITE")
        print("=" * 60)
        print(f"Backend: {self.backend_url}")
        print(f"Time: {datetime.now().isoformat()}")
        print()
        
        test_phrases = [
            "Hello, how are you?",
            "Where is the nearest restaurant?",
            "I need help with translation",
            "The weather is nice today",
            "Thank you very much",
        ]
        
        results = []
        for phrase in test_phrases:
            print(f"\nTesting: {phrase}")
            print("-" * 40)
            result = await self.test_single_phrase(phrase)
            results.append(result)
            self.results.append(result)
            
            # Small delay between tests
            await asyncio.sleep(2)
        
        # Generate report
        return self.generate_report(results)
    
    def generate_report(self, results: List[PipelineTestResult]) -> Dict:
        """Generate comprehensive test report."""
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        
        avg_stt = np.mean([r.stt_latency_ms for r in successful]) if successful else 0
        avg_translation = np.mean([r.translation_latency_ms for r in successful]) if successful else 0
        avg_tts = np.mean([r.tts_latency_ms for r in successful]) if successful else 0
        avg_e2e = np.mean([r.end_to_end_latency_ms for r in successful]) if successful else 0
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results) * 100 if results else 0,
            "latency_metrics": {
                "avg_stt_ms": avg_stt,
                "avg_translation_ms": avg_translation,
                "avg_tts_ms": avg_tts,
                "avg_end_to_end_ms": avg_e2e,
                "max_end_to_end_ms": max([r.end_to_end_latency_ms for r in successful]) if successful else 0,
                "min_end_to_end_ms": min([r.end_to_end_latency_ms for r in successful]) if successful else 0,
            },
            "test_results": [
                {
                    "test_name": r.test_name,
                    "success": r.success,
                    "stt_latency_ms": r.stt_latency_ms,
                    "translation_latency_ms": r.translation_latency_ms,
                    "tts_latency_ms": r.tts_latency_ms,
                    "end_to_end_latency_ms": r.end_to_end_latency_ms,
                    "source_text": r.source_text,
                    "translated_text": r.translated_text,
                    "audio_chunks": r.audio_chunks_received,
                    "errors": r.errors,
                }
                for r in results
            ],
        }
        
        # Print report
        print("\n" + "=" * 60)
        print("TEST REPORT")
        print("=" * 60)
        print(f"Total Tests: {report['total_tests']}")
        print(f"Successful: {report['successful']}")
        print(f"Failed: {report['failed']}")
        print(f"Success Rate: {report['success_rate']:.1f}%")
        print()
        print("LATENCY METRICS:")
        print(f"  Average STT: {avg_stt:.0f}ms")
        print(f"  Average Translation: {avg_translation:.0f}ms")
        print(f"  Average TTS: {avg_tts:.0f}ms")
        print(f"  Average End-to-End: {avg_e2e:.0f}ms")
        print(f"  Max End-to-End: {report['latency_metrics']['max_end_to_end_ms']:.0f}ms")
        print(f"  Min End-to-End: {report['latency_metrics']['min_end_to_end_ms']:.0f}ms")
        print()
        
        if failed:
            print("FAILED TESTS:")
            for r in failed:
                print(f"  - {r.test_name}")
                for err in r.errors:
                    print(f"    Error: {err}")
            print()
        
        # Benchmark evaluation
        print("BENCHMARK EVALUATION:")
        if report['success_rate'] >= 90:
            print("  ✓ Pipeline Validation: 10/10 (90%+ success rate)")
        elif report['success_rate'] >= 80:
            print("  ○ Pipeline Validation: 8/10 (80-90% success rate)")
        else:
            print("  ✗ Pipeline Validation: <8/10 (<80% success rate)")
        
        if avg_e2e < 1000:
            print("  ✓ Latency: 10/10 (<1s average)")
        elif avg_e2e < 2000:
            print("  ○ Latency: 8/10 (1-2s average)")
        else:
            print("  ✗ Latency: <8/10 (>2s average)")
        
        return report


async def main():
    parser = argparse.ArgumentParser(description="Test real device pipeline")
    parser.add_argument("--backend-url", required=True, help="Backend URL (e.g., http://localhost:8000)")
    parser.add_argument("--token", required=True, help="Authentication token")
    parser.add_argument("--test-audio-dir", default="models", help="Directory for test audio files")
    
    args = parser.parse_args()
    
    tester = RealDevicePipelineTester(
        backend_url=args.backend_url,
        token=args.token,
        test_audio_dir=args.test_audio_dir,
    )
    
    report = await tester.run_test_suite()
    
    # Save report to file
    report_file = Path("test_reports") / f"pipeline_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    report_file.parent.mkdir(exist_ok=True)
    with open(report_file, "w") as f:
        json.dump(report, f, indent=2)
    
    print(f"\nReport saved to: {report_file}")
    
    # Exit with error code if tests failed
    sys.exit(0 if report['success_rate'] >= 80 else 1)


if __name__ == "__main__":
    asyncio.run(main())
