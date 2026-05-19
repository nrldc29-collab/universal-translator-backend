# Production Readiness Scorecard

Score each category from 0 to 3.

## Scoring

- 0 = Not started
- 1 = Designed but not implemented
- 2 = Implemented but not validated in production-like conditions
- 3 = Implemented, tested, documented, and ready for production

## Scorecard

| Category | Score | Required for launch | Notes |
|---|---:|---|---|
| Architecture ADR | 0 | Yes | Self-hosted decision documented |
| API-key security | 0 | Yes | No dev default outside dev |
| Streaming latency baseline | 0 | Yes | Phase 1 metrics captured |
| Triton deployment | 0 | Yes | Parakeet loaded and reachable |
| Sortformer diarization | 0 | Yes | Word-level speakers emitted |
| GPU capacity | 0 | Yes | Minimum 2 reserved GPU nodes |
| Postgres state | 0 | Yes | Tenants, keys, usage, audit log |
| Redis ephemeral counters | 0 | Yes | Active sessions and rate limits |
| Connection draining | 0 | Yes | Rolling restarts preserve sessions |
| KEDA autoscaling | 0 | Yes | Gateway and Triton scaling configured |
| Load testing | 0 | Yes | 12-hour, 200-stream soak test passed |
| Multi-AZ deployment | 0 | Yes | Gateway, Triton, Postgres, Redis |
| API-key RBAC | 0 | Yes | Scoped route access enforced |
| Audit logging | 0 | Yes | Tenant-visible audit events |
| Status page | 0 | Yes | Public components and SEV process |
| SOC 2 evidence | 0 | Yes | Evidence platform connected |
| Domain models | 0 | No | Differentiation feature |
| Speaker enrollment | 0 | No | Requires biometric controls |
| Regional GPU pools | 0 | No | Needed for latency-sensitive tenants |

## Launch rule

Production launch is allowed only when every `Required for launch` item has a score of `3`.

## Current launch status

Not ready for production.

This gives you a simple production-readiness gate for the self-hosted path: every required launch category must be implemented, tested, documented, and production-ready before release.
