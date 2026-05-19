# Changelog

## v0.2.0-self-hosted-stt

### Added

- Self-hosted streaming STT architecture decision record
- GPU Kubernetes deployment plan
- NVIDIA Triton deployment templates
- Parakeet streaming ASR backend path
- Sortformer streaming diarization plan
- FastAPI gateway deployment template
- Triton gRPC client wrapper
- Tenant backend routing between `triton` and `whisper` 
- Whisper fallback during rollout
- Postgres durable state for tenants, API keys, usage counters, and audit logs
- Redis ephemeral counters for active streams and rate limits
- Connection draining and PodDisruptionBudgets
- KEDA autoscaling for gateway and Triton
- Per-tenant API-key RBAC scopes
- Per-tenant audit logging
- Usage API
- Domain model registry and `GET /v1/models` 
- Tenant default model admin endpoint
- Request-level model override support
- Speaker enrollment storage and API plan
- Speaker embedding encryption support
- Delete-my-voiceprint endpoint
- Speaker identity schema and confidence threshold enforcement
- Regional routing and regional failover controls
- Production validation scripts and launch checklists
- Rollout, rollback, incident response, monitoring, and alerting runbooks

### Changed

- Removed unsafe development API-key default
- Replaced temp-WAV streaming path with direct PCM-16LE to NumPy `float32` conversion
- Added decoder knobs for streaming and REST transcription
- Added structured JSON logging with trace IDs
- Cached API-key map lookup
- Switched implementation focus from Phase 2A cloud-first to Phase 2B self-hosted

### Security

- Added explicit production API-key requirement
- Added API-key scope enforcement
- Added audit events for backend routing, fallback, model overrides, speaker enrollment, regional routing, and tenant settings
- Added encrypted speaker embedding storage
- Added delete-my-voiceprint behavior for biometric voice data

### Operational readiness

- Added production validation checklist
- Added regional smoke test checklist
- Added 12-hour, 200-stream load test plan
- Added status page plan
- Added SOC 2 Type II evidence collection plan
- Added production launch decision record
