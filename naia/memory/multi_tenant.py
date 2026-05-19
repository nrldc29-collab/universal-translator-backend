"""Multi-tenant memory isolation for NAIA."""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from memory.memory_store import MemoryRecord

logger = logging.getLogger(__name__)


class TenantContext(BaseModel):
    """Context for a specific tenant."""

    tenant_id: str
    user_id: str | None = None
    permissions: list[str] = Field(default_factory=list)
    isolation_level: str = "strict"  # strict, medium, loose


class MultiTenantMemoryStore:
    """Multi-tenant memory store with isolation between tenants."""

    def __init__(self, db_path: str | Path = "memory/naia_memory_multi_tenant.sqlite3") -> None:
        """
        Initialize the multi-tenant memory store.

        Args:
            db_path: Path to the SQLite database
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self) -> None:
        """Initialize the multi-tenant database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Tenants table
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS tenants (
                tenant_id TEXT PRIMARY KEY,
                created_at TEXT,
                isolation_level TEXT DEFAULT 'strict',
                metadata TEXT
            )"""
        )

        # Memory records with tenant isolation
        cursor.execute(
            """CREATE TABLE IF NOT EXISTS memory_records (
                memory_id TEXT PRIMARY KEY,
                tenant_id TEXT NOT NULL,
                user_id TEXT,
                content TEXT,
                memory_type TEXT,
                confidence REAL,
                importance REAL,
                status TEXT DEFAULT 'active',
                vector TEXT,
                created_at TEXT,
                last_accessed_at TEXT,
                metadata TEXT,
                FOREIGN KEY (tenant_id) REFERENCES tenants (tenant_id)
            )"""
        )

        # Create indexes for tenant isolation
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_tenant_id ON memory_records(tenant_id)"""
        )
        cursor.execute(
            """CREATE INDEX IF NOT EXISTS idx_tenant_user ON memory_records(tenant_id, user_id)"""
        )

        conn.commit()
        conn.close()

    def create_tenant(self, tenant_id: str, isolation_level: str = "strict") -> bool:
        """
        Create a new tenant.

        Args:
            tenant_id: Unique tenant identifier
            isolation_level: Isolation level (strict, medium, loose)

        Returns:
            True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            cursor.execute(
                """INSERT INTO tenants (tenant_id, created_at, isolation_level)
                   VALUES (?, ?, ?)""",
                (tenant_id, datetime.now(timezone.utc).isoformat(), isolation_level),
            )
            conn.commit()
            logger.info(f"Created tenant: {tenant_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Tenant already exists: {tenant_id}")
            return False
        finally:
            conn.close()

    def store(
        self,
        tenant_id: str,
        content: str,
        memory_type: str,
        user_id: str | None = None,
        **kwargs: Any,
    ) -> str:
        """
        Store a memory record for a specific tenant.

        Args:
            tenant_id: Tenant identifier
            content: Memory content
            memory_type: Type of memory
            user_id: Optional user identifier within tenant
            **kwargs: Additional memory fields

        Returns:
            Memory ID
        """
        import uuid

        memory_id = str(uuid.uuid4())
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute(
            """INSERT INTO memory_records
               (memory_id, tenant_id, user_id, content, memory_type, confidence, importance,
                status, created_at, last_accessed_at, metadata)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                memory_id,
                tenant_id,
                user_id,
                content,
                memory_type,
                kwargs.get("confidence", 0.5),
                kwargs.get("importance", 0.5),
                kwargs.get("status", "active"),
                datetime.now(timezone.utc).isoformat(),
                datetime.now(timezone.utc).isoformat(),
                str(kwargs.get("metadata", {})),
            ),
        )

        conn.commit()
        conn.close()

        return memory_id

    def retrieve(
        self,
        tenant_id: str,
        memory_type: str | None = None,
        user_id: str | None = None,
        limit: int = 50,
    ) -> list[MemoryRecord]:
        """
        Retrieve memory records for a specific tenant.

        Args:
            tenant_id: Tenant identifier
            memory_type: Optional memory type filter
            user_id: Optional user identifier filter
            limit: Maximum number of records to return

        Returns:
            List of memory records
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        query = "SELECT * FROM memory_records WHERE tenant_id = ? AND status = 'active'"
        params = [tenant_id]

        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)

        if user_id:
            query += " AND user_id = ?"
            params.append(user_id)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(query, params)
        rows = cursor.fetchall()
        conn.close()

        records = []
        for row in rows:
            records.append(self._row_to_record(row))

        return records

    def _row_to_record(self, row: tuple) -> MemoryRecord:
        """Convert database row to MemoryRecord."""
        import json

        return MemoryRecord(
            memory_id=row[0],
            content=row[3],
            memory_type=row[4],
            confidence=row[5],
            importance=row[6],
            status=row[7],
            vector=json.loads(row[8]) if row[8] else [],
            created_at=datetime.fromisoformat(row[9]),
            last_accessed_at=datetime.fromisoformat(row[10]),
            metadata=json.loads(row[11]) if row[11] else {},
        )

    def get_tenant_stats(self, tenant_id: str) -> dict[str, Any]:
        """
        Get statistics for a specific tenant.

        Args:
            tenant_id: Tenant identifier

        Returns:
            Tenant statistics
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Get total records
        cursor.execute(
            """SELECT COUNT(*) FROM memory_records WHERE tenant_id = ?""",
            (tenant_id,),
        )
        total_records = cursor.fetchone()[0]

        # Get records by type
        cursor.execute(
            """SELECT memory_type, COUNT(*) FROM memory_records
               WHERE tenant_id = ? GROUP BY memory_type""",
            (tenant_id,),
        )
        by_type = dict(cursor.fetchall())

        # Get user count
        cursor.execute(
            """SELECT COUNT(DISTINCT user_id) FROM memory_records
               WHERE tenant_id = ? AND user_id IS NOT NULL""",
            (tenant_id,),
        )
        user_count = cursor.fetchone()[0]

        conn.close()

        return {
            "tenant_id": tenant_id,
            "total_records": total_records,
            "records_by_type": by_type,
            "user_count": user_count,
        }

    def delete_tenant(self, tenant_id: str) -> bool:
        """
        Delete a tenant and all associated memory records.

        Args:
            tenant_id: Tenant identifier

        Returns:
            True if successful
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        try:
            # Delete all memory records for tenant
            cursor.execute(
                """DELETE FROM memory_records WHERE tenant_id = ?""",
                (tenant_id,),
            )

            # Delete tenant
            cursor.execute("""DELETE FROM tenants WHERE tenant_id = ?""", (tenant_id,))

            conn.commit()
            logger.info(f"Deleted tenant: {tenant_id}")
            return True
        except Exception as exc:
            logger.error(f"Failed to delete tenant {tenant_id}: {exc}")
            conn.rollback()
            return False
        finally:
            conn.close()

    def list_tenants(self) -> list[str]:
        """List all tenant IDs."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("SELECT tenant_id FROM tenants")
        tenant_ids = [row[0] for row in cursor.fetchall()]

        conn.close()
        return tenant_ids
