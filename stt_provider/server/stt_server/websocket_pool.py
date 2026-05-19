"""
WebSocket connection pool for managing streaming connections.
"""
import asyncio
import os
import time
from dataclasses import dataclass, field
from typing import Optional
from uuid import UUID


@dataclass
class WebSocketConnection:
    connection_id: UUID
    tenant_id: UUID
    connected_at: float
    last_activity: float
    is_active: bool = True


@dataclass
class PoolStats:
    total_connections: int = 0
    active_connections: int = 0
    idle_connections: int = 0
    connections_by_tenant: dict[str, int] = field(default_factory=dict)


class WebSocketConnectionPool:
    def __init__(
        self,
        max_connections: int = 1000,
        max_connections_per_tenant: int = 50,
        idle_timeout_seconds: int = 300,
        max_session_duration_seconds: int = 3600,
    ):
        self.max_connections = max_connections
        self.max_connections_per_tenant = max_connections_per_tenant
        self.idle_timeout_seconds = idle_timeout_seconds
        self.max_session_duration_seconds = max_session_duration_seconds
        self._connections: dict[UUID, WebSocketConnection] = {}
        self._tenant_connections: dict[str, set[UUID]] = {}
        self._lock = asyncio.Lock()

    async def add_connection(self, connection_id: UUID, tenant_id: UUID) -> tuple[bool, str | None]:
        async with self._lock:
            allowed, message = await self._is_connection_allowed_unlocked(tenant_id)
            if not allowed:
                return False, message
            now = time.time()
            tenant_key = str(tenant_id)
            self._connections[connection_id] = WebSocketConnection(
                connection_id=connection_id,
                tenant_id=tenant_id,
                connected_at=now,
                last_activity=now,
            )
            self._tenant_connections.setdefault(tenant_key, set()).add(connection_id)
            return True, None

    async def remove_connection(self, connection_id: UUID) -> bool:
        async with self._lock:
            connection = self._connections.pop(connection_id, None)
            if connection is None:
                return False
            tenant_key = str(connection.tenant_id)
            tenant_connections = self._tenant_connections.get(tenant_key)
            if tenant_connections is not None:
                tenant_connections.discard(connection_id)
                if not tenant_connections:
                    self._tenant_connections.pop(tenant_key, None)
            return True

    async def update_activity(self, connection_id: UUID) -> bool:
        async with self._lock:
            connection = self._connections.get(connection_id)
            if connection is None:
                return False
            connection.last_activity = time.time()
            return True

    async def cleanup_idle_connections(self) -> int:
        async with self._lock:
            now = time.time()
            to_remove = [
                connection_id
                for connection_id, connection in self._connections.items()
                if now - connection.last_activity > self.idle_timeout_seconds
                or now - connection.connected_at > self.max_session_duration_seconds
            ]
            for connection_id in to_remove:
                connection = self._connections.pop(connection_id, None)
                if connection is None:
                    continue
                tenant_key = str(connection.tenant_id)
                tenant_connections = self._tenant_connections.get(tenant_key)
                if tenant_connections is not None:
                    tenant_connections.discard(connection_id)
                    if not tenant_connections:
                        self._tenant_connections.pop(tenant_key, None)
            return len(to_remove)

    def get_stats(self) -> PoolStats:
        now = time.time()
        active_count = 0
        idle_count = 0
        for connection in self._connections.values():
            if now - connection.last_activity < 30:
                active_count += 1
            else:
                idle_count += 1
        return PoolStats(
            total_connections=len(self._connections),
            active_connections=active_count,
            idle_connections=idle_count,
            connections_by_tenant={key: len(value) for key, value in self._tenant_connections.items()},
        )

    def get_tenant_connection_count(self, tenant_id: UUID) -> int:
        return len(self._tenant_connections.get(str(tenant_id), set()))

    async def is_connection_allowed(self, tenant_id: UUID) -> tuple[bool, str | None]:
        async with self._lock:
            return await self._is_connection_allowed_unlocked(tenant_id)

    async def _is_connection_allowed_unlocked(self, tenant_id: UUID) -> tuple[bool, str | None]:
        if len(self._connections) >= self.max_connections:
            return False, f"Maximum connections ({self.max_connections}) reached"
        tenant_connections = self._tenant_connections.get(str(tenant_id), set())
        if len(tenant_connections) >= self.max_connections_per_tenant:
            return False, f"Maximum connections per tenant ({self.max_connections_per_tenant}) reached"
        return True, None


_global_pool: Optional[WebSocketConnectionPool] = None


def get_websocket_pool() -> WebSocketConnectionPool:
    global _global_pool
    if _global_pool is None:
        _global_pool = WebSocketConnectionPool(
            max_connections=int(os.environ.get("WS_MAX_CONNECTIONS", "1000")),
            max_connections_per_tenant=int(os.environ.get("WS_MAX_CONNECTIONS_PER_TENANT", "50")),
            idle_timeout_seconds=int(os.environ.get("WS_IDLE_TIMEOUT_SECONDS", "300")),
            max_session_duration_seconds=int(os.environ.get("WS_MAX_SESSION_DURATION_SECONDS", "3600")),
        )
    return _global_pool
