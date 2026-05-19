"""Trace viewer for NAIA event logs with drift detection."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class TraceEvent(BaseModel):
    """A single trace event from the event log."""

    event_id: str
    event_type: str
    module: str
    session_id: str
    timestamp: datetime
    details: dict[str, Any] = Field(default_factory=dict)


class DriftDetectionResult(BaseModel):
    """Result from drift detection analysis."""

    has_drift: bool
    drift_metrics: dict[str, float] = Field(default_factory=dict)
    drift_detected_in: list[str] = Field(default_factory=list)
    baseline_period: tuple[datetime, datetime]
    comparison_period: tuple[datetime, datetime]
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TraceViewer:
    """Viewer for NAIA event traces with drift detection capabilities."""

    def __init__(self, db_path: str | Path = "runtime/events.sqlite3") -> None:
        """
        Initialize the trace viewer.

        Args:
            db_path: Path to the SQLite database containing event logs
        """
        self.db_path = Path(db_path)
        if not self.db_path.exists():
            logger.warning(f"Event database not found: {self.db_path}")

    def get_session_trace(self, session_id: str) -> list[TraceEvent]:
        """
        Get all events for a specific session.

        Args:
            session_id: Session identifier

        Returns:
            List of trace events in chronological order
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """SELECT event_id, event_type, module, session_id, timestamp, details
               FROM events
               WHERE session_id = ?
               ORDER BY timestamp""",
            (session_id,),
        )

        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            event_id, event_type, module, session_id, timestamp_str, details_str = row
            import json

            events.append(
                TraceEvent(
                    event_id=event_id,
                    event_type=event_type,
                    module=module,
                    session_id=session_id,
                    timestamp=datetime.fromisoformat(timestamp_str),
                    details=json.loads(details_str) if details_str else {},
                )
            )

        return events

    def get_recent_traces(
        self, limit: int = 100, event_type: str | None = None
    ) -> list[TraceEvent]:
        """
        Get recent trace events.

        Args:
            limit: Maximum number of events to return
            event_type: Filter by event type if specified

        Returns:
            List of trace events
        """
        if not self.db_path.exists():
            return []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if event_type:
            cursor.execute(
                """SELECT event_id, event_type, module, session_id, timestamp, details
                   FROM events
                   WHERE event_type = ?
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (event_type, limit),
            )
        else:
            cursor.execute(
                """SELECT event_id, event_type, module, session_id, timestamp, details
                   FROM events
                   ORDER BY timestamp DESC
                   LIMIT ?""",
                (limit,),
            )

        rows = cursor.fetchall()
        conn.close()

        events = []
        for row in rows:
            event_id, event_type, module, session_id, timestamp_str, details_str = row
            import json

            events.append(
                TraceEvent(
                    event_id=event_id,
                    event_type=event_type,
                    module=module,
                    session_id=session_id,
                    timestamp=datetime.fromisoformat(timestamp_str),
                    details=json.loads(details_str) if details_str else {},
                )
            )

        return events

    def detect_drift(
        self,
        baseline_days: int = 7,
        comparison_days: int = 1,
        drift_threshold: float = 0.2,
    ) -> DriftDetectionResult:
        """
        Detect drift in system behavior by comparing recent events to baseline.

        Args:
            baseline_days: Number of days for baseline period
            comparison_days: Number of days for comparison period
            drift_threshold: Threshold for detecting significant drift (0.0-1.0)

        Returns:
            Drift detection result
        """
        if not self.db_path.exists():
            return DriftDetectionResult(
                has_drift=False,
                baseline_period=(datetime.now(timezone.utc), datetime.now(timezone.utc)),
                comparison_period=(datetime.now(timezone.utc), datetime.now(timezone.utc)),
            )

        now = datetime.now(timezone.utc)
        baseline_start = now - timedelta(days=baseline_days)
        baseline_end = now - timedelta(days=comparison_days)
        comparison_start = now - timedelta(days=comparison_days)
        comparison_end = now

        # Get baseline metrics
        baseline_metrics = self._calculate_period_metrics(baseline_start, baseline_end)
        comparison_metrics = self._calculate_period_metrics(comparison_start, comparison_end)

        # Compare metrics
        drift_metrics = {}
        drift_detected_in = []

        for metric_name in baseline_metrics:
            baseline_value = baseline_metrics[metric_name]
            comparison_value = comparison_metrics.get(metric_name, 0)

            if baseline_value > 0:
                drift = abs(comparison_value - baseline_value) / baseline_value
                drift_metrics[metric_name] = drift

                if drift > drift_threshold:
                    drift_detected_in.append(metric_name)

        has_drift = len(drift_detected_in) > 0

        return DriftDetectionResult(
            has_drift=has_drift,
            drift_metrics=drift_metrics,
            drift_detected_in=drift_detected_in,
            baseline_period=(baseline_start, baseline_end),
            comparison_period=(comparison_start, comparison_end),
        )

    def _calculate_period_metrics(
        self, start: datetime, end: datetime
    ) -> dict[str, float]:
        """Calculate metrics for a time period."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        metrics = {}

        # Total events
        cursor.execute(
            """SELECT COUNT(*) FROM events WHERE timestamp BETWEEN ? AND ?""",
            (start.isoformat(), end.isoformat()),
        )
        metrics["total_events"] = float(cursor.fetchone()[0])

        # Event type distribution
        cursor.execute(
            """SELECT event_type, COUNT(*) FROM events
               WHERE timestamp BETWEEN ? AND ?
               GROUP BY event_type""",
            (start.isoformat(), end.isoformat()),
        )
        event_counts = dict(cursor.fetchall())
        for event_type, count in event_counts.items():
            metrics[f"event_type_{event_type}"] = float(count)

        # Module distribution
        cursor.execute(
            """SELECT module, COUNT(*) FROM events
               WHERE timestamp BETWEEN ? AND ?
               GROUP BY module""",
            (start.isoformat(), end.isoformat()),
        )
        module_counts = dict(cursor.fetchall())
        for module, count in module_counts.items():
            metrics[f"module_{module}"] = float(count)

        # Error rate (RISK_DETECTED events)
        cursor.execute(
            """SELECT COUNT(*) FROM events
               WHERE event_type = 'RISK_DETECTED' AND timestamp BETWEEN ? AND ?""",
            (start.isoformat(), end.isoformat()),
        )
        risk_count = cursor.fetchone()[0]
        metrics["error_rate"] = (
            risk_count / metrics["total_events"] if metrics["total_events"] > 0 else 0.0
        )

        conn.close()
        return metrics

    def get_statistics(self) -> dict[str, Any]:
        """Get overall statistics from the event log."""
        if not self.db_path.exists():
            return {}

        conn = sqlite3.connect(self.db_path)
        # Get statistics from the existing get_statistics method
        try:
            from runtime.events import EventLog
            event_log = EventLog(db_path=str(self.db_path))
            stats = event_log.get_statistics()
            conn.close()
            return stats
        except Exception as exc:
            logger.warning(f"Failed to get statistics: {exc}")
            conn.close()
            return {}

    def visualize_trace(self, session_id: str) -> str:
        """
        Generate a text visualization of a session trace.

        Args:
            session_id: Session identifier

        Returns:
            Text visualization of the trace
        """
        events = self.get_session_trace(session_id)

        if not events:
            return f"No events found for session {session_id}"

        lines = [f"Trace for session: {session_id}"]
        lines.append("=" * 60)

        for event in events:
            lines.append(f"\n[{event.timestamp}] {event.event_type}")
            lines.append(f"  Module: {event.module}")
            if event.details:
                lines.append(f"  Details: {event.details}")

        return "\n".join(lines)
