"""Approval queue for human confirmation of high-risk actions."""

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


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXPIRED = "expired"


class ApprovalRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: str(uuid4()))
    request_type: str
    risk_level: str
    session_id: str | None = None
    requested_by: str | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime | None = None
    status: ApprovalStatus = ApprovalStatus.PENDING
    details: dict[str, Any] = Field(default_factory=dict)
    reason: str = ""
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_notes: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)


class ApprovalQueue:
    """Persistent approval queue using SQLite."""

    def __init__(self, db_path: str | Path | None = None, ttl_hours: int = 24) -> None:
        if db_path is None:
            db_path = Path.cwd() / "governance" / "approvals.sqlite3"
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self.ttl_hours = ttl_hours
        self._initialize_db()

    def _initialize_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approval_requests (
                    request_id TEXT PRIMARY KEY,
                    request_type TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    session_id TEXT,
                    requested_by TEXT,
                    timestamp TEXT NOT NULL,
                    expires_at TEXT,
                    status TEXT NOT NULL,
                    details TEXT,
                    reason TEXT,
                    reviewed_by TEXT,
                    reviewed_at TEXT,
                    review_notes TEXT,
                    metadata TEXT
                )
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_session_id 
                ON approval_requests(session_id)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_status 
                ON approval_requests(status)
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_timestamp 
                ON approval_requests(timestamp)
                """
            )
            conn.commit()

    def submit(self, request: ApprovalRequest) -> ApprovalRequest:
        """Submit a new approval request."""
        if request.expires_at is None:
            request.expires_at = datetime.now(timezone.utc).replace(
                hour=23, minute=59, second=59
            )
        
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO approval_requests 
                    (request_id, request_type, risk_level, session_id, requested_by, 
                     timestamp, expires_at, status, details, reason, reviewed_by, 
                     reviewed_at, review_notes, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        request.request_id,
                        request.request_type,
                        request.risk_level,
                        request.session_id,
                        request.requested_by,
                        request.timestamp.isoformat(),
                        request.expires_at.isoformat(),
                        request.status.value,
                        json.dumps(request.details) if request.details else None,
                        request.reason,
                        request.reviewed_by,
                        request.reviewed_at.isoformat() if request.reviewed_at else None,
                        request.review_notes,
                        json.dumps(request.metadata) if request.metadata else None,
                    ),
                )
                conn.commit()
        return request

    def approve(
        self, request_id: str, reviewed_by: str, review_notes: str = ""
    ) -> ApprovalRequest | None:
        """Approve a pending request."""
        return self._update_status(
            request_id, ApprovalStatus.APPROVED, reviewed_by, review_notes
        )

    def deny(
        self, request_id: str, reviewed_by: str, review_notes: str = ""
    ) -> ApprovalRequest | None:
        """Deny a pending request."""
        return self._update_status(
            request_id, ApprovalStatus.DENIED, reviewed_by, review_notes
        )

    def _update_status(
        self,
        request_id: str,
        status: ApprovalStatus,
        reviewed_by: str,
        review_notes: str,
    ) -> ApprovalRequest | None:
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE approval_requests 
                    SET status = ?, reviewed_by = ?, reviewed_at = ?, review_notes = ?
                    WHERE request_id = ? AND status = ?
                    """,
                    (
                        status.value,
                        reviewed_by,
                        datetime.now(timezone.utc).isoformat(),
                        review_notes,
                        request_id,
                        ApprovalStatus.PENDING.value,
                    ),
                )
                if cursor.rowcount == 0:
                    return None
                conn.commit()
        return self.get_by_id(request_id)

    def get_by_id(self, request_id: str) -> ApprovalRequest | None:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
            )
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_request(row)

    def list_pending(self, limit: int = 100) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        self._expire_old_requests()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM approval_requests 
                WHERE status = ? 
                ORDER BY timestamp ASC 
                LIMIT ?
                """,
                (ApprovalStatus.PENDING.value, limit),
            )
            return [self._row_to_request(row) for row in cursor.fetchall()]

    def list_by_session(
        self, session_id: str, limit: int = 100
    ) -> list[ApprovalRequest]:
        """List approval requests for a specific session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                """
                SELECT * FROM approval_requests 
                WHERE session_id = ? 
                ORDER BY timestamp DESC 
                LIMIT ?
                """,
                (session_id, limit),
            )
            return [self._row_to_request(row) for row in cursor.fetchall()]

    def _expire_old_requests(self) -> None:
        """Mark expired requests as expired."""
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                UPDATE approval_requests 
                SET status = ? 
                WHERE status = ? AND expires_at < ?
                """,
                (ApprovalStatus.EXPIRED.value, ApprovalStatus.PENDING.value, now),
            )
            conn.commit()

    def _row_to_request(self, row: sqlite3.Row) -> ApprovalRequest:
        return ApprovalRequest(
            request_id=row["request_id"],
            request_type=row["request_type"],
            risk_level=row["risk_level"],
            session_id=row["session_id"],
            requested_by=row["requested_by"],
            timestamp=datetime.fromisoformat(row["timestamp"]),
            expires_at=datetime.fromisoformat(row["expires_at"]) if row["expires_at"] else None,
            status=ApprovalStatus(row["status"]),
            details=json.loads(row["details"]) if row["details"] else {},
            reason=row["reason"] or "",
            reviewed_by=row["reviewed_by"],
            reviewed_at=datetime.fromisoformat(row["reviewed_at"]) if row["reviewed_at"] else None,
            review_notes=row["review_notes"] or "",
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def get_statistics(self) -> dict[str, Any]:
        """Get approval queue statistics."""
        self._expire_old_requests()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM approval_requests")
            total = cursor.fetchone()[0]

            cursor = conn.execute(
                "SELECT status, COUNT(*) FROM approval_requests GROUP BY status"
            )
            by_status = {row[0]: row[1] for row in cursor.fetchall()}

            cursor = conn.execute(
                "SELECT risk_level, COUNT(*) FROM approval_requests GROUP BY risk_level"
            )
            by_risk = {row[0]: row[1] for row in cursor.fetchall()}

            return {
                "total_requests": total,
                "by_status": by_status,
                "by_risk_level": by_risk,
            }
