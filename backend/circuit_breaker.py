"""Circuit breaker implementation for external service calls.

Prevents cascading failures by temporarily blocking calls to failing services.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any, Callable, TypeVar

logger = logging.getLogger("anai_translator.circuit_breaker")

T = TypeVar("T")


class CircuitState(Enum):
    CLOSED = "closed"  # Normal operation, calls allowed
    OPEN = "open"  # Circuit tripped, calls blocked
    HALF_OPEN = "half_open"  # Testing if service has recovered


@dataclass
class CircuitBreakerConfig:
    failure_threshold: int = 5  # Failures before opening
    recovery_timeout: float = 30.0  # Seconds before trying half-open
    success_threshold: int = 2  # Successes before closing from half-open
    timeout: float = 10.0  # Per-call timeout


@dataclass
class CircuitBreakerStats:
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    last_failure_time: float = 0.0
    last_success_time: float = 0.0


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is OPEN and rejects a call."""
    pass


class CircuitBreaker:
    """Circuit breaker for protecting against cascading failures."""

    def __init__(self, name: str, config: CircuitBreakerConfig | None = None):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.stats = CircuitBreakerStats()
        self._failure_count = 0
        self._success_count = 0
        self._lock = asyncio.Lock()
        logger.info("CircuitBreaker initialized: name=%s config=%s", name, self.config)

    async def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """Execute function with circuit breaker protection."""
        self.stats.total_calls += 1

        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                await self._transition_to_half_open()
            else:
                self.stats.rejected_calls += 1
                logger.warning(
                    "CircuitBreaker rejected call: name=%s state=%s failures=%d",
                    self.name,
                    self.state.value,
                    self._failure_count,
                )
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN. Rejecting call."
                )

        try:
            result = await asyncio.wait_for(func(*args, **kwargs), timeout=self.config.timeout)
            await self._record_success()
            return result
        except asyncio.TimeoutError as exc:
            await self._record_failure()
            raise CircuitBreakerOpenError(
                f"Circuit breaker '{self.name}' call timed out after {self.config.timeout}s"
            ) from exc
        except (RuntimeError, ValueError, TimeoutError, ConnectionError, OSError) as exc:
            # Network/connection failures are the canonical reason to trip a
            # breaker, so they must count toward the failure threshold too.
            await self._record_failure()
            raise exc

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try half-open."""
        return (time() - self.stats.last_failure_time) >= self.config.recovery_timeout

    async def _transition_to_half_open(self) -> None:
        """Transition from OPEN to HALF_OPEN state."""
        async with self._lock:
            if self.state == CircuitState.OPEN and self._should_attempt_reset():
                self.state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info(
                    "CircuitBreaker transition: name=%s from=OPEN to=HALF_OPEN",
                    self.name,
                )

    async def _record_success(self) -> None:
        """Record a successful call."""
        async with self._lock:
            self.stats.successful_calls += 1
            self.stats.last_success_time = time()

            if self.state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self._failure_count = 0
                    logger.info(
                        "CircuitBreaker transition: name=%s from=HALF_OPEN to=CLOSED",
                        self.name,
                    )
            elif self.state == CircuitState.CLOSED:
                self._failure_count = 0

    async def _record_failure(self) -> None:
        """Record a failed call."""
        async with self._lock:
            self.stats.failed_calls += 1
            self.stats.last_failure_time = time()

            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(
                    "CircuitBreaker transition: name=%s from=HALF_OPEN to=OPEN",
                    self.name,
                )
            elif self.state == CircuitState.CLOSED:
                self._failure_count += 1
                if self._failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    logger.warning(
                        "CircuitBreaker transition: name=%s from=CLOSED to=OPEN failures=%d",
                        self.name,
                        self._failure_count,
                    )

    async def force_open(self) -> None:
        """Force circuit breaker to OPEN state (for testing/maintenance)."""
        async with self._lock:
            self.state = CircuitState.OPEN
            self.stats.last_failure_time = time()
            logger.info("CircuitBreaker forced open: name=%s", self.name)

    async def force_close(self) -> None:
        """Force circuit breaker to CLOSED state (for testing/recovery)."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            logger.info("CircuitBreaker forced closed: name=%s", self.name)

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_stats(self) -> dict[str, Any]:
        """Get circuit breaker statistics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
            },
            "stats": {
                "total_calls": self.stats.total_calls,
                "successful_calls": self.stats.successful_calls,
                "failed_calls": self.stats.failed_calls,
                "rejected_calls": self.stats.rejected_calls,
                "last_failure_time": self.stats.last_failure_time,
                "last_success_time": self.stats.last_success_time,
            },
        }


# Global circuit breaker registry
_circuit_breakers: dict[str, CircuitBreaker] = {}
_breaker_lock = asyncio.Lock()


def get_circuit_breaker(name: str, config: CircuitBreakerConfig | None = None) -> CircuitBreaker:
    """Get or create a circuit breaker by name."""
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
    return _circuit_breakers[name]


async def reset_all_circuit_breakers() -> None:
    """Reset all circuit breakers to CLOSED state."""
    async with _breaker_lock:
        for breaker in _circuit_breakers.values():
            await breaker.force_close()
    logger.info("All circuit breakers reset")


def get_all_circuit_breaker_stats() -> dict[str, dict[str, Any]]:
    """Get statistics for all circuit breakers."""
    return {name: breaker.get_stats() for name, breaker in _circuit_breakers.items()}
