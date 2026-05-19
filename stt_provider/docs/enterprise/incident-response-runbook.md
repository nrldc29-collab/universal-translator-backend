# Streaming STT Incident Response Runbook

## Goal

Respond consistently to production incidents affecting the self-hosted streaming STT platform.

## Severity levels

### SEV-1

Complete production outage, widespread transcription failure, or major security incident.

### SEV-2

Major degradation affecting many customers, regional failure with fallback available, high latency, or elevated disconnects.

### SEV-3

Partial degradation, isolated tenant impact, delayed usage reporting, or increased non-critical errors.

### SEV-4

Minor bug, cosmetic issue, documentation issue, or planned maintenance notice.

## First 15 minutes

1. Assign incident commander.
2. Assign communications owner.
3. Assign technical lead.
4. Open incident channel.
5. Identify affected services, regions, and tenants.
6. Check gateway, Triton, Redis, Postgres, GPU, and ingress metrics.
7. Decide whether to roll back affected tenants to Whisper.
8. Update the status page if there is customer-visible impact.

## Key metrics to check

- Gateway error rate
- WebSocket disconnect rate
- P50 and P95 time-to-first-partial
- P50 and P95 time-between-partials
- Triton inference queue duration
- GPU utilization
- GPU memory utilization
- Redis availability
- Postgres write latency
- Audit-log write success
- Usage-counter write success

## Rollback decision

Rollback affected tenants to Whisper when:

- P95 time-to-first-partial exceeds 700 ms for 30 minutes
- Disconnect rate exceeds 1%
- Triton queue duration remains elevated
- Triton pods are crash-looping
- GPU saturation cannot recover
- Usage or audit writes are failing

## Customer communication

Every customer-facing update must include:

- What is affected
- Who is affected
- Current mitigation
- Next update time
- Whether transcript accuracy, latency, or availability is impacted

## Post-incident follow-up

For every SEV-1 and SEV-2, create a postmortem with:

- Summary
- Timeline
- Root cause
- Customer impact
- Detection gap
- Resolution
- Preventive actions
- Owners
- Due dates

This completes the incident workflow required by the enterprise hardening phase, including SEV taxonomy, on-call response, rollback criteria, public status updates, and postmortems
