# Production Launch Decision Record

## Decision

Production launch is not approved until every required launch gate is complete.

## Required launch gates

The self-hosted streaming STT platform may launch only when:

- Phase 0 ADR is complete
- Phase 1 quick wins are implemented
- Phase 1 baseline metrics are captured
- Phase 2B self-hosted backend is deployed
- GPU capacity is reserved
- Triton loads Parakeet and Sortformer
- Gateway-to-Triton gRPC path is validated
- Postgres durable state is live
- Redis ephemeral counters are live
- Connection draining is tested
- KEDA autoscaling is configured
- 12-hour, 200-stream soak test passes
- Whisper fallback is enabled during rollout
- Phase 3 enterprise hardening requirements are complete
- Public status page is live
- On-call alerting is active
- SOC 2 evidence collection has started

## Explicit non-launch conditions

Do not launch if any of these are true:

- Triton is not stable under soak test
- GPU capacity is not reserved
- Rolling restarts drop active sessions
- Audit logs fail to write
- Usage counters fail to write
- Redis active-connection counters are inaccurate
- P95 time-to-first-partial exceeds target
- WebSocket disconnect rate exceeds 1%
- Whisper fallback is unavailable
- Status page or on-call routing is not ready

## Launch approval

Before launch, record:

- Launch owner:
- Engineering approver:
- Security approver:
- Infrastructure approver:
- Support/on-call approver:
- Launch date:
- Rollback owner:
- First customer or tenant cohort:

## Final launch decision

Status: Not approved

Reason:

Required launch gates are not yet fully validated in production-like conditions.

This creates the final go/no-go record for the self-hosted launch. It ties together the guide's required self-hosted backend work, enterprise hardening, load testing, fallback rollout, and operational readiness requirements.
