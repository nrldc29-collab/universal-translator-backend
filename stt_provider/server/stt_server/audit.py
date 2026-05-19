"""
Audit logging module for security and compliance.

This module provides functionality for writing audit events to the database
for security auditing and compliance purposes. It tracks tenant actions,
actor identities, event types, resources, and payloads with trace ID correlation.
"""
import logging
from typing import Any, Optional
from uuid import UUID

import asyncpg

from stt_server.logging_utils import get_trace_id

logger = logging.getLogger(__name__)


async def write_audit_event(
    db: asyncpg.Connection,
    *,
    tenant_id: Optional[UUID],
    actor_id: Optional[str],
    event_type: str,
    resource: Optional[str] = None,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """
    Write an audit event to the database.
    
    Inserts an audit log entry with tenant, actor, event type, resource,
    trace ID, and optional payload for security auditing and compliance.
    
    Args:
        db: Database connection
        tenant_id: UUID of the tenant associated with the event
        actor_id: ID of the actor who performed the action
        event_type: Type of audit event (e.g., "tenant_created", "api_key_rotated")
        resource: Optional resource identifier affected by the event
        payload: Optional dictionary of additional event data
    """
    try:
        await db.execute(
            """
            INSERT INTO audit_log (
                tenant_id,
                actor_id,
                event_type,
                resource,
                trace_id,
                payload_jsonb
            )
            VALUES ($1, $2, $3, $4, $5, $6::jsonb)
            """,
            tenant_id,
            actor_id,
            event_type,
            resource,
            get_trace_id(),
            payload or {},
        )
        logger.debug(
            f"Audit event written: event_type={event_type}, tenant_id={tenant_id}, actor_id={actor_id}"
        )
    except asyncpg.PostgresError as e:
        logger.error(f"Failed to write audit event: {e}")
        raise
