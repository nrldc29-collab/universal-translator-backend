# Phase 3 Step 6: Public Status Page

## Target

Provide customers with a public status page that reports platform availability, incidents, maintenance windows, and regional service health.

## Approved providers

Use one of:

- Better Stack
- Atlassian Statuspage
- Statuspage.io

Default choice:

- Better Stack

## Status page components

Create one component per region and service:

- API Gateway — US
- API Gateway — EU
- Streaming STT — US
- Streaming STT — EU
- Triton ASR Backend — US
- Triton ASR Backend — EU
- Tenant Admin API
- Usage and Billing API
- Webhooks
- Dashboard

## Incident severity taxonomy

### SEV-1

Complete production outage or widespread transcription failure.

### SEV-2

Major degradation affecting many customers, high latency, or regional failure with fallback available.

### SEV-3

Partial degradation, elevated errors, delayed usage reporting, or isolated tenant impact.

### SEV-4

Minor bug, cosmetic issue, or maintenance notice.

## Required incident fields

Every incident must include:

- Severity
- Affected components
- Affected regions
- Start time
- Current status
- Customer impact
- Mitigation status
- Next update time
- Final resolution summary

## Postmortem requirements

Publish a postmortem for every SEV-1 and SEV-2.

Postmortems must include:

- Summary
- Timeline
- Root cause
- Customer impact
- Detection gap
- Resolution
- Preventive actions
- Owners
- Due dates

## Alert routing

Production alerts must route to the on-call rotation through:

- PagerDuty, or
- Opsgenie

## Acceptance checks

- Public status page exists.
- Each production region and major service has a component.
- Monitoring alerts can update status page incidents.
- On-call receives SEV-1 and SEV-2 alerts.
- SEV taxonomy is documented.
- Postmortem template is ready.

This implements Phase 3, Step 6: create a public status page, define regional service components, document SEV taxonomy, connect alerts to on-call, and prepare the postmortem process.
