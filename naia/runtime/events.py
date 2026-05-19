"""Observable runtime events for the NAIA cognitive runtime kernel."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


logger = logging.getLogger("naia.runtime")


class EventType(StrEnum):
    INPUT_RECEIVED = "INPUT_RECEIVED"
    SESSION_CREATED = "SESSION_CREATED"
    LIFECYCLE_TRANSITIONED = "LIFECYCLE_TRANSITIONED"
    INPUT_NORMALIZED = "INPUT_NORMALIZED"
    INTENT_CLASSIFIED = "INTENT_CLASSIFIED"
    ROUTE_SELECTED = "ROUTE_SELECTED"
    RISK_PRECHECKED = "RISK_PRECHECKED"
    RISK_DETECTED = "RISK_DETECTED"
    COGNITIVE_DISPATCHED = "COGNITIVE_DISPATCHED"
    FINAL_RESPONSE_RENDERED = "FINAL_RESPONSE_RENDERED"
    RESPONSE_SYNTHESIZED = "RESPONSE_SYNTHESIZED"
    TELEMETRY_RECORDED = "TELEMETRY_RECORDED"
    TOOL_EXECUTED = "TOOL_EXECUTED"
    AGENT_CREATED = "AGENT_CREATED"
    AGENT_PLANNED = "AGENT_PLANNED"
    AGENT_TASK_COMPLETED = "AGENT_TASK_COMPLETED"
    AGENT_FAILED = "AGENT_FAILED"
    AGENT_RECOVERED = "AGENT_RECOVERED"
    AGENT_COMPLETED = "AGENT_COMPLETED"
    MEMORY_RETRIEVED = "MEMORY_RETRIEVED"
    MEMORY_WRITTEN = "MEMORY_WRITTEN"
    MEMORY_VALIDATED = "MEMORY_VALIDATED"
    MEMORY_DECAYED = "MEMORY_DECAYED"
    SCHEDULER_TASK_STARTED = "SCHEDULER_TASK_STARTED"
    SCHEDULER_TASK_COMPLETED = "SCHEDULER_TASK_COMPLETED"
    SCHEDULER_TASK_FAILED = "SCHEDULER_TASK_FAILED"
    FAILURE_OCCURRED = "FAILURE_OCCURRED"
    RECOVERY_TRIGGERED = "RECOVERY_TRIGGERED"
    SESSION_COMPLETED = "SESSION_COMPLETED"


class RuntimeEvent(BaseModel):
    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event: EventType
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    module: str
    session_id: str | None = None
    latency_ms: float | None = None
    state_snapshot: dict[str, Any] | None = None
    details: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class EventLog:
    """Persistent event log using SQLite for observability per Constitution Section 8."""

    def __init__(self, db_path: str | Path | None = None, max_events: int = 10000) -> None:
        if db_path is None:
            db_path = Path.cwd() / "runtime" / "events.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.max_events = max_events
        self._lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self) -> None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        event_id TEXT PRIMARY KEY,
                        event TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        module TEXT NOT NULL,
                        session_id TEXT,
                        latency_ms REAL,
                        state_snapshot TEXT,
                        details TEXT,
                        error TEXT
                    )
                    """
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_session_id ON events(session_id)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_timestamp ON events(timestamp)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_event_type ON events(event)"
                )
                conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_module ON events(module)"
                )
                conn.commit()
        except sqlite3.OperationalError as exc:
            logger.error("event_db_init_failed path=%s: %s", self.db_path, exc)

    async def append(self, event: RuntimeEvent) -> RuntimeEvent:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO events
                    (event_id, event, timestamp, module, session_id, latency_ms,
                     state_snapshot, details, error)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.event_id,
                        event.event.value,
                        event.timestamp.isoformat(),
                        event.module,
                        event.session_id,
                        event.latency_ms,
                        json.dumps(event.state_snapshot) if event.state_snapshot else None,
                        json.dumps(event.details) if event.details else None,
                        event.error,
                    ),
                )
                conn.commit()

        self._prune_old_events()

        logger.info(
            "runtime_event",
            extra={
                "event": event.event.value,
                "module": event.module,
                "session_id": event.session_id,
                "latency_ms": event.latency_ms,
                "error": event.error,
            },
        )
        return event

    def _prune_old_events(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM events")
            count = cursor.fetchone()[0]
            if count > self.max_events:
                conn.execute(
                    """
                    DELETE FROM events
                    WHERE event_id IN (
                        SELECT event_id FROM events
                        ORDER BY timestamp ASC
                        LIMIT ?
                    )
                    """,
                    (count - self.max_events,),
                )
                conn.commit()

    async def emit(
        self,
        event: EventType,
        *,
        module: str,
        session_id: str | None = None,
        latency_ms: float | None = None,
        state_snapshot: dict[str, Any] | None = None,
        details: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> RuntimeEvent:
        return await self.append(
            RuntimeEvent(
                event=event,
                module=module,
                session_id=session_id,
                latency_ms=latency_ms,
                state_snapshot=state_snapshot,
                details=details or {},
                error=error,
            )
        )

    async def list_events(
        self,
        *,
        limit: int = 100,
        session_id: str | None = None,
        event_type: str | None = None,
    ) -> list[RuntimeEvent]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            query = "SELECT * FROM events"
            conditions: list[str] = []
            params: list[Any] = []

            if session_id is not None:
                conditions.append("session_id = ?")
                params.append(session_id)

            if event_type is not None:
                conditions.append("event = ?")
                params.append(event_type)

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)

            cursor = conn.execute(query, params)
            return [self._row_to_event(row) for row in cursor.fetchall()]

    async def snapshot(self, *, limit: int = 100) -> dict[str, Any]:
        events = await self.list_events(limit=limit)
        return {
            "count": len(events),
            "events": [event.model_dump(mode="json") for event in events],
        }

    def _row_to_event(self, row: sqlite3.Row) -> RuntimeEvent:
        return RuntimeEvent(
            event_id=row["event_id"],
            event=EventType(row["event"]),
            timestamp=datetime.fromisoformat(row["timestamp"]),
            module=row["module"],
            session_id=row["session_id"],
            latency_ms=row["latency_ms"],
            state_snapshot=json.loads(row["state_snapshot"]) if row["state_snapshot"] else None,
            details=json.loads(row["details"]) if row["details"] else {},
            error=row["error"],
        )

    def get_statistics(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM events")
            total = cursor.fetchone()[0]

            cursor = conn.execute("SELECT event, COUNT(*) FROM events GROUP BY event")
            by_event = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute("SELECT module, COUNT(*) FROM events GROUP BY module")
            by_module = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_events": total,
                "by_event_type": by_event,
                "by_module": by_module,
            }
