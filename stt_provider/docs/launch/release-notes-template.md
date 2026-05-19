# Release Notes: Self-Hosted Streaming STT

## Release

Version:

Date:

Release owner:

Rollback owner:

## Summary

This release enables the self-hosted streaming STT backend using:

- FastAPI gateway
- NVIDIA Triton
- Parakeet streaming ASR
- Sortformer streaming diarization
- Postgres durable state
- Redis ephemeral counters
- Whisper fallback during rollout

## Customer impact

Expected impact:

- Lower dependency on external STT providers
- Tenant-level backend routing
- Word-level speaker labels
- Improved data-residency control
- Foundation for domain models and speaker enrollment

## Rollout plan

Rollout stages:

- [ ] Internal tenants
- [ ] 10% low-risk tenants
- [ ] 25% tenants
- [ ] 50% tenants
- [ ] 100% eligible tenants

Whisper fallback remains enabled throughout rollout.

## Validation completed

- [ ] Local validation passed
- [ ] Production validation passed
- [ ] Regional smoke tests passed
- [ ] 12-hour, 200-stream soak test passed
- [ ] P95 time-to-first-partial stayed under 700 ms
- [ ] WebSocket disconnect rate stayed below 1%
- [ ] Audit logs wrote successfully
- [ ] Usage counters wrote successfully
- [ ] Redis counters returned to zero after test completion

## Rollback plan

Rollback trigger examples:

- P95 time-to-first-partial exceeds 700 ms for 30 minutes
- WebSocket disconnect rate exceeds 1%
- Triton queue duration remains elevated
- GPU saturation cannot recover
- Audit logs or usage counters fail

Rollback action:

```text
tenant.backend = whisper
```

## Known limitations

- Speaker identity matching is disabled until privacy, encryption, audit, and confidence-threshold controls are approved.
- Domain models are limited to the approved model allowlist.
- Cross-region failover is disabled unless explicitly enabled per tenant.

## Approval

Engineering approver:

Security approver:

Infrastructure approver:

Support/on-call approver:

Final launch decision:
