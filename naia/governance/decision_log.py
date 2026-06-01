"""Decision log for tracking governance decisions."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from datetime import datetime, timezone
from enum import StrEnum
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


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
        self._record_count = 0
        self._error_count = 0
        self._initialize_db()
        logger.info(f"DecisionLog initialized with db_path={self.db_path}")

    def _initialize_db(self) -> None:
        try:
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
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_outcome 
                    ON decisions(outcome)
                    """
                )
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_risk_level 
                    ON decisions(risk_level)
                    """
                )
                conn.commit()
            logger.debug("DecisionLog database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize DecisionLog database: {e}", exc_info=True)
            raise

    def record(self, record: DecisionRecord) -> DecisionRecord:
        try:
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
            self._record_count += 1
            logger.info(f"Decision recorded: {record.decision_id} (type={record.decision_type}, outcome={record.outcome})")
            return record
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to record decision: {e}", exc_info=True)
            raise

    def get_by_id(self, decision_id: str) -> DecisionRecord | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM decisions WHERE decision_id = ?", (decision_id,)
                )
                row = cursor.fetchone()
                if row is None:
                    logger.debug(f"Decision not found: {decision_id}")
                    return None
                return self._row_to_record(row)
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get decision {decision_id}: {e}", exc_info=True)
            raise

    def list_by_session(
        self, session_id: str, limit: int = 100
    ) -> list[DecisionRecord]:
        try:
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
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list decisions for session {session_id}: {e}", exc_info=True)
            raise

    def list_recent(self, limit: int = 100) -> list[DecisionRecord]:
        try:
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
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list recent decisions: {e}", exc_info=True)
            raise

    def list_by_type(
        self, decision_type: DecisionType, limit: int = 100
    ) -> list[DecisionRecord]:
        try:
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
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list decisions by type {decision_type}: {e}", exc_info=True)
            raise

    def list_by_risk_level(self, risk_level: str, limit: int = 100) -> list[DecisionRecord]:
        """List decisions by risk level."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    """
                    SELECT * FROM decisions 
                    WHERE risk_level = ? 
                    ORDER BY timestamp DESC 
                    LIMIT ?
                    """,
                    (risk_level, limit),
                )
                return [self._row_to_record(row) for row in cursor.fetchall()]
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list decisions by risk level {risk_level}: {e}", exc_info=True)
            raise

    def _row_to_record(self, row: sqlite3.Row) -> DecisionRecord:
        try:
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
        except Exception as e:
            logger.error(f"Failed to parse row to DecisionRecord: {e}", exc_info=True)
            raise

    def get_statistics(self) -> dict[str, Any]:
        """Get decision log statistics."""
        try:
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

                cursor = conn.execute(
                    "SELECT risk_level, COUNT(*) FROM decisions GROUP BY risk_level"
                )
                by_risk = {row[0]: row[1] for row in cursor.fetchall()}

                # Calculate approval rate
                approved_count = by_outcome.get("approved", 0)
                approval_rate = approved_count / total if total > 0 else 0

                return {
                    "db_path": str(self.db_path),
                    "total_decisions": total,
                    "by_outcome": by_outcome,
                    "by_type": by_type,
                    "by_risk_level": by_risk,
                    "record_count": self._record_count,
                    "error_count": self._error_count,
                    "approval_rate": approval_rate,
                }
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {
                "db_path": str(self.db_path),
                "error": str(e),
                "record_count": self._record_count,
                "error_count": self._error_count,
            }
