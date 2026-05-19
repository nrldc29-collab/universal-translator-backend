# Git Commit Plan

## Goal

Commit the self-hosted streaming STT implementation in reviewable chunks.

## Commit 1: Architecture and launch planning

```bash
git add docs/adr docs/launch docs/IMPLEMENTATION_INDEX.md docs/MASTER_EXECUTION_CHECKLIST.md CHANGELOG.md
git commit -m "Document self-hosted streaming STT launch plan"
```

## Commit 2: Core gateway hardening

```bash
git add stt_server/config.py stt_server/model.py stt_server/streaming.py stt_server/logging_utils.py stt_server/auth.py main.py .env.example README.md
git commit -m "Harden gateway configuration and streaming path"
```

## Commit 3: Self-hosted backend routing

```bash
git add stt_server/backends stt_server/backend_routing.py stt_server/backend_fallback.py stt_server/admin_backend.py stt_server/tenant_rollout.py
git commit -m "Add Triton backend routing with Whisper fallback"
```

## Commit 4: Durable and ephemeral state

```bash
git add infra/db stt_server/usage.py stt_server/usage_api.py stt_server/connection_counters.py stt_server/connection_counter_cleanup.py stt_server/stream_limits.py stt_server/rate_limits.py
git commit -m "Add Postgres and Redis state paths"
```

## Commit 5: Kubernetes deployment

```bash
git add infra/k8s docs/infra scripts/regional_smoke_test.py
git commit -m "Add Kubernetes deployment and regional validation assets"
```

## Commit 6: Enterprise controls

```bash
git add docs/enterprise docs/observability stt_server/rbac.py stt_server/audit.py
git commit -m "Add enterprise hardening and observability controls"
```

## Commit 7: Domain models and speaker enrollment

```bash
git add docs/ml stt_server/model_registry.py stt_server/models_api.py stt_server/admin_models.py stt_server/model_override_audit.py stt_server/speaker_profiles.py stt_server/speaker_profiles_api.py stt_server/encryption.py stt_server/speaker_identity.py stt_server/speaker_identity_audit.py
git commit -m "Add domain model and speaker enrollment foundations"
```

## Commit 8: Regional routing

```bash
git add stt_server/regional_routing.py stt_server/regional_routing_audit.py stt_server/admin_regions.py
git commit -m "Add tenant regional routing controls"
```

## Commit 9: Tests

```bash
git add tests
git commit -m "Add self-hosted STT rollout tests"
```

## Commit 10: Validation scripts

```bash
git add scripts/validate_local.sh scripts/validate_production.sh
git commit -m "Add local and production validation scripts"
```

## Final tag

```bash
git tag v0.2.0-self-hosted-stt
```

This gives you clean review chunks instead of one giant commit, covering architecture, gateway hardening, Triton routing, state, Kubernetes, enterprise controls, Phase 4 features, regional routing, tests, and validation. The guide's self-hosted track includes GPU Kubernetes, Triton, Parakeet, Sortformer, Postgres, Redis, connection draining, KEDA, and tenant rollout with Whisper fallback.
