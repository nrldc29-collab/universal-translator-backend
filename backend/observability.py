import json
import os
from pathlib import Path
from threading import RLock
from time import time


class Observability:
    def __init__(self):
        self.events_path = Path(os.getenv("EVENT_LOG_PATH", "logs/events.jsonl"))
        self.events_path.parent.mkdir(parents=True, exist_ok=True)
        self.counters = {
            "translation_failures_total": 0,
            "websocket_disconnects_total": 0,
            "websocket_errors_total": 0,
            "websocket_connects_total": 0,
            "vad_speech_total": 0,
            "vad_silence_total": 0,
            "vad_errors_total": 0,
            "tts_playback_chunks_total": 0,
            "tts_failures_total": 0,
        }
        self.latencies = {}
        self._lock = RLock()

    def record_event(self, event_type: str, **fields) -> None:
        event = {"timestamp": time(), "type": event_type, **fields}
        try:
            with self._lock:
                self.events_path.parent.mkdir(parents=True, exist_ok=True)
                with self.events_path.open("a", encoding="utf-8") as file:
                    file.write(json.dumps(event, default=str) + "\n")
        except OSError:
            self.increment("event_log_write_failures_total")

    def increment(self, name: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[name] = self.counters.get(name, 0) + amount

    def observe_latency(self, name: str, seconds: float) -> None:
        with self._lock:
            values = self.latencies.setdefault(name, [])
            values.append(seconds)
            self.latencies[name] = values[-200:]

    def snapshot(self) -> dict:
        with self._lock:
            counters = dict(self.counters)
            latencies = {name: list(values) for name, values in self.latencies.items()}
        return {
            "counters": counters,
            "latency_seconds": {
                name: {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 4) if values else 0,
                    "max": round(max(values), 4) if values else 0,
                }
                for name, values in latencies.items()
            },
            "event_log_path": str(self.events_path),
        }

    def stabilization_snapshot(self) -> dict:
        snapshot = self.snapshot()
        return {
            "response_latency": snapshot["latency_seconds"],
            "connection_stability": {
                "connects": snapshot["counters"].get("websocket_connects_total", 0),
                "disconnects": snapshot["counters"].get("websocket_disconnects_total", 0),
                "errors": snapshot["counters"].get("websocket_errors_total", 0),
            },
            "speech_detection": {
                "speech": snapshot["counters"].get("vad_speech_total", 0),
                "silence": snapshot["counters"].get("vad_silence_total", 0),
                "errors": snapshot["counters"].get("vad_errors_total", 0),
            },
            "tts_playback": {
                "chunks": snapshot["counters"].get("tts_playback_chunks_total", 0),
                "failures": snapshot["counters"].get("tts_failures_total", 0),
            },
            "event_log_path": str(self.events_path),
        }

    def prometheus(self, gpu_queue: dict | None = None) -> str:
        lines = []
        snapshot = self.snapshot()
        for name, value in snapshot["counters"].items():
            lines.append(f"anai_translator_{name} {value}")
        for name, values in snapshot["latency_seconds"].items():
            lines.append(f"anai_translator_{name}_latency_seconds_count {values['count']}")
            lines.append(f"anai_translator_{name}_latency_seconds_avg {values['avg']}")
            lines.append(f"anai_translator_{name}_latency_seconds_max {values['max']}")
        try:
            gpu_memory = float(os.getenv("GPU_MEMORY_USED_MB", "0"))
        except ValueError:
            gpu_memory = 0.0
        try:
            gpu_utilization = float(os.getenv("GPU_UTILIZATION_PERCENT", "0"))
        except ValueError:
            gpu_utilization = 0.0
        lines.append(f"anai_translator_gpu_memory_used_mb {gpu_memory}")
        lines.append(f"anai_translator_gpu_utilization_percent {gpu_utilization}")
        if gpu_queue:
            for key, value in gpu_queue.items():
                lines.append(f"anai_translator_gpu_queue_{key} {value}")
        return "\n".join(lines) + "\n"


observability = Observability()
