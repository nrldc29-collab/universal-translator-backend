# Production Smoke Test Checklist

## Goal

Confirm every production regional WebSocket endpoint can accept authenticated streaming traffic and return a transcript event before tenant rollout.

## Required command

Run:

```bash
PRODUCTION_STT_API_KEY="replace-me" ./scripts/production_smoke_test.sh
```

## Required production regions

- [ ] us-east-1
- [ ] us-west-2
- [ ] eu-west-1

## Pass criteria

Each production region passes only when:

- [ ] WebSocket connection succeeds
- [ ] Authentication succeeds
- [ ] First audio chunk is accepted
- [ ] First transcript event returns within 10 seconds
- [ ] Gateway logs include a trace ID
- [ ] Regional routing allows the correct production region
- [ ] No cross-region routing violation occurs
- [ ] Triton readiness remains healthy
- [ ] Parakeet model readiness is healthy
- [ ] Sortformer model readiness is healthy
- [ ] Redis active-connection counters increment and decrement
- [ ] Audit-log write succeeds
- [ ] Usage-counter write succeeds
- [ ] Status page component remains healthy
- [ ] On-call alerts do not fire unexpectedly

## Failure handling

If any production region fails:

- [ ] Stop tenant rollout
- [ ] Mark the failed region as not ready
- [ ] Keep tenants off the failed region
- [ ] Check gateway logs by trace ID
- [ ] Check Triton readiness
- [ ] Check Parakeet model readiness
- [ ] Check Sortformer model readiness
- [ ] Check Redis counter writes
- [ ] Check Postgres audit and usage writes
- [ ] Re-run production smoke tests after remediation

## Tenant rollout gate

Do not enable Triton for production tenants until:

- [ ] Production validation script passes
- [ ] Production smoke tests pass in every target region
- [ ] 12-hour, 200-stream soak test passes
- [ ] Whisper fallback is enabled
- [ ] Rollback owner is assigned
- [ ] Status page is live
- [ ] On-call rotation is active
