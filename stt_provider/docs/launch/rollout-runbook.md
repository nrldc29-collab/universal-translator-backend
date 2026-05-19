# Self-Hosted Streaming STT Rollout Runbook

## Goal

Roll out the self-hosted Triton + Parakeet + Sortformer backend safely while keeping the Whisper backend available as fallback.

## Prerequisites

- Production readiness scorecard is complete.
- All required launch categories score `3`.
- 12-hour, 200-stream soak test has passed.
- GPU capacity is reserved.
- Status page is live.
- On-call rotation is active.
- Rollback owner is assigned.

## Rollout stages

### Stage 1: Internal tenants

- Enable `STT_BACKEND=triton` for internal test tenants only.
- Monitor for 24 hours.
- Compare latency and disconnects against Phase 1 baseline.

Proceed only if:

- P95 time-to-first-partial stays under 700 ms.
- Disconnect rate stays below 1%.
- No uncontrolled Triton restarts occur.

### Stage 2: 10% low-risk tenants

- Enable Triton backend for 10% of low-risk tenants.
- Keep Whisper fallback enabled.
- Monitor for 24 hours.

Rollback if:

- P95 latency exceeds launch target for 30 minutes.
- Disconnect rate exceeds 1%.
- GPU queue duration remains elevated.
- Audit logs or usage counters fail.

### Stage 3: 25% tenants

- Increase rollout to 25%.
- Monitor GPU utilization, Triton queue duration, Redis counters, and WebSocket session stability.

### Stage 4: 50% tenants

- Increase rollout to 50%.
- Confirm support volume does not increase materially.
- Confirm status page remains green.

### Stage 5: 100% tenants

- Enable Triton backend for all eligible tenants.
- Keep Whisper fallback available until production metrics are stable for at least 2 weeks.

## Rollback procedure

Set affected tenants back to the Whisper backend.

```text
tenant.backend = whisper
```

Then verify:

- New WebSocket sessions use Whisper.
- Existing Triton sessions drain naturally.
- Audit log records the rollback.
- Incident notes include reason, scope, and owner.

## Success criteria

Rollout is complete when:

- 100% of eligible tenants use Triton.
- Whisper fallback has not been needed for 2 weeks.
- Latency targets remain stable.
- Disconnect rate remains below 1%.
- No unresolved SEV-1 or SEV-2 incidents remain open.
