# Self-Hosted Streaming STT Rollback Checklist

## Goal

Safely move affected tenants from the self-hosted Triton backend back to the Whisper fallback backend during rollout issues.

## Rollback triggers

Start rollback if any of these happen:

- P95 time-to-first-partial exceeds 700 ms for 30 minutes
- WebSocket disconnect rate exceeds 1%
- Triton inference queue duration remains elevated
- GPU utilization is saturated and autoscaling cannot recover
- Redis connection counters become inaccurate
- Usage counters fail to write
- Audit logs fail to write
- Triton pods restart repeatedly
- Customer-impacting transcript errors are confirmed

## Rollback action

Set affected tenants back to Whisper:

```text
tenant.backend = whisper
```

## Verification

After rollback, confirm:

- New WebSocket sessions use Whisper
- Existing Triton sessions drain naturally
- No new sessions are routed to Triton for rolled-back tenants
- Error rate returns to normal
- P95 latency returns to the Phase 1 baseline range
- Usage counters continue writing
- Audit events record the rollback
- Support and on-call teams are notified

## Audit event

Record this event:

```json
{
  "event_type": "tenant.backend_rollback",
  "resource": "stt_backend",
  "payload": {
    "from_backend": "triton",
    "to_backend": "whisper",
    "reason": "rollback trigger exceeded",
    "scope": "affected tenants"
  }
}
```

## Status page

Update the public status page if rollback is caused by customer-visible impact.

Include:

- Affected region
- Affected service
- Customer impact
- Mitigation status
- Next update time

## Completion criteria

Rollback is complete when:

- Affected tenants are stable on Whisper
- Triton sessions have drained
- Metrics are back within acceptable range
- Incident notes are updated
- Follow-up owner is assigned
