"""Approval queue for human confirmation of high-risk actions."""

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
        self._submit_count = 0
        self._approve_count = 0
        self._deny_count = 0
        self._expire_count = 0
        self._error_count = 0
        self._initialize_db()
        logger.info(f"ApprovalQueue initialized with db_path={self.db_path}, ttl_hours={ttl_hours}")

    def _initialize_db(self) -> None:
        try:
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
                conn.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_risk_level 
                    ON approval_requests(risk_level)
                    """
                )
                conn.commit()
            logger.debug("ApprovalQueue database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize ApprovalQueue database: {e}", exc_info=True)
            raise

    def submit(self, request: ApprovalRequest) -> ApprovalRequest:
        """Submit a new approval request."""
        start_time = time.time()
        try:
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
            self._submit_count += 1
            logger.info(f"Approval request submitted: {request.request_id} (type={request.request_type}, risk={request.risk_level})")
            return request
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to submit approval request: {e}", exc_info=True)
            raise

    def approve(
        self, request_id: str, reviewed_by: str, review_notes: str = ""
    ) -> ApprovalRequest | None:
        """Approve a pending request."""
        start_time = time.time()
        try:
            result = self._update_status(
                request_id, ApprovalStatus.APPROVED, reviewed_by, review_notes
            )
            if result:
                self._approve_count += 1
                logger.info(f"Approval request approved: {request_id} by {reviewed_by}")
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to approve request {request_id}: {e}", exc_info=True)
            raise

    def deny(
        self, request_id: str, reviewed_by: str, review_notes: str = ""
    ) -> ApprovalRequest | None:
        """Deny a pending request."""
        start_time = time.time()
        try:
            result = self._update_status(
                request_id, ApprovalStatus.DENIED, reviewed_by, review_notes
            )
            if result:
                self._deny_count += 1
                logger.info(f"Approval request denied: {request_id} by {reviewed_by}")
            return result
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to deny request {request_id}: {e}", exc_info=True)
            raise

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
                    logger.warning(f"No pending request found for update: {request_id}")
                    return None
                conn.commit()
        return self.get_by_id(request_id)

    def get_by_id(self, request_id: str) -> ApprovalRequest | None:
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.execute(
                    "SELECT * FROM approval_requests WHERE request_id = ?", (request_id,)
                )
                row = cursor.fetchone()
                if row is None:
                    logger.debug(f"Request not found: {request_id}")
                    return None
                return self._row_to_request(row)
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get request {request_id}: {e}", exc_info=True)
            raise

    def list_pending(self, limit: int = 100) -> list[ApprovalRequest]:
        """List all pending approval requests."""
        try:
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
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list pending requests: {e}", exc_info=True)
            raise

    def list_by_session(
        self, session_id: str, limit: int = 100
    ) -> list[ApprovalRequest]:
        """List approval requests for a specific session."""
        try:
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
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list requests for session {session_id}: {e}", exc_info=True)
            raise

    def _expire_old_requests(self) -> None:
        """Mark expired requests as expired."""
        try:
            now = datetime.now(timezone.utc).isoformat()
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    """
                    UPDATE approval_requests 
                    SET status = ? 
                    WHERE status = ? AND expires_at < ?
                    """,
                    (ApprovalStatus.EXPIRED.value, ApprovalStatus.PENDING.value, now),
                )
                expired_count = cursor.rowcount
                conn.commit()
                if expired_count > 0:
                    self._expire_count += expired_count
                    logger.info(f"Expired {expired_count} approval requests")
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to expire old requests: {e}", exc_info=True)

    def _row_to_request(self, row: sqlite3.Row) -> ApprovalRequest:
        try:
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
        except Exception as e:
            logger.error(f"Failed to parse row to ApprovalRequest: {e}", exc_info=True)
            raise

    def get_statistics(self) -> dict[str, Any]:
        """Get approval queue statistics."""
        try:
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

                cursor = conn.execute(
                    "SELECT request_type, COUNT(*) FROM approval_requests GROUP BY request_type"
                )
                by_type = {row[0]: row[1] for row in cursor.fetchall()}

                return {
                    "db_path": str(self.db_path),
                    "ttl_hours": self.ttl_hours,
                    "total_requests": total,
                    "by_status": by_status,
                    "by_risk_level": by_risk,
                    "by_type": by_type,
                    "submit_count": self._submit_count,
                    "approve_count": self._approve_count,
                    "deny_count": self._deny_count,
                    "expire_count": self._expire_count,
                    "error_count": self._error_count,
                    "approval_rate": self._approve_count / self._submit_count if self._submit_count > 0 else 0,
                }
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {
                "db_path": str(self.db_path),
                "error": str(e),
                "submit_count": self._submit_count,
                "approve_count": self._approve_count,
                "deny_count": self._deny_count,
                "expire_count": self._expire_count,
                "error_count": self._error_count,
            }
