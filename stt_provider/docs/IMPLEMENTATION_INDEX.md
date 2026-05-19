# Self-Hosted Streaming STT Implementation Index

## Phase 0: Strategic decision

- `docs/adr/0001-architecture.md` 

## Phase 1: Current stack quick wins

- `stt_server/config.py` 
- `main.py` 
- `.env.example` 
- `README.md` 
- `stt_server/model.py` 
- `stt_server/streaming.py` 
- `stt_server/logging_utils.py` 
- `stt_server/auth.py` 
- `scripts/measure_phase1.py` 

## Phase 2B: Self-hosted backend

- `infra/k8s/gpu-nodepool-notes.md` 
- `infra/k8s/triton-parakeet-statefulset.yaml` 
- `infra/k8s/triton-parakeet-service.yaml` 
- `infra/k8s/triton-sortformer-notes.md` 
- `infra/db/001_externalize_state.sql` 
- `infra/db/redis-state-contract.md` 
- `infra/k8s/gateway-draining-and-pdb.yaml` 
- `infra/k8s/keda-scaledobjects.yaml` 
- `scripts/phase2b_load_test_plan.md` 
- `stt_server/backends/triton.py` 
- `stt_server/backend_routing.py` 
- `stt_server/backend_fallback.py` 
- `stt_server/admin_backend.py` 

## Phase 3: Enterprise hardening

- `infra/k8s/edge-mtls-notes.md` 
- `docs/enterprise/sso-saml-scim-plan.md` 
- `stt_server/rbac.py` 
- `stt_server/audit.py` 
- `infra/k8s/multi-az-deployment-notes.md` 
- `docs/enterprise/status-page-plan.md` 
- `docs/enterprise/soc2-evidence-plan.md` 
- `docs/enterprise/incident-response-runbook.md` 

## Phase 4: Differentiation

- `docs/ml/nemo-fine-tuning-plan.md` 
- `docs/ml/domain-models-plan.md` 
- `docs/ml/speaker-enrollment-plan.md` 
- `docs/ml/speaker-enrollment.md` 
- `docs/ml/speaker-enrollment-launch-checklist.md` 
- `docs/infra/co-located-gpu-regions-plan.md` 
- `stt_server/model_registry.py` 
- `stt_server/models_api.py` 
- `stt_server/admin_models.py` 
- `stt_server/speaker_profiles.py` 
- `stt_server/speaker_profiles_api.py` 
- `stt_server/encryption.py` 
- `stt_server/speaker_identity.py` 
- `stt_server/speaker_identity_audit.py` 
- `stt_server/regional_routing.py` 
- `stt_server/regional_routing_audit.py` 
- `stt_server/admin_regions.py` 

## Launch and operations

- `docs/launch/open-questions-before-shipping.md` 
- `docs/launch/shipping-checklist.md` 
- `docs/launch/production-readiness-scorecard.md` 
- `docs/launch/rollout-runbook.md` 
- `docs/launch/rollback-checklist.md` 
- `docs/launch/production-launch-decision.md` 
- `docs/observability/monitoring-dashboard-spec.md` 
- `docs/observability/alert-rules-spec.md` 
- `docs/config/environment-variables.md` 
- `infra/k8s/secrets-template.yaml` 
- `infra/k8s/gateway-deployment.yaml` 
- `docs/infra/regional-deployment-checklist.md` 
- `scripts/regional_smoke_test.py` 
- `docs/infra/regional-smoke-test-checklist.md` 
- `docs/infra/regional-failover-runbook.md` 

## Tests

- `tests/test_backend_routing.py` 
- `tests/test_admin_backend.py` 
- `tests/test_backend_fallback_audit.py` 
- `tests/test_streaming_event_schema.py` 
- `tests/test_usage_api.py` 
- `tests/test_stream_limits.py` 
- `tests/test_connection_counter_cleanup.py` 
- `tests/test_rate_limits.py` 
- `tests/test_tenant_rollout.py` 
- `tests/test_triton_model_selection.py` 
- `tests/test_model_registry.py` 
- `tests/test_models_api.py` 
- `tests/test_admin_models.py` 
- `tests/test_admin_models_audit.py` 
- `tests/test_model_override.py` 
- `tests/test_model_override_audit.py` 
- `tests/test_speaker_profiles_api.py` 
- `tests/test_encryption.py` 
- `tests/test_delete_my_voiceprint.py` 
- `tests/test_speaker_identity.py` 
- `tests/test_speaker_identity_threshold.py` 
- `tests/test_speaker_identity_audit.py` 
- `tests/test_regional_routing.py` 
- `tests/test_regional_routing_audit.py` 
- `tests/test_admin_regions.py` 
- `tests/test_admin_regions_audit.py` 
- `tests/test_regional_failover.py` 
- `tests/test_regional_failover_audit.py` 

## Final command sequence

```bash
pytest
psql "$DATABASE_URL" -f infra/db/001_externalize_state.sql
psql "$DATABASE_URL" -f infra/db/002_tenant_backend_rollout.sql
psql "$DATABASE_URL" -f infra/db/003_speaker_profiles.sql
kubectl apply -f infra/k8s/secrets-template.yaml
kubectl apply -f infra/k8s/gateway-deployment.yaml
kubectl apply -f infra/k8s/triton-parakeet-statefulset.yaml
kubectl apply -f infra/k8s/triton-parakeet-service.yaml
kubectl apply -f infra/k8s/gateway-draining-and-pdb.yaml
kubectl apply -f infra/k8s/keda-scaledobjects.yaml
```

This index gives you one place to track every file created or modified across the self-hosted STT implementation, from Phase 0 strategy through Phase 2B infrastructure, Phase 3 enterprise hardening, Phase 4 differentiation, and production launch operations.
