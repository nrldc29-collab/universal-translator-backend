# Self-Hosted Streaming STT Master Execution Checklist

## Goal

Use this checklist to execute the self-hosted streaming STT implementation in order.

## Execution order

### 1. Commit architecture decision

- [ ] Create `docs/adr/0001-architecture.md` 
- [ ] Confirm self-hosted path is selected
- [ ] Confirm Phase 2A cloud-first path is out of scope
- [ ] Confirm Whisper fallback remains available during rollout

### 2. Apply Phase 1 app changes

- [ ] Remove default `dev-secret-key` 
- [ ] Add startup failure when `STT_API_KEY` is missing outside dev
- [ ] Remove temp-WAV round trip
- [ ] Add decoder knobs
- [ ] Add REST rate limits
- [ ] Add structured logging and trace IDs
- [ ] Cache API-key map
- [ ] Tag release as `v0.2.0` 
- [ ] Capture Phase 1 latency and WER baseline

### 3. Apply database migrations

Run:

```bash
psql "$DATABASE_URL" -f infra/db/001_externalize_state.sql
psql "$DATABASE_URL" -f infra/db/002_tenant_backend_rollout.sql
psql "$DATABASE_URL" -f infra/db/003_speaker_profiles.sql
```

### 4. Deploy Kubernetes infrastructure

Run:

```bash
kubectl create namespace stt --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -f infra/k8s/secrets-template.yaml
kubectl apply -f infra/k8s/gateway-deployment.yaml
kubectl apply -f infra/k8s/triton-parakeet-statefulset.yaml
kubectl apply -f infra/k8s/triton-parakeet-service.yaml
kubectl apply -f infra/k8s/gateway-draining-and-pdb.yaml
kubectl apply -f infra/k8s/keda-scaledobjects.yaml
```

### 5. Run tests

Run:

```bash
pytest
```

### 6. Validate regional readiness

Run one smoke test per region:

```bash
python scripts/regional_smoke_test.py \
  --websocket-url "wss://us-east-1.example.com/stt/stream" \
  --api-key "$STT_API_KEY" \
  --expected-region "us-east-1"

python scripts/regional_smoke_test.py \
  --websocket-url "wss://us-west-2.example.com/stt/stream" \
  --api-key "$STT_API_KEY" \
  --expected-region "us-west-2"

python scripts/regional_smoke_test.py \
  --websocket-url "wss://eu-west-1.example.com/stt/stream" \
  --api-key "$STT_API_KEY" \
  --expected-region "eu-west-1"
```

### 7. Run production-like load test

- [ ] Run 12-hour soak test
- [ ] Use 200 concurrent streams
- [ ] Validate rolling gateway restarts
- [ ] Validate rolling Triton restarts
- [ ] Confirm P95 time-to-first-partial stays under 700 ms
- [ ] Confirm disconnect rate stays below 1%
- [ ] Confirm Redis counters return to zero
- [ ] Confirm audit logs and usage counters write successfully

### 8. Complete enterprise launch gates

- [ ] TLS is active
- [ ] mTLS plan is ready for enterprise/private connectivity
- [ ] SSO / SAML / SCIM provider is selected
- [ ] API-key RBAC is enforced
- [ ] Per-tenant audit log is live
- [ ] Multi-AZ deployment is verified
- [ ] Public status page is live
- [ ] On-call alerting is active
- [ ] SOC 2 evidence collection has started

### 9. Roll out by tenant tier

- [ ] Internal tenants
- [ ] 10% low-risk tenants
- [ ] 25% tenants
- [ ] 50% tenants
- [ ] 100% eligible tenants
- [ ] Keep Whisper fallback enabled for at least 2 stable weeks

### 10. Final production decision

- [ ] Complete `docs/launch/production-launch-decision.md`
- [ ] Assign launch owner
- [ ] Assign rollback owner
- [ ] Get engineering approval
- [ ] Get security approval
- [ ] Get infrastructure approval
- [ ] Get support/on-call approval
