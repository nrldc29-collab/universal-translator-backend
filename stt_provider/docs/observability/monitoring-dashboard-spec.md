# Streaming STT Monitoring Dashboard Spec

## Goal

Create one production dashboard that shows gateway, Triton, GPU, Redis, Postgres, latency, and rollout health for the self-hosted streaming STT platform.

## Dashboard sections

### 1. Customer-facing health

Track:

- Active WebSocket sessions
- WebSocket connect rate
- WebSocket disconnect rate
- Gateway 4xx rate
- Gateway 5xx rate
- Current backend split: Triton vs Whisper
- Affected tenants during incident or rollback

### 2. Streaming latency

Track:

- P50 time-to-first-partial
- P95 time-to-first-partial
- P50 time-between-partials
- P95 time-between-partials
- Final transcript latency
- End-of-utterance processing latency

### 3. Triton inference

Track:

- Triton request rate
- Triton error rate
- Triton inference queue duration
- Triton model load status
- Parakeet model availability
- Sortformer model availability
- Per-model inference latency

### 4. GPU health

Track:

- GPU utilization
- GPU memory utilization
- GPU temperature
- GPU power usage
- GPU node availability
- GPU node restarts
- DCGM exporter health

### 5. Redis health

Track:

- Redis availability
- Redis command latency
- Active connection counter accuracy
- Per-tenant active connection counters
- Rate-limit counter writes
- Redis failover events

### 6. Postgres health

Track:

- Postgres availability
- Query latency
- Connection pool usage
- Usage-counter write success
- Audit-log write success
- Replication lag
- Backup status

### 7. Rollout safety

Track:

- Tenants on Triton
- Tenants on Whisper fallback
- Rollback events
- Error rate by backend
- Latency by backend
- Disconnect rate by backend

## Required alerts

Create alerts for:

- P95 time-to-first-partial over 700 ms for 30 minutes
- WebSocket disconnect rate over 1%
- Triton inference queue duration above threshold
- Triton pod crash loop
- GPU saturation without recovery
- Redis unavailable
- Postgres unavailable
- Audit-log writes failing
- Usage-counter writes failing
- Status page component unhealthy

## Acceptance checks

- Dashboard exists in production observability tool.
- On-call can see gateway, Triton, GPU, Redis, and Postgres health in one place.
- Alerts route to on-call.
- Dashboard can distinguish Triton issues from gateway issues.
- Dashboard can compare Triton backend metrics against Whisper fallback metrics.

This supports the guide's self-hosted path by monitoring the exact systems introduced in Phase 2B: GPU Kubernetes, Triton, Parakeet, Sortformer, Redis counters, Postgres state, connection draining, autoscaling, and rollout safety
