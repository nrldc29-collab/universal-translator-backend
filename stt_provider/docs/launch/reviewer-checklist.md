# Reviewer Checklist: Self-Hosted Streaming STT

## Scope

- [ ] PR focuses on Phase 2B self-hosted path
- [ ] Phase 2A cloud-first Deepgram + pyannoteAI path is not introduced
- [ ] Whisper fallback remains available during rollout
- [ ] Tenant-by-tenant rollout is supported

## Architecture

- [ ] ADR selects self-hosted architecture
- [ ] FastAPI gateway remains the public API
- [ ] Triton is the internal self-hosted inference backend
- [ ] Parakeet streaming ASR is the selected ASR model path
- [ ] Sortformer streaming diarization is the selected diarization path

## Security

- [ ] No production default API key exists
- [ ] API-key RBAC scopes are enforced
- [ ] Admin endpoints require `admin:*` 
- [ ] Audit logs are written for sensitive changes
- [ ] Speaker embeddings are encrypted before storage
- [ ] Speaker embeddings are never returned by APIs
- [ ] Delete-my-voiceprint behavior exists

## Reliability

- [ ] Gateway has readiness and liveness endpoints
- [ ] Gateway supports connection draining
- [ ] PodDisruptionBudgets are defined
- [ ] Redis counters have cleanup safety
- [ ] Postgres stores durable usage and audit state
- [ ] KEDA autoscaling objects are defined
- [ ] Production validation script exists

## Regional routing

- [ ] Tenants have a `home_region` 
- [ ] Cross-region routing is blocked by default
- [ ] Cross-region failover is explicit per tenant
- [ ] Regional routing decisions are audited
- [ ] Regional smoke test script exists

## Launch readiness

- [ ] Local validation script exists
- [ ] Production validation script exists
- [ ] Regional smoke checklist exists
- [ ] Rollout runbook exists
- [ ] Rollback checklist exists
- [ ] Incident response runbook exists
- [ ] Production launch decision remains gated
