import json
import os
from pathlib import Path
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

    def record_event(self, event_type: str, **fields) -> None:
        event = {"timestamp": time(), "type": event_type, **fields}
        with self.events_path.open("a", encoding="utf-8") as file:
            file.write(json.dumps(event, default=str) + "\n")

    def increment(self, name: str, amount: int = 1) -> None:
        self.counters[name] = self.counters.get(name, 0) + amount

    def observe_latency(self, name: str, seconds: float) -> None:
        values = self.latencies.setdefault(name, [])
        values.append(seconds)
        self.latencies[name] = values[-200:]

    def snapshot(self) -> dict:
        return {
            "counters": self.counters,
            "latency_seconds": {
                name: {
                    "count": len(values),
                    "avg": round(sum(values) / len(values), 4) if values else 0,
                    "max": round(max(values), 4) if values else 0,
                }
                for name, values in self.latencies.items()
            },
            "event_log_path": str(self.events_path),
        }

    def stabilization_snapshot(self) -> dict:
        return {
            "response_latency": self.snapshot()["latency_seconds"],
            "connection_stability": {
                "connects": self.counters.get("websocket_connects_total", 0),
                "disconnects": self.counters.get("websocket_disconnects_total", 0),
                "errors": self.counters.get("websocket_errors_total", 0),
            },
            "speech_detection": {
                "speech": self.counters.get("vad_speech_total", 0),
                "silence": self.counters.get("vad_silence_total", 0),
                "errors": self.counters.get("vad_errors_total", 0),
            },
            "tts_playback": {
                "chunks": self.counters.get("tts_playback_chunks_total", 0),
                "failures": self.counters.get("tts_failures_total", 0),
            },
            "event_log_path": str(self.events_path),
        }

    def prometheus(self, gpu_queue: dict | None = None) -> str:
        lines = []
        for name, value in self.counters.items():
            lines.append(f"universal_translator_{name} {value}")
        for name, values in self.latencies.items():
            lines.append(f"universal_translator_{name}_latency_seconds_count {len(values)}")
            lines.append(f"universal_translator_{name}_latency_seconds_avg {sum(values) / len(values) if values else 0}")
            lines.append(f"universal_translator_{name}_latency_seconds_max {max(values) if values else 0}")
        lines.append(f"universal_translator_gpu_memory_used_mb {float(os.getenv('GPU_MEMORY_USED_MB', '0'))}")
        lines.append(f"universal_translator_gpu_utilization_percent {float(os.getenv('GPU_UTILIZATION_PERCENT', '0'))}")
        if gpu_queue:
            for key, value in gpu_queue.items():
                lines.append(f"universal_translator_gpu_queue_{key} {value}")
        return "\n".join(lines) + "\n"


observability = Observability()
