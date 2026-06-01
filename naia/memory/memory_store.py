"""SQLite memory persistence and vector search."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from memory.memory_policy import MemoryStatus, MemoryType, MemoryWriteCandidate

logger = logging.getLogger(__name__)


class MemoryRecord(BaseModel):
    memory_id: str
    memory_type: MemoryType
    content: str
    context: str = ""
    confidence: float = Field(ge=0.0, le=1.0)
    importance: float = Field(ge=0.0, le=1.0)
    source: str
    session_id: str | None = None
    status: MemoryStatus
    sensitivity: str = "normal"
    topic: str = "general"
    vector: list[float] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    decay_rate: float = Field(default=0.01, ge=0.0, le=1.0)
    created_at: datetime
    updated_at: datetime
    last_accessed: datetime | None = None
    last_verified: datetime | None = None


class MemorySearchResult(BaseModel):
    record: MemoryRecord
    similarity: float
    score: float


class MemoryStore:
    def __init__(self, db_path: str | Path | None = None) -> None:
        self.db_path = Path(db_path or Path("memory") / "naia_memory.sqlite3")
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._write_count = 0
        self._read_count = 0
        self._error_count = 0
        self._initialize()
        logger.info(f"MemoryStore initialized with db_path={self.db_path}")

    def write(
        self,
        candidate: MemoryWriteCandidate,
        *,
        vector: list[float],
        status: MemoryStatus,
        sensitivity: str,
        topic: str,
        decay_rate: float,
    ) -> MemoryRecord:
        start_time = time.time()
        try:
            now = datetime.now(timezone.utc)
            record = MemoryRecord(
                memory_id=str(uuid4()),
                memory_type=candidate.memory_type,
                content=candidate.content,
                context=candidate.context,
                confidence=candidate.confidence,
                importance=candidate.importance,
                source=candidate.source,
                session_id=candidate.session_id,
                status=status,
                sensitivity=sensitivity,
                topic=topic,
                vector=vector,
                metadata=dict(candidate.metadata),
                decay_rate=decay_rate,
                created_at=now,
                updated_at=now,
                last_accessed=None,
                last_verified=now if candidate.confidence >= 0.85 else None,
            )
            with self._connect() as connection:
                connection.execute(
                    """
                    INSERT INTO memories (
                        memory_id, memory_type, content, context, confidence,
                        importance, source, session_id, status, sensitivity, topic,
                        vector_json, metadata_json, decay_rate, created_at, updated_at,
                        last_accessed, last_verified
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._row_values(record),
                )
                connection.execute(
                    """
                    INSERT OR IGNORE INTO memory_index (topic, memory_id)
                    VALUES (?, ?)
                    """,
                    (record.topic, record.memory_id),
                )
            self._write_count += 1
            logger.debug(f"Memory record written: {record.memory_id}, type={record.memory_type}")
            return record
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to write memory record: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory write took {duration_ms:.2f}ms")

    def list_records(
        self,
        *,
        memory_type: MemoryType | None = None,
        status: MemoryStatus | None = None,
        limit: int = 100,
    ) -> list[MemoryRecord]:
        start_time = time.time()
        try:
            query = "SELECT * FROM memories"
            filters: list[str] = []
            values: list[Any] = []
            if memory_type is not None:
                filters.append("memory_type = ?")
                values.append(memory_type.value)
            if status is not None:
                filters.append("status = ?")
                values.append(status.value)
            if filters:
                query += " WHERE " + " AND ".join(filters)
            query += " ORDER BY created_at DESC LIMIT ?"
            values.append(limit)

            with self._connect() as connection:
                rows = connection.execute(query, values).fetchall()
            self._read_count += 1
            return [self._record_from_row(row) for row in rows]
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to list memory records: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory list took {duration_ms:.2f}ms")

    def get_record(self, memory_id: str) -> MemoryRecord | None:
        start_time = time.time()
        try:
            with self._connect() as connection:
                row = connection.execute(
                    "SELECT * FROM memories WHERE memory_id = ?",
                    (memory_id,),
                ).fetchone()
            self._read_count += 1
            return self._record_from_row(row) if row else None
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get memory record {memory_id}: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory get took {duration_ms:.2f}ms")

    def active_records(self) -> list[MemoryRecord]:
        return self.list_records(status=MemoryStatus.ACTIVE, limit=10_000)

    def update_confidence(
        self, memory_id: str, confidence: float, status: MemoryStatus | None = None
    ) -> None:
        start_time = time.time()
        try:
            now = datetime.now(timezone.utc).isoformat()
            with self._connect() as connection:
                if status is None:
                    connection.execute(
                        """
                        UPDATE memories
                        SET confidence = ?, updated_at = ?
                        WHERE memory_id = ?
                        """,
                        (confidence, now, memory_id),
                    )
                else:
                    connection.execute(
                        """
                        UPDATE memories
                        SET confidence = ?, status = ?, updated_at = ?
                        WHERE memory_id = ?
                        """,
                        (confidence, status.value, now, memory_id),
                    )
            logger.debug(f"Memory confidence updated: {memory_id}, confidence={confidence}")
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to update confidence for {memory_id}: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory update confidence took {duration_ms:.2f}ms")

    def update_status(
        self,
        memory_id: str,
        status: MemoryStatus,
        *,
        metadata_update: dict[str, Any] | None = None,
    ) -> MemoryRecord | None:
        start_time = time.time()
        try:
            record = self.get_record(memory_id)
            if record is None:
                logger.warning(f"Memory record not found for status update: {memory_id}")
                return None
            metadata = dict(record.metadata)
            metadata.update(metadata_update or {})
            now = datetime.now(timezone.utc).isoformat()
            with self._connect() as connection:
                connection.execute(
                    """
                    UPDATE memories
                    SET status = ?, metadata_json = ?, updated_at = ?
                    WHERE memory_id = ?
                    """,
                    (status.value, json.dumps(metadata), now, memory_id),
                )
            logger.debug(f"Memory status updated: {memory_id}, status={status}")
            return self.get_record(memory_id)
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to update status for {memory_id}: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory update status took {duration_ms:.2f}ms")

    def mark_accessed(self, memory_ids: list[str]) -> None:
        if not memory_ids:
            return
        start_time = time.time()
        try:
            now = datetime.now(timezone.utc).isoformat()
            placeholders = ",".join("?" for _ in memory_ids)
            with self._connect() as connection:
                connection.execute(
                    f"""
                    UPDATE memories
                    SET last_accessed = ?
                    WHERE memory_id IN ({placeholders})
                    """,
                    [now, *memory_ids],
                )
            logger.debug(f"Marked {len(memory_ids)} memories as accessed")
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to mark memories as accessed: {e}", exc_info=True)
            raise
        finally:
            duration_ms = (time.time() - start_time) * 1000
            logger.debug(f"Memory mark accessed took {duration_ms:.2f}ms")

    def count_by_status(self) -> dict[str, int]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT status, COUNT(*) AS count FROM memories GROUP BY status"
                ).fetchall()
            return {row["status"]: row["count"] for row in rows}
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to count by status: {e}", exc_info=True)
            return {}

    def count_by_type(self) -> dict[str, int]:
        try:
            with self._connect() as connection:
                rows = connection.execute(
                    "SELECT memory_type, COUNT(*) AS count FROM memories GROUP BY memory_type"
                ).fetchall()
            return {row["memory_type"]: row["count"] for row in rows}
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to count by type: {e}", exc_info=True)
            return {}

    def get_statistics(self) -> dict[str, Any]:
        """Get memory store statistics."""
        try:
            with self._connect() as connection:
                cursor = connection.execute("SELECT COUNT(*) FROM memories")
                total = cursor.fetchone()[0]
            return {
                "db_path": str(self.db_path),
                "total_records": total,
                "by_status": self.count_by_status(),
                "by_type": self.count_by_type(),
                "write_count": self._write_count,
                "read_count": self._read_count,
                "error_count": self._error_count,
                "error_rate": self._error_count / (self._write_count + self._read_count) if (self._write_count + self._read_count) > 0 else 0,
            }
        except Exception as e:
            self._error_count += 1
            logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return {
                "db_path": str(self.db_path),
                "error": str(e),
                "write_count": self._write_count,
                "read_count": self._read_count,
                "error_count": self._error_count,
            }

    def _initialize(self) -> None:
        try:
            with self._connect() as connection:
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memories (
                        memory_id TEXT PRIMARY KEY,
                        memory_type TEXT NOT NULL,
                        content TEXT NOT NULL,
                        context TEXT NOT NULL DEFAULT '',
                        confidence REAL NOT NULL,
                        importance REAL NOT NULL,
                        source TEXT NOT NULL,
                        session_id TEXT,
                        status TEXT NOT NULL,
                        sensitivity TEXT NOT NULL,
                        topic TEXT NOT NULL,
                        vector_json TEXT NOT NULL,
                        metadata_json TEXT NOT NULL,
                        decay_rate REAL NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        last_accessed TEXT,
                        last_verified TEXT
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE TABLE IF NOT EXISTS memory_index (
                        topic TEXT NOT NULL,
                        memory_id TEXT NOT NULL,
                        PRIMARY KEY (topic, memory_id),
                        FOREIGN KEY (memory_id) REFERENCES memories(memory_id)
                    )
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_status_type
                    ON memories(status, memory_type)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_topic
                    ON memories(topic)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_session_id
                    ON memories(session_id)
                    """
                )
                connection.execute(
                    """
                    CREATE INDEX IF NOT EXISTS idx_memories_confidence
                    ON memories(confidence)
                    """
                )
            logger.debug("MemoryStore database initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize MemoryStore database: {e}", exc_info=True)
            raise

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def _row_values(self, record: MemoryRecord) -> tuple[Any, ...]:
        return (
            record.memory_id,
            record.memory_type.value,
            record.content,
            record.context,
            record.confidence,
            record.importance,
            record.source,
            record.session_id,
            record.status.value,
            record.sensitivity,
            record.topic,
            json.dumps(record.vector),
            json.dumps(record.metadata),
            record.decay_rate,
            record.created_at.isoformat(),
            record.updated_at.isoformat(),
            record.last_accessed.isoformat() if record.last_accessed else None,
            record.last_verified.isoformat() if record.last_verified else None,
        )

    def _record_from_row(self, row: sqlite3.Row) -> MemoryRecord:
        try:
            return MemoryRecord(
                memory_id=row["memory_id"],
                memory_type=MemoryType(row["memory_type"]),
                content=row["content"],
                context=row["context"],
                confidence=row["confidence"],
                importance=row["importance"],
                source=row["source"],
                session_id=row["session_id"],
                status=MemoryStatus(row["status"]),
                sensitivity=row["sensitivity"],
                topic=row["topic"],
                vector=json.loads(row["vector_json"]),
                metadata=json.loads(row["metadata_json"]),
                decay_rate=row["decay_rate"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                last_accessed=(
                    datetime.fromisoformat(row["last_accessed"])
                    if row["last_accessed"]
                    else None
                ),
                last_verified=(
                    datetime.fromisoformat(row["last_verified"])
                    if row["last_verified"]
                    else None
                ),
            )
        except Exception as e:
            logger.error(f"Failed to parse row to MemoryRecord: {e}", exc_info=True)
            raise
