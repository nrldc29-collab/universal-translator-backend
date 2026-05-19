"""Decision log for tracking governance decisions."""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


class DecisionType(StrEnum):
    TOOL_EXECUTION = "tool_execution"
    AGENT_ACTION = "agent_action"
    MEMORY_MUTATION = "memory_mutation"
    SYSTEM_CHANGE = "system_change"
    RISK_OVERRIDE = "risk_override"


class DecisionOutcome(StrEnum):
    APPROVED = "approved"
    DENIED = "denied"
    ESCALATED = "escalated"
    BLOCKED = "blocked"


class DecisionRecord(BaseModel):
    decision_id: str = Field(default_factory=lambda: str(uuid4()))
    decision_type: DecisionType
    outcome: DecisionOutcome
    risk_level: str
    session_id: str | None = None
    requested_by: str | None = None
    reviewed_by: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class DecisionLog:
    """Persistent decision log using SQLite."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        if db_path is None:
            db_path = Path.cwd() / "governance" / "decisions.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS decisions (
                    decision_id TEXT PRIMARY KEY,
                    decision_type TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    session_id TEXT,
                    requested_by TEXT,
                    reviewed_by TEXT,
                    timestamp TEXT NOT NULL,
                    details TEXT,
                    reason TEXT,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON decisions(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON decisions(timestamp)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_decision_type 
                ON decisions(decision_type)
                """
            )
            conn.commit()

    def record(self, record: DecisionRecord) -> DecisionRecord:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO decisions 
                    (decision_id, decision_type, outcome, risk_level, session_id, 
                     requested_by, reviewed_by, timestamp, details, reason, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        record.decision_id,
                        record.decision_type.value,
                        record.outcome.value,
                        record.risk_level,
                        record.session_id,
                        record.requested_by,
                        record.reviewed_by,
                        record.timestamp.isoformat(),
                        json.dumps(record.details) if record.details else None,
                        record.reason,
                        json.dumps(record.metadata) if record.metadata else None,
                    ),
                )
                conn.commit()
        return record

    def get_by_id(self, decision_id: str) -> DecisionRecord | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_record(row)

    def list_by_session(
        self, session_id: str, limit: int = 100
    ) -> list[DecisionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM decisions 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit),
            )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def list_recent(self, limit: int = 100) -> list[DecisionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM decisions 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (limit,),
            )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def list_by_type(
        self, decision_type: DecisionType, limit: int = 100
    ) -> list[DecisionRecord]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM decisions 
                WHERE decision_type = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (decision_type.value, limit),
            )
            return [self._row_to_record(row) for row in cursor.fetchall()]

    def _row_to_record(self, row: sqlite3.Row) -> DecisionRecord:
        return DecisionRecord(
            decision_id=row["decision_id"],
            decision_type=DecisionType(row["decision_type"]),
            outcome=DecisionOutcome(row["outcome"]),
            risk_level=row["risk_level"],
            session_id=row["session_id"],
            requested_by=row["requested_by"],
            reviewed_by=row["reviewed_by"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            details=json.loads(row["details"]) if row["details"] else {},
            reason=row["reason"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def get_statistics(self) -> dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM decisions")
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT outcome, COUNT(*) FROM decisions GROUP BY outcome"
            )
            by_outcome = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                "SELECT decision_type, COUNT(*) FROM decisions GROUP BY decision_type"
            )
            by_type = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_decisions": total,
                "by_outcome": by_outcome,
                "by_type": by_type,
            }
