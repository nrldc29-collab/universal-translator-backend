"""
Webhook notification system for STT service events.

This module provides a webhook notification system that allows external services
to receive real-time notifications about STT service events such as session
start/end, transcript completion, errors, and backend failovers. Features include:
- Event type filtering per subscription
- HMAC signature verification for security
- Automatic retry logic with exponential backoff
- Background delivery worker for async processing
"""
import asyncio
import json
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import httpx

logger = logging.getLogger(__name__)


class WebhookEventType(str, Enum):
    """Types of webhook events that can be emitted by the STT service."""
    SESSION_STARTED = "session.started"
    SESSION_ENDED = "session.ended"
    TRANSCRIPT_COMPLETED = "transcript.completed"
    ERROR_OCCURRED = "error.occurred"
    RATE_LIMIT_EXCEEDED = "rate_limit.exceeded"
    SPEAKER_MATCHED = "speaker.matched"
    BACKEND_FAILOVER = "backend.failover"


@dataclass
class WebhookEvent:
    """
    Represents a webhook event to be delivered to subscribers.
    
    Attributes:
        event_type: Type of the event
        tenant_id: Tenant ID that owns the event
        timestamp: Unix timestamp when the event occurred
        data: Event-specific data payload
        event_id: Unique identifier for this event instance
    """
    event_type: WebhookEventType
    tenant_id: str
    timestamp: float
    data: Dict[str, Any]
    event_id: str = field(default_factory=lambda: f"evt_{int(time.time() * 1000)}")


@dataclass
class WebhookSubscription:
    """
    Represents a webhook subscription configuration.
    
    Attributes:
        subscription_id: Unique identifier for the subscription
        tenant_id: Tenant ID that owns the subscription
        url: Webhook URL to deliver events to
        event_types: List of event types this subscription listens to
        secret: Optional secret for HMAC signature verification
        is_active: Whether the subscription is currently active
        created_at: Unix timestamp when subscription was created
    """
    subscription_id: str
    tenant_id: str
    url: str
    event_types: List[WebhookEventType]
    secret: Optional[str] = None
    is_active: bool = True
    created_at: float = field(default_factory=time.time)


@dataclass
class WebhookDeliveryResult:
    """
    Result of a webhook delivery attempt.
    
    Attributes:
        success: Whether the delivery was successful
        status_code: HTTP status code from webhook endpoint
        error: Error message if delivery failed
        duration_ms: Time taken to deliver the webhook
    """
    success: bool
    status_code: Optional[int] = None
    error: Optional[str] = None
    duration_ms: float = 0.0


class WebhookNotifier:
    """
    Manage webhook notifications for STT service events.
    
    This class handles webhook subscription management, event emission,
    and delivery with retry logic. Supports HMAC signature verification
    and background async delivery workers.
    
    Attributes:
        timeout_seconds: HTTP request timeout for webhook delivery
        max_retries: Maximum number of retry attempts for failed deliveries
        retry_delay_seconds: Base delay between retry attempts
        _subscriptions: Dictionary of active subscriptions by ID
        _delivery_queue: Async queue for background event delivery
        _is_running: Whether the background delivery worker is running
    """
    
    def __init__(
        self,
        timeout_seconds: int = 10,
        max_retries: int = 3,
        retry_delay_seconds: float = 1.0,
    ):
        """
        Initialize the webhook notifier.
        
        Args:
            timeout_seconds: HTTP request timeout for webhook delivery
            max_retries: Maximum number of retry attempts for failed deliveries
            retry_delay_seconds: Base delay between retry attempts
        """
        self.timeout_seconds = timeout_seconds
        self.max_retries = max_retries
        self.retry_delay_seconds = retry_delay_seconds
        self._subscriptions: Dict[str, WebhookSubscription] = {}
        self._delivery_queue: asyncio.Queue = asyncio.Queue()
        self._is_running = False
        logger.debug(f"WebhookNotifier initialized with timeout={timeout_seconds}s, max_retries={max_retries}")
    
    def add_subscription(
        self,
        subscription_id: str,
        tenant_id: str,
        url: str,
        event_types: List[WebhookEventType],
        secret: Optional[str] = None,
    ) -> WebhookSubscription:
        """
        Add a webhook subscription.
        
        Args:
            subscription_id: Unique identifier for the subscription
            tenant_id: Tenant ID that owns the subscription
            url: Webhook URL to deliver events to
            event_types: List of event types this subscription listens to
            secret: Optional secret for HMAC signature verification
            
        Returns:
            The created WebhookSubscription object
        """
        subscription = WebhookSubscription(
            subscription_id=subscription_id,
            tenant_id=tenant_id,
            url=url,
            event_types=event_types,
            secret=secret,
        )
        
        self._subscriptions[subscription_id] = subscription
        logger.info(f"Added webhook subscription: {subscription_id} for tenant {tenant_id} to {url}")
        return subscription
    
    def remove_subscription(self, subscription_id: str) -> bool:
        """
        Remove a webhook subscription.
        
        Args:
            subscription_id: Unique identifier of the subscription to remove
            
        Returns:
            True if subscription was removed, False if not found
        """
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            logger.info(f"Removed webhook subscription: {subscription_id}")
            return True
        logger.warning(f"Attempted to remove non-existent subscription: {subscription_id}")
        return False
    
    def get_subscriptions_for_tenant(self, tenant_id: str) -> List[WebhookSubscription]:
        """
        Get all active subscriptions for a tenant.
        
        Args:
            tenant_id: Tenant ID to query subscriptions for
            
        Returns:
            List of active WebhookSubscription objects for the tenant
        """
        return [
            sub for sub in self._subscriptions.values()
            if sub.tenant_id == tenant_id and sub.is_active
        ]
    
    async def emit_event(self, event: WebhookEvent) -> List[WebhookDeliveryResult]:
        """
        Emit an event to all relevant subscribers.
        
        Finds all active subscriptions for the tenant that match the event type,
        then delivers the webhook concurrently to all matching subscriptions.
        
        Args:
            event: The event to emit
            
        Returns:
            List of delivery results for each subscription
        """
        logger.debug(f"Emitting event {event.event_type.value} for tenant {event.tenant_id}")
        
        # Find relevant subscriptions
        relevant_subs = [
            sub for sub in self._subscriptions.values()
            if sub.tenant_id == event.tenant_id
            and sub.is_active
            and event.event_type in sub.event_types
        ]
        
        if not relevant_subs:
            logger.debug(f"No matching subscriptions for event {event.event_type.value}")
            return []
        
        logger.info(f"Delivering event {event.event_type.value} to {len(relevant_subs)} subscriptions")
        
        # Deliver to all subscribers concurrently
        delivery_tasks = [
            self._deliver_webhook(sub, event)
            for sub in relevant_subs
        ]
        
        results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
        
        successful = sum(1 for r in results if isinstance(r, WebhookDeliveryResult) and r.success)
        logger.info(f"Event delivery complete: {successful}/{len(relevant_subs)} successful")
        
        return [r for r in results if isinstance(r, WebhookDeliveryResult)]
    
    async def _deliver_webhook(
        self,
        subscription: WebhookSubscription,
        event: WebhookEvent,
    ) -> WebhookDeliveryResult:
        """
        Deliver a webhook to a subscription with retry logic.
        
        Attempts to deliver the webhook with exponential backoff retry logic.
        Adds HMAC signature if secret is configured.
        
        Args:
            subscription: The subscription to deliver to
            event: The event to deliver
            
        Returns:
            WebhookDeliveryResult indicating success or failure
        """
        start_time = time.time()
        
        payload = {
            "event_id": event.event_id,
            "event_type": event.event_type.value,
            "tenant_id": event.tenant_id,
            "timestamp": event.timestamp,
            "data": event.data,
        }
        
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "STT-Webhook-Notifier/1.0",
        }
        
        # Add signature if secret is configured
        if subscription.secret:
            import hmac
            import hashlib
            signature = hmac.new(
                subscription.secret.encode(),
                json.dumps(payload).encode(),
                hashlib.sha256,
            ).hexdigest()
            headers["X-Webhook-Signature"] = f"sha256={signature}"
            logger.debug(f"Added HMAC signature for subscription {subscription.subscription_id}")
        
        # Retry logic
        last_error = None
        
        for attempt in range(self.max_retries):
            try:
                logger.debug(f"Webhook delivery attempt {attempt + 1}/{self.max_retries} to {subscription.url}")
                async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                    response = await client.post(
                        subscription.url,
                        json=payload,
                        headers=headers,
                    )
                    
                    duration_ms = (time.time() - start_time) * 1000
                    
                    if response.status_code >= 200 and response.status_code < 300:
                        logger.info(f"Webhook delivered successfully to {subscription.url} in {duration_ms:.0f}ms")
                        return WebhookDeliveryResult(
                            success=True,
                            status_code=response.status_code,
                            duration_ms=duration_ms,
                        )
                    else:
                        last_error = f"HTTP {response.status_code}"
                        logger.warning(f"Webhook delivery failed with status {response.status_code} on attempt {attempt + 1}")
                        
            except Exception as e:
                last_error = str(e)
                logger.warning(f"Webhook delivery error on attempt {attempt + 1}: {e}")
            
            # Wait before retry
            if attempt < self.max_retries - 1:
                delay = self.retry_delay_seconds * (attempt + 1)
                logger.debug(f"Retrying webhook delivery in {delay}s")
                await asyncio.sleep(delay)
        
        duration_ms = (time.time() - start_time) * 1000
        logger.error(f"Webhook delivery failed after {self.max_retries} attempts to {subscription.url}: {last_error}")
        
        return WebhookDeliveryResult(
            success=False,
            error=last_error,
            duration_ms=duration_ms,
        )
    
    async def start_delivery_worker(self) -> None:
        """
        Start the background delivery worker.
        
        Starts an async worker that processes events from the delivery queue.
        Only one worker can run at a time.
        """
        if self._is_running:
            logger.warning("Delivery worker already running")
            return
        
        self._is_running = True
        logger.info("Starting webhook delivery worker")
        
        while self._is_running:
            try:
                event = await asyncio.wait_for(
                    self._delivery_queue.get(),
                    timeout=1.0,
                )
                await self.emit_event(event)
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Webhook delivery error: {e}", exc_info=True)
    
    async def stop_delivery_worker(self) -> None:
        """
        Stop the background delivery worker.
        
        Signals the worker to stop processing events.
        """
        self._is_running = False
        logger.info("Stopping webhook delivery worker")
    
    async def queue_event(self, event: WebhookEvent) -> None:
        """
        Queue an event for background delivery.
        
        Adds the event to the delivery queue for processing by the
        background worker. Requires the delivery worker to be running.
        
        Args:
            event: The event to queue for delivery
        """
        await self._delivery_queue.put(event)
        logger.debug(f"Queued event {event.event_id} for delivery")
    
    def get_stats(self) -> dict:
        """
        Get webhook notification statistics.
        
        Returns:
            Dictionary containing subscription counts, worker status, and queue size
        """
        stats = {
            "total_subscriptions": len(self._subscriptions),
            "active_subscriptions": sum(1 for s in self._subscriptions.values() if s.is_active),
            "is_running": self._is_running,
            "queue_size": self._delivery_queue.qsize(),
        }
        logger.debug(f"Webhook stats: {stats}")
        return stats


# Global webhook notifier instance
_global_notifier: Optional[WebhookNotifier] = None


def get_webhook_notifier() -> WebhookNotifier:
    """
    Get the global webhook notifier instance.
    
    Creates and configures the notifier on first call using environment variables.
    Subsequent calls return the same singleton instance.
    
    Environment variables:
        WEBHOOK_TIMEOUT_SECONDS: HTTP request timeout (default: 10)
        WEBHOOK_MAX_RETRIES: Maximum retry attempts (default: 3)
        WEBHOOK_RETRY_DELAY_SECONDS: Base retry delay (default: 1.0)
        
    Returns:
        The global WebhookNotifier instance
    """
    global _global_notifier
    
    if _global_notifier is None:
        import os
        _global_notifier = WebhookNotifier(
            timeout_seconds=int(os.environ.get("WEBHOOK_TIMEOUT_SECONDS", "10")),
            max_retries=int(os.environ.get("WEBHOOK_MAX_RETRIES", "3")),
            retry_delay_seconds=float(os.environ.get("WEBHOOK_RETRY_DELAY_SECONDS", "1.0")),
        )
        logger.info("Global webhook notifier initialized")
    
    return _global_notifier
