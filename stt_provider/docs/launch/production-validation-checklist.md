# Production Validation Checklist

## Goal

Confirm the deployed self-hosted STT platform is healthy before tenant rollout begins.

## Kubernetes validation

Run:

```bash
./scripts/validate_production.sh
```

Pass criteria:

- [ ] stt namespace exists
- [ ] stt-gateway deployment is rolled out
- [ ] triton-parakeet StatefulSet is rolled out
- [ ] stt-gateway service exists
- [ ] triton-parakeet service exists
- [ ] Gateway PodDisruptionBudget exists
- [ ] Triton PodDisruptionBudget exists
- [ ] KEDA gateway ScaledObject exists
- [ ] KEDA Triton ScaledObject exists
- [ ] Gateway pods are running
- [ ] Triton pods are running on GPU nodes
- [ ] stt-platform-secrets exists

## Health endpoint validation

Pass criteria:

- [ ] Gateway readiness endpoint returns success
- [ ] Gateway liveness endpoint returns success
- [ ] Triton readiness endpoint returns success

## Production rollout gate

Do not start tenant rollout until:

- [ ] Production validation script passes
- [ ] Regional smoke tests pass
- [ ] 12-hour, 200-stream soak test passes
- [ ] Status page is live
- [ ] On-call alerting is active
- [ ] Whisper fallback is enabled
- [ ] Rollback owner is assigned

This creates the checklist that pairs with `scripts/validate_production.sh`, covering Kubernetes rollout state, health endpoints, and production rollout gates before tenant rollout begins.
