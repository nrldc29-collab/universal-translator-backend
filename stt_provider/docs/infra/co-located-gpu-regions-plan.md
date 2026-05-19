# Phase 4 Step 4: Co-Located GPU Regions

## Target

Deploy Triton GPU pools close to latency-sensitive customers so WebSocket audio traffic stays in-region and avoids unnecessary cross-region latency.

## Initial regions

Start with:

- us-east-1
- us-west-2
- eu-west-1

Add more regions only when a tenant contract requires it.

## Routing strategy

Use geo-aware DNS or Anycast ingress so each WebSocket connects to the closest healthy region.

Routing must consider:

- Customer assigned region
- Tenant data-residency policy
- Regional GPU capacity
- Regional health
- Failover policy

## Regional deployment requirements

Each production region must include:

- Gateway replicas
- Triton GPU pool
- Redis
- Regional ingress
- Metrics collection
- Log forwarding
- Status page component

## Tenant region settings

Add this column:

```sql
ALTER TABLE tenants
ADD COLUMN IF NOT EXISTS home_region TEXT NOT NULL DEFAULT 'us-east-1';
```

## Acceptance checks

- Tenant has a configured home region.
- WebSocket traffic routes to the tenant's home region.
- Triton inference runs in the same region as the gateway.
- Status page exposes regional health.
- Failover behavior is documented per tenant.
- Cross-region routing is blocked when tenant residency policy forbids it.
