"""
True Streaming STT Provider Server Package.

This package contains the core server implementation for the True Streaming
Speech-to-Text provider, including WebSocket streaming, audio validation,
tenant management, authentication, rate limiting, circuit breaker patterns,
and backend routing for transcription services.

Key modules:
- main: FastAPI application and health check endpoints
- streaming: Streaming transcription session management
- websocket_validation: WebSocket message validation
- audio_validation: Audio data validation for PCM16 format
- auth: JWT token authentication and validation
- rbac: Role-based access control
- tenant_throttling: Per-tenant request and stream throttling
- circuit_breaker: Circuit breaker pattern for fault tolerance
- backend_routing: Backend selection and routing
- backend_fallback: Backend fallback with circuit breaker protection
- model_registry: Model ID validation and registry
- audit: Audit event logging
- rate_limits: Redis-backed rate limiting
- connection_counters: Redis-backed connection tracking
- metrics: Prometheus metrics collection
- security: Security utilities and helpers
- logging_utils: Structured logging utilities
"""