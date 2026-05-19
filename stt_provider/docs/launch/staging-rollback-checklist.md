# Staging Rollback Checklist: Self-Hosted Streaming STT

## Goal

Safely roll staging back to the Whisper fallback path if the self-hosted Triton backend fails validation.

## Rollback triggers

Start staging rollback if any of these happen:

- Gateway deployment fails rollout
- Triton StatefulSet fails rollout
- Triton readiness check fails
- Parakeet model does not load
- Sortformer model does not load
- Redis counters fail
- Postgres usage writes fail
- Audit-log writes fail
- Regional smoke test fails
- WebSocket sessions disconnect unexpectedly
- P95 time-to-first-partial exceeds target during staging validation

## Rollback action

Set staging tenants back to Whisper:

```sql
UPDATE tenants
SET backend = 'whisper'
WHERE backend = 'triton';
```

Then restart gateway pods if needed:

```bash
kubectl -n stt rollout restart deployment/stt-gateway
kubectl -n stt rollout status deployment/stt-gateway
```

## Verification

After rollback, confirm:

- [ ] New staging WebSocket sessions use Whisper
- [ ] Triton sessions drain naturally
- [ ] Gateway readiness passes
- [ ] Gateway liveness passes
- [ ] Usage counters still write
- [ ] Audit logs record the backend change
- [ ] Regional routing still blocks invalid cross-region traffic
- [ ] Staging validation failure is documented

## Completion criteria

Staging rollback is complete when:

- All staging tenants are stable on Whisper
- Gateway is healthy
- Failed Triton rollout is paused
- Incident notes include cause, scope, mitigation, and owner
- Follow-up fix is assigned before retrying self-hosted validation
