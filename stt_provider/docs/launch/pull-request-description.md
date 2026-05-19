# Pull Request: Self-Hosted Streaming STT Platform

## Summary

This PR implements the self-hosted streaming STT path using:

- FastAPI gateway
- NVIDIA Triton
- Parakeet streaming ASR
- Sortformer streaming diarization
- Postgres durable state
- Redis ephemeral counters
- Tenant backend routing
- Whisper fallback during rollout
- Enterprise audit, RBAC, observability, and launch-readiness controls

This PR intentionally focuses on Phase 2B self-hosted deployment and does not implement the Phase 2A cloud-first Deepgram + pyannoteAI path.

## Why

The selected architecture prioritizes:

- Data-residency control
- Lower vendor lock-in
- GPU-based self-hosted inference
- Future NeMo fine-tuning
- Tenant-selectable domain models
- Enterprise reliability and auditability

## Major changes

### Gateway and streaming

- Removes unsafe development API-key default
- Adds production startup guard for missing `STT_API_KEY` 
- Removes temp-WAV round trip
- Converts PCM-16LE directly to NumPy `float32` 
- Adds decoder knobs
- Adds structured JSON logging with trace IDs
- Adds health endpoints

### Self-hosted backend

- Adds Triton gRPC client wrapper
- Adds tenant backend routing
- Adds Whisper fallback
- Adds backend admin controls
- Adds backend fallback audit events

### State

- Adds Postgres migrations for tenants, API keys, usage counters, audit logs, rollout fields, and speaker profiles
- Adds Redis active-connection counters
- Adds Redis rate-limit counters
- Adds usage counter write path and usage API

### Enterprise controls

- Adds API-key RBAC scopes
- Adds per-tenant audit logging
- Adds mTLS plan
- Adds SSO / SAML / SCIM plan
- Adds status page plan
- Adds SOC 2 evidence plan
- Adds incident response, rollback, rollout, monitoring, and alerting runbooks

### Differentiation

- Adds domain model registry
- Adds `GET /v1/models` 
- Adds tenant default model admin endpoint
- Adds request-level model override support
- Adds speaker enrollment foundations
- Adds encrypted speaker embedding storage
- Adds delete-my-voiceprint endpoint
- Adds speaker identity confidence threshold support
- Adds regional routing and failover controls

## Validation

Run:

```bash
./scripts/validate_local.sh
```

Then run production validation after Kubernetes deployment:

```bash
./scripts/validate_production.sh
```

Run regional smoke tests:

```bash
python scripts/regional_smoke_test.py \
  --websocket-url "wss://us-east-1.example.com/stt/stream" \
  --api-key "$STT_API_KEY" \
  --expected-region "us-east-1"
```

## Launch gates

Do not launch until:

- All tests pass
- Production validation passes
- Regional smoke tests pass
- 12-hour, 200-stream soak test passes
- Whisper fallback is enabled
- Status page is live
- On-call alerting is active
- SOC 2 evidence collection has started
- Production launch decision record is approved

## Rollback

Rollback affected tenants to Whisper:

```text
tenant.backend = whisper
```

## Risk

Main risks:

- GPU capacity shortage
- Triton model readiness issues
- WebSocket disconnects during rolling restarts
- Redis counter drift
- Audit or usage write failures
- Regional routing misconfiguration

## Reviewer checklist

- [ ] Architecture matches self-hosted Phase 2B path
- [ ] Phase 2A cloud-first code is not introduced
- [ ] Triton routing preserves Whisper fallback
- [ ] Tenant rollout controls are safe
- [ ] Audit events cover sensitive changes
- [ ] Speaker embeddings are encrypted and never returned
- [ ] Regional routing respects tenant home region
- [ ] Production launch remains gated
