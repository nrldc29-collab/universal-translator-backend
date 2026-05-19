# Tenant Rollout Cohort Template

## Goal

Track which tenants move from Whisper fallback to the self-hosted Triton backend during staged rollout.

## Cohort summary

Cohort name:

Rollout stage:

- [ ] Internal tenants
- [ ] 10% low-risk tenants
- [ ] 25% tenants
- [ ] 50% tenants
- [ ] 100% eligible tenants

Rollout owner:

Rollback owner:

Start date:

End date:

## Tenant list

| Tenant ID | Tenant name | Home region | Current backend | Target backend | Fallback enabled | Status | Notes |
|---|---|---|---|---|---|---|---|
|  |  |  | whisper | triton | yes | pending |  |

## Pre-rollout checks

- [ ] Production validation passed
- [ ] Production smoke tests passed
- [ ] 12-hour, 200-stream soak test passed
- [ ] Whisper fallback is enabled
- [ ] Rollback owner is assigned
- [ ] Status page is live
- [ ] On-call rotation is active
- [ ] No open SEV-1 or SEV-2 incidents
- [ ] Tenant home regions are configured
- [ ] Tenant stream limits are configured

## Rollout command

For each tenant in the cohort:

```sql
UPDATE tenants
SET
    backend = 'triton',
    allow_backend_fallback = true
WHERE id = 'TENANT_ID';
```

## Monitoring window

Monitor each cohort for at least 24 hours.

Track:

- P95 time-to-first-partial
- P95 time-between-partials
- WebSocket disconnect rate
- Triton inference queue duration
- GPU utilization
- Redis counter accuracy
- Audit-log write success
- Usage-counter write success
- Support tickets
- Rollback events

## Rollback trigger

Rollback the cohort if any of these occur:

- P95 time-to-first-partial exceeds 700 ms for 30 minutes
- WebSocket disconnect rate exceeds 1%
- Triton queue duration remains elevated
- GPU saturation cannot recover
- Audit-log writes fail
- Usage-counter writes fail
- Customer-impacting transcript failures are confirmed

## Rollback command

```sql
UPDATE tenants
SET backend = 'whisper'
WHERE id IN (
    'TENANT_ID'
);
```

## Cohort decision

Final status:

- [ ] Approved to proceed to next cohort
- [ ] Paused
- [ ] Rolled back

Decision reason:

Approver:
