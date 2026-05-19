"""
Circuit breaker pattern implementation for fault tolerance.

This module provides a circuit breaker pattern implementation to prevent cascading
failures and improve system resilience. It automatically trips when failures exceed
a threshold and attempts recovery after a timeout period.
"""
import asyncio
import logging
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Callable, Dict, Optional

logger = logging.getLogger(__name__)


class CircuitState(StrEnum):
    """
    States of a circuit breaker.
    
    Defines the three possible states of a circuit breaker:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Circuit has tripped, requests are blocked
    - HALF_OPEN: Recovery mode, limited requests allowed to test if system has recovered
    
    Attributes:
        CLOSED: Normal operation state
        OPEN: Failed state blocking requests
        HALF_OPEN: Recovery testing state
    """
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.
    
    Defines the thresholds and timeouts that control circuit breaker behavior.
    
    Attributes:
        failure_threshold: Number of failures before circuit trips (default: 5)
        recovery_timeout: Seconds to wait before attempting recovery (default: 60)
        expected_exception: Exception type to consider as failure (default: Exception)
    """
    failure_threshold: int = 5
    recovery_timeout: float = 60.0  # seconds
    expected_exception: type[Exception] = Exception


@dataclass
class CircuitBreakerState:
    """
    Internal state of a circuit breaker.
    
    Tracks the current state, failure counts, success counts, and timing
    information for circuit breaker decision making.
    
    Attributes:
        state: Current circuit breaker state
        failure_count: Number of consecutive failures
        last_failure_time: Timestamp of last failure
        success_count: Number of consecutive successes in half-open state
    """
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count: int = 0


class CircuitBreaker:
    """
    Circuit breaker implementation for fault tolerance.
    
    Implements the circuit breaker pattern to prevent cascading failures
    by automatically tripping when failures exceed a threshold and
    attempting recovery after a timeout period.
    
    Attributes:
        name: Name identifier for the circuit breaker
        config: Configuration parameters
        _state: Internal circuit breaker state
        _lock: Async lock for thread-safe state updates
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None,
    ) -> None:
        """
        Initialize the circuit breaker.
        
        Args:
            name: Name identifier for the circuit breaker
            config: Optional configuration parameters
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self._state = CircuitBreakerState()
        self._lock = asyncio.Lock()
        logger.info(
            f"CircuitBreaker '{name}' initialized with failure_threshold={self.config.failure_threshold}, "
            f"recovery_timeout={self.config.recovery_timeout}s"
        )

    @property
    def state(self) -> CircuitState:
        """Get current circuit breaker state."""
        return self._state.state

    @property
    def failure_count(self) -> int:
        """Get current failure count."""
        return self._state.failure_count

    @property
    def success_count(self) -> int:
        """Get current success count."""
        return self._state.success_count

    async def call(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Call a function with circuit breaker protection.
        
        Executes the function with circuit breaker protection, automatically
        tracking failures and successes and tripping the circuit when needed.
        
        Args:
            func: The async function to call
            *args: Positional arguments for the function
            **kwargs: Keyword arguments for the function
            
        Returns:
            The result of the function call
            
        Raises:
            CircuitBreakerOpenError: If circuit is open and recovery timeout not elapsed
            Exception: Re-raises the expected exception from the function
        """
        async with self._lock:
            if self._state.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self._state.state = CircuitState.HALF_OPEN
                    logger.info(f"Circuit breaker '{self.name}' transitioned to HALF_OPEN state")
                else:
                    logger.warning(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {time.time() - self._state.last_failure_time:.2f}s ago. "
                        f"Recovery timeout: {self.config.recovery_timeout}s"
                    )
                    raise CircuitBreakerOpenError(
                        f"Circuit breaker '{self.name}' is OPEN. "
                        f"Last failure: {self._state.last_failure_time:.2f}s ago. "
                        f"Recovery timeout: {self.config.recovery_timeout}s"
                    )

        try:
            result = await func(*args, **kwargs)
            
            async with self._lock:
                self._on_success()
            
            return result
            
        except self.config.expected_exception as e:
            async with self._lock:
                self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """
        Check if enough time has passed to attempt recovery.
        
        Returns True if the recovery timeout has elapsed since the last failure.
        
        Returns:
            Boolean indicating if reset should be attempted
        """
        return (
            time.time() - self._state.last_failure_time
            >= self.config.recovery_timeout
        )

    def _on_success(self) -> None:
        """
        Handle successful function execution.
        
        Resets failure count in closed state, or tracks consecutive successes
        in half-open state to determine if circuit should close.
        """
        if self._state.state == CircuitState.HALF_OPEN:
            self._state.success_count += 1
            logger.debug(
                f"Circuit breaker '{self.name}' success in HALF_OPEN: {self._state.success_count}/2"
            )
            if self._state.success_count >= 2:  # Need 2 consecutive successes
                self._reset()
                logger.info(f"Circuit breaker '{self.name}' recovered and transitioned to CLOSED state")
        else:
            self._state.failure_count = 0

    def _on_failure(self) -> None:
        """
        Handle failed function execution.
        
        Increments failure count and trips the circuit if threshold is exceeded.
        """
        self._state.failure_count += 1
        self._state.last_failure_time = time.time()
        self._state.success_count = 0

        logger.warning(
            f"Circuit breaker '{self.name}' failure: count={self._state.failure_count}, "
            f"threshold={self.config.failure_threshold}"
        )

        if (
            self._state.failure_count >= self.config.failure_threshold
            and self._state.state != CircuitState.OPEN
        ):
            self._state.state = CircuitState.OPEN
            logger.error(f"Circuit breaker '{self.name}' tripped to OPEN state")

    def _reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self._state.state = CircuitState.CLOSED
        self._state.failure_count = 0
        self._state.success_count = 0
        self._state.last_failure_time = 0.0

    def force_open(self) -> None:
        """
        Force the circuit breaker to open state.
        
        Manually trips the circuit breaker regardless of failure count.
        Useful for maintenance or emergency scenarios.
        """
        self._state.state = CircuitState.OPEN
        self._state.last_failure_time = time.time()
        logger.warning(f"Circuit breaker '{self.name}' forced to OPEN state")

    def force_close(self) -> None:
        """
        Force the circuit breaker to closed state.
        
        Manually closes the circuit breaker, resetting all counters.
        Useful for recovery after maintenance.
        """
        self._reset()
        logger.info(f"Circuit breaker '{self.name}' forced to CLOSED state")

    def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.
        
        Returns a dictionary containing the current state and configuration
        of the circuit breaker for monitoring and debugging.
        
        Returns:
            Dictionary with circuit breaker status information
        """
        return {
            "name": self.name,
            "state": self._state.state.value,
            "failure_count": self._state.failure_count,
            "success_count": self._state.success_count,
            "last_failure_time": self._state.last_failure_time,
            "failure_threshold": self.config.failure_threshold,
            "recovery_timeout": self.config.recovery_timeout,
        }


class CircuitBreakerOpenError(Exception):
    """
    Raised when circuit breaker is open.
    
    Exception raised when attempting to call a function through an open
    circuit breaker, indicating that the system is in a failed state
    and requests are being blocked.
    """
    pass


# Global circuit breaker registry
_circuit_breakers: Dict[str, CircuitBreaker] = {}


def get_circuit_breaker(
    name: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """
    Get or create a circuit breaker by name.
    
    Returns an existing circuit breaker with the given name, or creates
    a new one if it doesn't exist. Enables sharing circuit breakers
    across the application.
    
    Args:
        name: Name identifier for the circuit breaker
        config: Optional configuration for new circuit breakers
        
    Returns:
        CircuitBreaker instance
    """
    if name not in _circuit_breakers:
        _circuit_breakers[name] = CircuitBreaker(name, config)
        logger.info(f"Created new circuit breaker '{name}'")
    return _circuit_breakers[name]


def get_all_circuit_breaker_status() -> Dict[str, Dict[str, Any]]:
    """
    Get status of all registered circuit breakers.
    
    Returns a dictionary mapping circuit breaker names to their current
    status, useful for monitoring dashboards and health checks.
    
    Returns:
        Dictionary of circuit breaker statuses
    """
    return {
        name: cb.get_status() for name, cb in _circuit_breakers.items()
    }


def reset_all_circuit_breakers() -> None:
    """
    Reset all circuit breakers to closed state.
    
    Forces all registered circuit breakers to the closed state,
    resetting all failure counters. Useful for recovery after
    system-wide maintenance or outages.
    """
    for cb in _circuit_breakers.values():
        cb.force_close()
    logger.info(f"Reset all {len(_circuit_breakers)} circuit breakers to CLOSED state")
