# Regional Failover Runbook

## Goal

Move tenant streaming traffic away from an unhealthy GPU region while respecting tenant data-residency and cross-region failover policy.

## Failover triggers

Start regional failover when any of these happen:

- Regional gateway outage
- Regional Triton outage
- GPU node pool unavailable
- Triton inference queue duration remains elevated
- Regional Redis unavailable
- Regional ingress or TLS failure
- Regional P95 time-to-first-partial exceeds target for 30 minutes

## Pre-check

Before failing over a tenant, confirm:

- [ ] Tenant has `allow_cross_region_failover = true` 
- [ ] Target failover region is healthy
- [ ] Target region has GPU capacity
- [ ] Target region has gateway, Triton, Redis, metrics, and logging available
- [ ] Status page component is updated if customer-visible

## Failover action

Update the affected tenant:

```sql
UPDATE tenants
SET home_region = 'TARGET_REGION'
WHERE id = 'TENANT_ID'
  AND allow_cross_region_failover = true;
```

## Verification

After failover, confirm:

- [ ] New WebSocket sessions land in the target region
- [ ] Regional routing audit event is written
- [ ] Triton inference succeeds in the target region
- [ ] Redis active-connection counters update in the target region
- [ ] P95 time-to-first-partial returns to target range
- [ ] Disconnect rate stays below 1%

## Rollback

When the original region is healthy again:

```sql
UPDATE tenants
SET home_region = 'ORIGINAL_REGION'
WHERE id = 'TENANT_ID';
```

Then verify:

- [ ] New sessions return to the original region
- [ ] Active sessions in the failover region drain naturally
- [ ] Audit log records the routing change
- [ ] Status page is updated

## Completion criteria

Regional failover is complete when:

- Affected tenants are stable in a healthy region
- Customer-facing impact has stopped
- Audit logs show the routing change
- Incident notes include cause, scope, mitigation, and owner

This gives you a safe regional failover process for co-located GPU deployments while respecting tenant home-region and failover policy. The guide's co-located GPU regions step requires routing to consider tenant region, data residency, regional GPU capacity, regional health, and failover behavior.

Next step pointer: **Final step — Add regional failover tests**
