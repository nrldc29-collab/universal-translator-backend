# Self-Hosted Streaming STT Shipping Checklist

## Phase 0: Strategy

- [ ] ADR exists at `docs/adr/0001-architecture.md`
- [ ] Target customer profile is documented
- [ ] Latency targets are documented
- [ ] Compliance ceiling is documented
- [ ] Self-hosted path is selected
- [ ] Cloud-first and hybrid alternatives are documented

## Phase 1: Current Stack Quick Wins

- [ ] Dev API-key default removed
- [ ] App fails startup outside dev if `STT_API_KEY` is empty
- [ ] Temp-WAV round trip removed
- [ ] PCM-16LE converts directly to NumPy `float32`
- [ ] Decoder knobs exposed on WebSocket and REST endpoints
- [ ] REST endpoint rate limits are enabled
- [ ] Structured JSON logging is enabled
- [ ] Trace IDs exist for HTTP and WebSocket sessions
- [ ] API-key map is cached
- [ ] Release tag `v0.2.0` exists
- [ ] Phase 1 baseline metrics are captured

## Phase 2B: Self-Hosted Backend

- [ ] GPU Kubernetes cluster exists
- [ ] NVIDIA device plugin is installed
- [ ] DCGM exporter is installed
- [ ] At least 2 GPU nodes are reserved
- [ ] Triton StatefulSet is deployed
- [ ] Parakeet streaming ASR is loaded by Triton
- [ ] Sortformer streaming diarization is loaded by Triton
- [ ] Gateway can call Triton over gRPC
- [ ] Transcript events include word-level speaker labels
- [ ] Postgres stores tenants, API keys, usage counters, and audit logs
- [ ] Redis stores active connection counters and rate-limit counters
- [ ] Gateway connection draining works
- [ ] PodDisruptionBudgets are applied
- [ ] KEDA autoscaling is configured
- [ ] 12-hour, 200-stream soak test passes
- [ ] Whisper fallback remains enabled during rollout

## Phase 3: Enterprise Hardening

- [ ] TLS is required at the edge
- [ ] Enterprise mTLS plan is documented
- [ ] SSO / SAML / SCIM provider is selected
- [ ] API-key RBAC scopes are enforced
- [ ] Per-tenant audit log exists
- [ ] Multi-AZ deployment requirements are met
- [ ] Public status page exists
- [ ] SEV taxonomy is documented
- [ ] SOC 2 Type II evidence collection has started

## Phase 4: Differentiation

- [ ] NeMo fine-tuning plan exists
- [ ] Domain model plan exists
- [ ] Speaker enrollment plan exists
- [ ] Voice embeddings are treated as biometric data
- [ ] Co-located GPU region plan exists
- [ ] Tenant home-region setting exists

## Launch Gate

Production launch is blocked until all required Phase 0, Phase 1, Phase 2B, and Phase 3 checklist items are complete.

This turns the full self-hosted plan into a single launch gate, covering the guide's required strategy, quick wins, self-hosted backend, enterprise hardening, and differentiation work.
