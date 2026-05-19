# Staging Deployment Checklist: Self-Hosted Streaming STT

## Goal

Deploy the self-hosted STT stack to staging before any production rollout.

## Prerequisites

- [ ] Merge checklist is complete
- [ ] Release tag exists
- [ ] Staging database exists
- [ ] Staging Kubernetes cluster exists
- [ ] Staging GPU node pool exists
- [ ] Staging Redis exists
- [ ] Staging secrets are configured
- [ ] Whisper fallback is enabled

## Apply staging database migrations

```bash
psql "$STAGING_DATABASE_URL" -f infra/db/001_externalize_state.sql
psql "$STAGING_DATABASE_URL" -f infra/db/002_tenant_backend_rollout.sql
psql "$STAGING_DATABASE_URL" -f infra/db/003_speaker_profiles.sql
```

## Deploy staging Kubernetes resources

```bash
kubectl config use-context staging
kubectl create namespace stt --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f infra/k8s/secrets-template.yaml
kubectl apply -f infra/k8s/gateway-deployment.yaml
kubectl apply -f infra/k8s/triton-parakeet-statefulset.yaml
kubectl apply -f infra/k8s/triton-parakeet-service.yaml
kubectl apply -f infra/k8s/gateway-draining-and-pdb.yaml
kubectl apply -f infra/k8s/keda-scaledobjects.yaml
```

## Validate staging

```bash
./scripts/validate_production.sh
```

## Staging pass criteria

- [ ] Gateway deployment is healthy
- [ ] Triton StatefulSet is healthy
- [ ] Gateway readiness check passes
- [ ] Gateway liveness check passes
- [ ] Triton readiness check passes
- [ ] Redis counters work
- [ ] Postgres usage writes work
- [ ] Audit-log writes work
- [ ] Whisper fallback works
- [ ] Regional smoke test passes in staging

## Staging launch rule

Do not schedule production rollout until staging passes validation and the 12-hour, 200-stream soak test is scheduled.
