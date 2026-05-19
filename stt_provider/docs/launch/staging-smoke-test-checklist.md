# Staging Smoke Test Checklist

## Goal

Confirm every staging regional WebSocket endpoint can accept authenticated streaming traffic and return a transcript event before production rollout.

## Required command

Run:

```bash
STAGING_STT_API_KEY="replace-me" ./scripts/staging_smoke_test.sh
```

## Required staging regions

- [ ] us-east-1
- [ ] us-west-2
- [ ] eu-west-1

## Pass criteria

Each staging region passes only when:

- [ ] WebSocket connection succeeds
- [ ] Authentication succeeds
- [ ] First audio chunk is accepted
- [ ] First transcript event returns within 10 seconds
- [ ] Gateway logs include a trace ID
- [ ] Regional routing allows the correct staging region
- [ ] No cross-region routing violation occurs
- [ ] Triton readiness remains healthy
- [ ] Redis active-connection counters increment and decrement
- [ ] Audit-log write succeeds
- [ ] Usage-counter write succeeds

## Failure handling

If any staging region fails:

- [ ] Stop production rollout preparation
- [ ] Mark the failed region as not ready
- [ ] Check gateway logs by trace ID
- [ ] Check Triton readiness
- [ ] Check Parakeet model readiness
- [ ] Check Sortformer model readiness
- [ ] Check Redis counter writes
- [ ] Check Postgres audit and usage writes
- [ ] Re-run staging smoke tests after the fix

## Production gate

Do not run production smoke tests until all staging regions pass.
