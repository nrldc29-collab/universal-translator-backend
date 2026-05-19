# Regional Deployment Checklist

## Goal

Verify that each production GPU region is ready to serve tenant WebSocket traffic locally.

## Required regions

Initial production regions:

- [ ] `us-east-1` 
- [ ] `us-west-2` 
- [ ] `eu-west-1` 

## Per-region infrastructure

For each region, verify:

- [ ] Gateway deployment exists
- [ ] Gateway has at least 2 replicas
- [ ] Triton GPU pool exists
- [ ] Triton has at least 2 replicas
- [ ] NVIDIA device plugin is installed
- [ ] DCGM exporter is installed
- [ ] Redis is available
- [ ] Postgres connectivity is available
- [ ] Ingress is configured
- [ ] TLS certificate is active
- [ ] Metrics are collected
- [ ] Logs are forwarded
- [ ] Status page component exists

## Tenant routing

For each region, verify:

- [ ] `REGION` environment variable is set correctly
- [ ] Tenant `home_region` routing works
- [ ] Cross-region traffic is blocked by default
- [ ] Cross-region failover works only when explicitly enabled
- [ ] Regional routing decisions are written to the audit log

## GPU readiness

For each region, verify:

- [ ] GPU capacity is reserved
- [ ] GPU nodes are not spot/preemptible
- [ ] Triton pods are scheduled onto GPU nodes
- [ ] Parakeet model is loaded
- [ ] Sortformer model is loaded
- [ ] GPU metrics appear in the production dashboard

## Launch gate

A region is production-ready only when:

- All required infrastructure checks pass
- Tenant routing checks pass
- GPU readiness checks pass
- A regional smoke test succeeds
- Status page monitoring is live
- On-call alerting is active

This creates the operational checklist for co-located GPU regions, covering gateway, Triton, Redis, Postgres, ingress, observability, tenant routing, residency enforcement, and GPU readiness. The guide's co-located GPU regions step requires regional GPU pools near customers with geo-aware or Anycast routing while respecting tenant data-residency policy.
