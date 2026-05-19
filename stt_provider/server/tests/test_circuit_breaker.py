"""
Tests for circuit breaker functionality.

This module tests the CircuitBreaker implementation which provides fault
tolerance by blocking calls to failing services after a threshold is reached.
Tests verify state transitions (CLOSED, OPEN, HALF_OPEN), failure counting,
recovery behavior, forced state changes, and the global registry.

Run tests:
    pytest server/tests/test_circuit_breaker.py

Purpose:
This ensures that the circuit breaker properly protects the system from
cascading failures by temporarily blocking calls to failing backends,
allowing them time to recover before retrying.
"""
import asyncio
import logging

import pytest
from uuid import uuid4

from stt_server.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
    get_circuit_breaker,
    reset_all_circuit_breakers,
)

logger = logging.getLogger(__name__)


class DummyException(Exception):
    """Dummy exception for testing."""
    pass


@pytest.mark.asyncio
async def test_circuit_breaker_initial_state():
    """
    Test that circuit breaker starts in CLOSED state.
    
    Verifies that a newly created circuit breaker initializes in the CLOSED
    state with zero failure and success counts.
    """
    logger.info("Testing circuit breaker initial state")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
    
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    assert cb.success_count == 0
    
    logger.info("Initial state test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_opens_on_threshold():
    """
    Test that circuit breaker opens after failure threshold.
    
    Verifies that after the configured number of consecutive failures,
    the circuit breaker transitions to the OPEN state.
    """
    logger.info("Testing circuit breaker opens on threshold")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Fail twice to reach threshold
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    # Circuit should be open
    assert cb.state == CircuitState.OPEN
    assert cb.failure_count == 2
    
    logger.info("Circuit breaker opens on threshold test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_blocks_when_open():
    """
    Test that circuit breaker blocks calls when OPEN.
    
    Verifies that when the circuit is OPEN, calls are blocked and raise
    CircuitBreakerOpenError without executing the wrapped function.
    """
    logger.info("Testing circuit breaker blocks calls when open")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Fail twice to open circuit
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    # Try to call when open - should raise CircuitBreakerOpenError
    async def should_not_run():
        raise AssertionError("Function should not run when circuit is open")
    
    with pytest.raises(CircuitBreakerOpenError):
        await cb.call(should_not_run)
    
    logger.info("Circuit breaker blocks calls when open test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_resets_on_success():
    """
    Test that circuit breaker resets on successful calls.
    
    Verifies that a successful call resets the failure count to zero,
    preventing the circuit from opening due to isolated failures.
    """
    logger.info("Testing circuit breaker resets on success")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3))
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Fail twice (below threshold)
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    assert cb.failure_count == 2
    
    # Successful call should reset failure count
    async def success_func():
        return "success"
    
    result = await cb.call(success_func)
    assert result == "success"
    assert cb.failure_count == 0
    
    logger.info("Circuit breaker resets on success test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_recovery():
    """
    Test that circuit breaker transitions from HALF_OPEN to CLOSED on success.
    
    Verifies that after the recovery timeout, a successful call transitions
    the circuit from OPEN to HALF_OPEN, and another success transitions to CLOSED.
    """
    logger.info("Testing circuit breaker half-open recovery")
    
    cb = CircuitBreaker(
        "test",
        CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1),
    )
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Open circuit
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    # Wait for recovery timeout
    await asyncio.sleep(0.15)
    
    # Successful call should transition to HALF_OPEN then CLOSED
    async def success_func():
        return "success"
    
    result = await cb.call(success_func)
    assert result == "success"
    assert cb.state == CircuitState.CLOSED
    
    logger.info("Circuit breaker half-open recovery test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_half_open_failure():
    """
    Test that circuit breaker reopens on failure in HALF_OPEN.
    
    Verifies that if a call fails while in HALF_OPEN state, the circuit
    immediately reopens to the OPEN state.
    """
    logger.info("Testing circuit breaker half-open failure")
    
    cb = CircuitBreaker(
        "test",
        CircuitBreakerConfig(failure_threshold=2, recovery_timeout=0.1),
    )
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Open circuit
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    # Wait for recovery timeout
    await asyncio.sleep(0.15)
    
    # First success transitions to HALF_OPEN
    async def success_func():
        return "success"
    
    await cb.call(success_func)
    assert cb.state == CircuitState.HALF_OPEN
    
    # Failure in HALF_OPEN should reopen
    try:
        await cb.call(failing_func)
    except DummyException:
        pass
    
    assert cb.state == CircuitState.OPEN
    
    logger.info("Circuit breaker half-open failure test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_force_open():
    """
    Test forcing circuit breaker to OPEN state.
    
    Verifies that the force_open method can manually transition the circuit
    to OPEN state, blocking all subsequent calls.
    """
    logger.info("Testing circuit breaker force open")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=5))
    
    assert cb.state == CircuitState.CLOSED
    
    cb.force_open()
    assert cb.state == CircuitState.OPEN
    
    # Should block calls
    with pytest.raises(CircuitBreakerOpenError):
        async def dummy():
            return "test"
        await cb.call(dummy)
    
    logger.info("Circuit breaker force open test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_force_close():
    """
    Test forcing circuit breaker to CLOSED state.
    
    Verifies that the force_close method can manually transition the circuit
    to CLOSED state and reset the failure count.
    """
    logger.info("Testing circuit breaker force close")
    
    cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=2))
    
    async def failing_func():
        raise DummyException("Test error")
    
    # Open circuit
    for _ in range(2):
        try:
            await cb.call(failing_func)
        except DummyException:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    cb.force_close()
    assert cb.state == CircuitState.CLOSED
    assert cb.failure_count == 0
    
    logger.info("Circuit breaker force close test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_get_status():
    """
    Test getting circuit breaker status.
    
    Verifies that the get_status method returns a dictionary with the
    current state, counts, and configuration.
    """
    logger.info("Testing circuit breaker get status")
    
    cb = CircuitBreaker(
        "test",
        CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0),
    )
    
    status = cb.get_status()
    
    assert status["name"] == "test"
    assert status["state"] == "closed"
    assert status["failure_count"] == 0
    assert status["failure_threshold"] == 3
    assert status["recovery_timeout"] == 60.0
    
    logger.info("Circuit breaker get status test passed")


@pytest.mark.asyncio
async def test_global_circuit_breaker_registry():
    """
    Test global circuit breaker registry.
    
    Verifies that get_circuit_breaker returns the same instance for the
    same name (singleton pattern) and different instances for different names.
    """
    logger.info("Testing global circuit breaker registry")
    
    # Get circuit breaker with same name should return same instance
    cb1 = get_circuit_breaker("test_global")
    cb2 = get_circuit_breaker("test_global")
    
    assert cb1 is cb2
    
    # Different name should return different instance
    cb3 = get_circuit_breaker("test_global_2")
    assert cb1 is not cb3
    
    logger.info("Global circuit breaker registry test passed")


@pytest.mark.asyncio
async def test_reset_all_circuit_breakers():
    """
    Test resetting all circuit breakers.
    
    Verifies that reset_all_circuit_breakers closes all registered circuit
    breakers and resets their failure counts.
    """
    logger.info("Testing reset all circuit breakers")
    
    cb1 = get_circuit_breaker("reset_test_1")
    cb2 = get_circuit_breaker("reset_test_2")
    
    # Force open both
    cb1.force_open()
    cb2.force_open()
    
    assert cb1.state == CircuitState.OPEN
    assert cb2.state == CircuitState.OPEN
    
    # Reset all
    reset_all_circuit_breakers()
    
    # Both should be closed now
    assert cb1.state == CircuitState.CLOSED
    assert cb2.state == CircuitState.CLOSED
    
    logger.info("Reset all circuit breakers test passed")


@pytest.mark.asyncio
async def test_circuit_breaker_with_different_exceptions():
    """
    Test circuit breaker with specific expected exception type.
    
    Verifies that when an expected_exception is configured, only exceptions
    of that type trigger the circuit breaker. Other exceptions are ignored.
    """
    logger.info("Testing circuit breaker with specific exception type")
    
    cb = CircuitBreaker(
        "test",
        CircuitBreakerConfig(failure_threshold=2, expected_exception=ValueError),
    )
    
    async def raise_value_error():
        raise ValueError("Test error")
    
    async def raise_type_error():
        raise TypeError("Different error")
    
    # ValueError should trigger circuit breaker
    for _ in range(2):
        try:
            await cb.call(raise_value_error)
        except ValueError:
            pass
    
    assert cb.state == CircuitState.OPEN
    
    # Close it
    cb.force_close()
    
    # TypeError should not trigger circuit breaker (not expected type)
    try:
        await cb.call(raise_type_error)
    except TypeError:
        pass
    
    # Should still be closed
    assert cb.state == CircuitState.CLOSED
    
    logger.info("Circuit breaker with specific exception type test passed")
