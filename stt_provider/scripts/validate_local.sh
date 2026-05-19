#!/usr/bin/env bash
set -euo pipefail

echo "==> Checking Python formatting/import safety"
python -m compileall stt_server tests

echo "==> Running test suite"
pytest --ignore=server/tests

echo "==> Checking required implementation files exist"
required_files=(
  "docs/adr/0001-architecture.md"
  "docs/MASTER_EXECUTION_CHECKLIST.md"
  "docs/IMPLEMENTATION_INDEX.md"
  "infra/db/001_externalize_state.sql"
  "infra/db/002_tenant_backend_rollout.sql"
  "infra/db/003_speaker_profiles.sql"
  "infra/k8s/gateway-deployment.yaml"
  "infra/k8s/triton-parakeet-statefulset.yaml"
  "infra/k8s/triton-parakeet-service.yaml"
  "infra/k8s/gateway-draining-and-pdb.yaml"
  "infra/k8s/keda-scaledobjects.yaml"
  "stt_server/backends/triton.py"
  "stt_server/backend_routing.py"
  "stt_server/backend_fallback.py"
  "stt_server/audit.py"
  "stt_server/rbac.py"
  "stt_server/usage.py"
  "stt_server/connection_counters.py"
  "stt_server/rate_limits.py"
  "stt_server/model_registry.py"
  "stt_server/speaker_profiles.py"
  "stt_server/regional_routing.py"
)

for file in "${required_files[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required file: $file"
    exit 1
  fi
done

echo "==> Local validation passed"
