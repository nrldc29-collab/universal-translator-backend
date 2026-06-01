"""Tests for backend.circuit_breaker."""
import asyncio
import pytest
from backend.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerOpenError,
    CircuitState,
)


async def _ok():
    return "ok"


async def _fail():
    raise ValueError("service error")


class TestCircuitBreakerInitialState:
    def setup_method(self):
        self.cb = CircuitBreaker("test", CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0))

    def test_initial_state_is_closed(self):
        assert self.cb.state == CircuitState.CLOSED

    def test_initial_stats_are_zero(self):
        assert self.cb.stats.total_calls == 0
        assert self.cb.stats.failed_calls == 0


class TestCircuitBreakerClosed:
    def setup_method(self):
        cfg = CircuitBreakerConfig(failure_threshold=3, recovery_timeout=60.0, timeout=5.0)
        self.cb = CircuitBreaker("test", cfg)

    @pytest.mark.asyncio
    async def test_successful_call_passes_through(self):
        result = await self.cb.call(_ok)
        assert result == "ok"
        assert self.cb.stats.successful_calls == 1

    @pytest.mark.asyncio
    async def test_failed_call_increments_failure_count(self):
        with pytest.raises(ValueError):
            await self.cb.call(_fail)
        assert self.cb.stats.failed_calls == 1

    @pytest.mark.asyncio
    async def test_reaches_threshold_and_opens(self):
        for _ in range(3):
            with pytest.raises(ValueError):
                await self.cb.call(_fail)
        assert self.cb.state == CircuitState.OPEN

    @pytest.mark.asyncio
    async def test_open_circuit_raises_open_error(self):
        for _ in range(3):
            with pytest.raises(ValueError):
                await self.cb.call(_fail)
        with pytest.raises(CircuitBreakerOpenError):
            await self.cb.call(_ok)
        assert self.cb.stats.rejected_calls == 1


class TestCircuitBreakerRecovery:
    @pytest.mark.asyncio
    async def test_successful_calls_reset_failure_count(self):
        cfg = CircuitBreakerConfig(failure_threshold=3, timeout=5.0)
        cb = CircuitBreaker("test", cfg)
        with pytest.raises(ValueError):
            await cb.call(_fail)
        await cb.call(_ok)
        assert cb._failure_count == 0

    @pytest.mark.asyncio
    async def test_half_open_success_closes_circuit(self):
        cfg = CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.0,
            success_threshold=1,
            timeout=5.0,
        )
        cb = CircuitBreaker("test", cfg)
        for _ in range(2):
            with pytest.raises(ValueError):
                await cb.call(_fail)
        assert cb.state == CircuitState.OPEN
        # Force immediate recovery by making time already elapsed
        cb.stats.last_failure_time = 0.0
        await cb.call(_ok)
        assert cb.state == CircuitState.CLOSED


class TestCircuitBreakerConfig:
    def test_default_config_values(self):
        cfg = CircuitBreakerConfig()
        assert cfg.failure_threshold == 5
        assert cfg.recovery_timeout == 30.0
        assert cfg.success_threshold == 2
        assert cfg.timeout == 10.0
