"""Service health management for graceful degradation.

Monitors external service health and provides fallback strategies
when services are unavailable or degraded.
"""

import logging
from dataclasses import dataclass, field
from enum import Enum
from time import time
from typing import Any

logger = logging.getLogger("anai_translator.service_health")


class ServiceStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNAVAILABLE = "unavailable"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    name: str
    status: ServiceStatus = ServiceStatus.UNKNOWN
    last_check_time: float = 0.0
    last_success_time: float = 0.0
    last_failure_time: float = 0.0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    failure_threshold: int = 3
    recovery_threshold: int = 2
    check_interval_seconds: float = 30.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def should_use_service(self) -> bool:
        """Determine if service should be used based on health status."""
        if self.status == ServiceStatus.HEALTHY:
            return True
        if self.status == ServiceStatus.UNAVAILABLE:
            return False
        # DEGRADED: allow but with caution
        return True

    def record_success(self, metadata: dict[str, Any] | None = None) -> None:
        """Record a successful service interaction."""
        self.last_success_time = time()
        self.last_check_time = time()
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        if metadata:
            self.metadata.update(metadata)

        if self.status == ServiceStatus.UNAVAILABLE and self.consecutive_successes >= self.recovery_threshold:
            self.status = ServiceStatus.DEGRADED
            logger.info("Service recovered to degraded: name=%s", self.name)
        elif self.status == ServiceStatus.DEGRADED and self.consecutive_successes >= self.recovery_threshold:
            self.status = ServiceStatus.HEALTHY
            logger.info("Service recovered to healthy: name=%s", self.name)

    def record_failure(self, metadata: dict[str, Any] | None = None) -> None:
        """Record a failed service interaction."""
        self.last_failure_time = time()
        self.last_check_time = time()
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        if metadata:
            self.metadata.update(metadata)

        if self.status == ServiceStatus.HEALTHY and self.consecutive_failures >= self.failure_threshold:
            self.status = ServiceStatus.DEGRADED
            logger.warning("Service degraded: name=%s failures=%d", self.name, self.consecutive_failures)
        elif self.status == ServiceStatus.DEGRADED and self.consecutive_failures >= self.failure_threshold:
            self.status = ServiceStatus.UNAVAILABLE
            logger.warning("Service unavailable: name=%s failures=%d", self.name, self.consecutive_failures)

    def get_health_summary(self) -> dict[str, Any]:
        """Get a summary of service health for diagnostics."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check_time": self.last_check_time,
            "last_success_time": self.last_success_time,
            "last_failure_time": self.last_failure_time,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "failure_threshold": self.failure_threshold,
            "recovery_threshold": self.recovery_threshold,
            "metadata": self.metadata,
        }


class ServiceHealthManager:
    """Manages health monitoring for multiple services."""

    def __init__(self):
        self.services: dict[str, ServiceHealth] = {}
        self._register_default_services()

    def _register_default_services(self) -> None:
        """Register default services to monitor."""
        self.register_service(
            "cip_external",
            failure_threshold=3,
            recovery_threshold=2,
            check_interval_seconds=30.0,
        )
        self.register_service(
            "stt_provider",
            failure_threshold=3,
            recovery_threshold=2,
            check_interval_seconds=30.0,
        )
        self.register_service(
            "tts",
            failure_threshold=5,
            recovery_threshold=3,
            check_interval_seconds=60.0,
        )

    def register_service(
        self,
        name: str,
        failure_threshold: int = 3,
        recovery_threshold: int = 2,
        check_interval_seconds: float = 30.0,
    ) -> ServiceHealth:
        """Register a new service for health monitoring."""
        service = ServiceHealth(
            name=name,
            failure_threshold=failure_threshold,
            recovery_threshold=recovery_threshold,
            check_interval_seconds=check_interval_seconds,
        )
        self.services[name] = service
        logger.info("Service registered for health monitoring: name=%s", name)
        return service

    def get_service(self, name: str) -> ServiceHealth | None:
        """Get a service by name."""
        return self.services.get(name)

    def record_success(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        """Record a successful interaction with a service."""
        service = self.get_service(name)
        if service:
            service.record_success(metadata)

    def record_failure(self, name: str, metadata: dict[str, Any] | None = None) -> None:
        """Record a failed interaction with a service."""
        service = self.get_service(name)
        if service:
            service.record_failure(metadata)

    def should_use_service(self, name: str) -> bool:
        """Check if a service should be used based on its health."""
        service = self.get_service(name)
        if not service:
            return True  # Unknown services are assumed healthy
        return service.should_use_service()

    def get_all_health_summaries(self) -> dict[str, dict[str, Any]]:
        """Get health summaries for all services."""
        return {name: service.get_health_summary() for name, service in self.services.items()}

    def get_degraded_services(self) -> list[str]:
        """Get list of services that are currently degraded or unavailable."""
        return [
            name
            for name, service in self.services.items()
            if service.status in (ServiceStatus.DEGRADED, ServiceStatus.UNAVAILABLE)
        ]


# Global service health manager instance
_service_health_manager = ServiceHealthManager()


def get_service_health_manager() -> ServiceHealthManager:
    """Get the global service health manager instance."""
    return _service_health_manager


def record_service_success(name: str, metadata: dict[str, Any] | None = None) -> None:
    """Convenience function to record service success."""
    _service_health_manager.record_success(name, metadata)


def record_service_failure(name: str, metadata: dict[str, Any] | None = None) -> None:
    """Convenience function to record service failure."""
    _service_health_manager.record_failure(name, metadata)


def should_use_service(name: str) -> bool:
    """Convenience function to check if service should be used."""
    return _service_health_manager.should_use_service(name)
