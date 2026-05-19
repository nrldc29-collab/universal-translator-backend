# Soak Test Execution Checklist

## Goal

Validate the self-hosted Triton backend under production-like streaming load before tenant rollout.

## Required test profile

Run a 12-hour soak test with:

- [ ] 200 concurrent WebSocket streams
- [ ] Realistic PCM-16LE audio chunks
- [ ] Triton backend enabled
- [ ] Whisper fallback enabled
- [ ] Redis active-connection counters enabled
- [ ] Postgres usage counters enabled
- [ ] Per-tenant audit logging enabled
- [ ] Prometheus metrics enabled
- [ ] On-call monitoring enabled

## Required disruption tests

During the soak test, perform:

- [ ] Rolling restart of gateway pods
- [ ] Rolling restart of Triton pods
- [ ] Redis failover test, if staging environment supports it
- [ ] Postgres failover test, if staging environment supports it
- [ ] KEDA scale-up validation
- [ ] KEDA scale-down validation

## Metrics to capture

- [ ] P50 time-to-first-partial
- [ ] P95 time-to-first-partial
- [ ] P50 time-between-partials
- [ ] P95 time-between-partials
- [ ] Final transcript latency
- [ ] WebSocket disconnect rate
- [ ] Triton inference queue duration
- [ ] Triton error rate
- [ ] GPU utilization
- [ ] GPU memory utilization
- [ ] Redis command latency
- [ ] Redis counter accuracy
- [ ] Postgres write latency
- [ ] Audit-log write success rate
- [ ] Usage-counter write success rate

## Pass criteria

The soak test passes only when:

- [ ] Test runs for 12 hours
- [ ] 200 concurrent streams are sustained
- [ ] P95 time-to-first-partial stays under 700 ms
- [ ] P95 time-between-partials stays under 700 ms
- [ ] WebSocket disconnect rate stays below 1%
- [ ] Rolling gateway restarts do not drop active sessions
- [ ] Triton remains available during pod restarts
- [ ] Redis active-connection counters return to zero after test completion
- [ ] Audit logs write successfully
- [ ] Usage counters write successfully
- [ ] No unresolved SEV-1 or SEV-2 incident remains open

## Failure handling

If the soak test fails:

- [ ] Stop production rollout
- [ ] Keep affected tenants on Whisper
- [ ] Record failed metric and timestamp
- [ ] Save gateway, Triton, Redis, Postgres, and GPU logs
- [ ] Assign an owner
- [ ] Re-run the full 12-hour soak test after remediation
