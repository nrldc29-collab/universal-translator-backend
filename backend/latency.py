"""End-to-end latency tracking for the full translation pipeline.

Tracks per-stage timing (VAD, STT, Translation, TTS, total) with EWMA smoothing,
percentile computation, and a history buffer for diagnostics.
"""

import logging
import time
from collections import deque
from dataclasses import dataclass, field
from threading import Lock

logger = logging.getLogger("anai_translator.latency")


@dataclass
class StageMetrics:
    """Rolling metrics for a single pipeline stage."""
    name: str
    count: int = 0
    total_ms: float = 0.0
    avg_ms: float = 0.0
    min_ms: float = float("inf")
    max_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    last_ms: float = 0.0
    _history: deque = field(default_factory=lambda: deque(maxlen=200))

    def record(self, ms):
        if ms is None or ms < 0:
            return
        self.count += 1
        self.total_ms += ms
        self.last_ms = ms
        self.min_ms = min(self.min_ms, ms)
        self.max_ms = max(self.max_ms, ms)
        self.avg_ms = (self.avg_ms * 0.8) + (ms * 0.2) if self.count > 1 else ms
        self._history.append(ms)
        self._recompute_percentiles()

    def _recompute_percentiles(self):
        if not self._history:
            return
        sorted_h = sorted(self._history)
        n = len(sorted_h)
        self.p50_ms = sorted_h[int(n * 0.50)]
        self.p95_ms = sorted_h[min(int(n * 0.95), n - 1)]
        self.p99_ms = sorted_h[min(int(n * 0.99), n - 1)]

    def snapshot(self):
        return {
            "name": self.name,
            "count": self.count,
            "avg_ms": round(self.avg_ms, 1),
            "min_ms": round(self.min_ms, 1) if self.min_ms != float("inf") else 0,
            "max_ms": round(self.max_ms, 1),
            "p50_ms": round(self.p50_ms, 1),
            "p95_ms": round(self.p95_ms, 1),
            "p99_ms": round(self.p99_ms, 1),
            "last_ms": round(self.last_ms, 1),
        }


@dataclass
class PipelineRun:
    """A single end-to-end pipeline execution with per-stage timing."""
    run_id: str
    started_at: float
    stages: dict = field(default_factory=dict)
    total_ms: float = 0.0
    speaker: str = ""
    source_lang: str = ""
    target_lang: str = ""

    def record_stage(self, stage, ms):
        self.stages[stage] = ms

    def finalize(self):
        self.total_ms = sum(self.stages.values())

    def snapshot(self):
        return {
            "run_id": self.run_id,
            "total_ms": round(self.total_ms, 1),
            "stages": {k: round(v, 1) for k, v in self.stages.items()},
            "speaker": self.speaker,
            "source_lang": self.source_lang,
            "target_lang": self.target_lang,
        }


class LatencyEngine:
    """Full pipeline latency tracker with per-stage metrics and run history."""

    STAGES = ("mic_to_backend", "vad", "stt", "translation", "tts", "total")

    def __init__(self):
        self._lock = Lock()
        self._stage_metrics = {name: StageMetrics(name=name) for name in self.STAGES}
        self._runs = deque(maxlen=100)
        self._current_run = None
        # Legacy compatibility
        self.avg_stt = 0.0
        self.avg_translate = 0.0
        self.avg_tts = 0.0

    def update(self, stt=0.0, translate=0.0, tts=0.0):
        """Legacy update method for backward compatibility."""
        self.avg_stt = (self.avg_stt * 0.8) + (float(stt) * 0.2)
        self.avg_translate = (self.avg_translate * 0.8) + (float(translate) * 0.2)
        self.avg_tts = (self.avg_tts * 0.8) + (float(tts) * 0.2)
        if stt > 0:
            self.record_stage("stt", float(stt) * 1000)
        if translate > 0:
            self.record_stage("translation", float(translate) * 1000)
        if tts > 0:
            self.record_stage("tts", float(tts) * 1000)

    def total(self):
        """Legacy total method."""
        return float(self.avg_stt + self.avg_translate + self.avg_tts)

    def begin_run(self, run_id, speaker="", source_lang="", target_lang=""):
        """Start tracking a new pipeline run."""
        with self._lock:
            run = PipelineRun(
                run_id=run_id,
                started_at=time.monotonic(),
                speaker=speaker,
                source_lang=source_lang,
                target_lang=target_lang,
            )
            self._current_run = run
            return run

    def record_stage(self, stage, ms):
        """Record timing for a pipeline stage."""
        with self._lock:
            if stage not in self._stage_metrics:
                self._stage_metrics[stage] = StageMetrics(name=stage)
            self._stage_metrics[stage].record(ms)
            if self._current_run:
                self._current_run.record_stage(stage, ms)

    def end_run(self):
        """Finalize the current pipeline run and add to history."""
        with self._lock:
            run = self._current_run
            if run:
                run.finalize()
                total_ms = run.total_ms
                self._stage_metrics["total"].record(total_ms)
                self._runs.append(run)
                self._current_run = None
                logger.info(
                    "pipeline_run_complete run_id=%s total_ms=%.1f stages=%s",
                    run.run_id, total_ms,
                    {k: f"{v:.0f}ms" for k, v in run.stages.items()},
                )
            return run

    def snapshot(self):
        """Full latency snapshot for the /diagnostics and /latency endpoints."""
        with self._lock:
            recent_runs = [r.snapshot() for r in list(self._runs)[-10:]]
            stage_metrics = {name: m.snapshot() for name, m in self._stage_metrics.items()}
            total_metric = self._stage_metrics.get("total")
            return {
                "stages": stage_metrics,
                "recent_runs": recent_runs,
                "summary": {
                    "avg_total_ms": round(total_metric.avg_ms, 1) if total_metric and total_metric.count else 0,
                    "p50_total_ms": round(total_metric.p50_ms, 1) if total_metric and total_metric.count else 0,
                    "p95_total_ms": round(total_metric.p95_ms, 1) if total_metric and total_metric.count else 0,
                    "total_runs": total_metric.count if total_metric else 0,
                },
            }

    def health_assessment(self):
        """Return a health assessment of latency levels."""
        total = self._stage_metrics.get("total")
        if not total or total.count == 0:
            return {"status": "unknown", "message": "No pipeline runs recorded yet"}
        p95 = total.p95_ms
        if p95 < 1000:
            return {"status": "excellent", "p95_ms": round(p95, 1), "message": "Sub-second response time"}
        elif p95 < 2500:
            return {"status": "good", "p95_ms": round(p95, 1), "message": "Acceptable latency for real-time translation"}
        elif p95 < 5000:
            return {"status": "degraded", "p95_ms": round(p95, 1), "message": "Noticeable delay"}
        else:
            return {"status": "poor", "p95_ms": round(p95, 1), "message": "High latency -- pipeline needs optimization"}
