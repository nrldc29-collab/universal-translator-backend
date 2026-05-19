# Regional Smoke Test Checklist

## Goal

Confirm each production region can accept authenticated WebSocket traffic, route to the correct regional backend, and return a transcript event.

## Required regions

Run the smoke test for:

- [ ] `us-east-1` 
- [ ] `us-west-2` 
- [ ] `eu-west-1` 

## Pre-test checks

Before running the smoke test, verify:

- [ ] Regional gateway deployment is healthy
- [ ] Regional Triton deployment is healthy
- [ ] Parakeet model is loaded
- [ ] Sortformer model is loaded
- [ ] Redis is reachable
- [ ] Postgres is reachable
- [ ] TLS certificate is valid
- [ ] `REGION` environment variable matches the region being tested
- [ ] Test tenant `home_region` matches the region being tested

## Test command

```bash
python scripts/regional_smoke_test.py \
  --websocket-url "wss://REGION.example.com/stt/stream" \
  --api-key "$STT_API_KEY" \
  --expected-region "REGION"
```

## Pass criteria

A region passes when:

- [ ] WebSocket connection succeeds
- [ ] Authentication succeeds
- [ ] First audio chunk is accepted
- [ ] First transcript event is returned within 10 seconds
- [ ] No cross-region routing violation occurs
- [ ] Regional routing audit event is written
- [ ] Gateway logs include a trace ID
- [ ] No Triton errors are emitted
- [ ] No Redis counter errors are emitted
- [ ] No Postgres write errors are emitted

## Failure handling

If a region fails:

- [ ] Mark the region as not ready for tenant traffic
- [ ] Keep tenant routing disabled for that region
- [ ] Check gateway logs by trace ID
- [ ] Check Triton model readiness
- [ ] Check Redis active-connection counters
- [ ] Check Postgres audit-log writes
- [ ] Re-run the smoke test after remediation

## Launch rule

Do not assign production tenants to a region until the regional smoke test passes and the status page component is live.

This gives you a repeatable checklist for validating each co-located GPU region before assigning tenants there. The guide's co-located GPU regions step requires regional GPU pools, regional routing, and tenant data-residency enforcement.

Next step pointer: **Final step — Add regional failover runbook**
