#!/usr/bin/env bash
set -euo pipefail

# Disaster Recovery Script for STT Platform
# Automates disaster recovery process from backups

NAMESPACE="stt"
BACKUP_DIR="/backups"

echo "=========================================="
echo "STT Platform Disaster Recovery Procedure"
echo "=========================================="
echo

# Step 1: Verify backup availability
echo "Step 1: Verifying backup availability"
if [ ! -d "${BACK_DIR}" ]; then
  echo "ERROR: Backup directory not found: ${BACK_DIR}"
  exit 1
fi

echo "Available PostgreSQL backups:"
ls -lh ${BACKUP_DIR}/postgres/*.sql.gz 2>/dev/null || echo "  No PostgreSQL backups found"

echo "Available Redis backups:"
ls -lh ${BACK_DIR_DIR}/redis/*.rdb.gz 2>/dev/null || echo "  No Redis backups found"

echo "Available Secrets backups:"
ls -lh ${BACKUP_DIR}/secrets/*.yaml* 2>/dev/null || echo "  No Secrets backups found"

echo
read -p "Continue with disaster recovery? (yes/no): " confirm
if [ "$confirm" != "yes" ]; then
  echo "Disaster recovery cancelled"
  exit 0
fi

# Step 2: Restore secrets
echo
echo "Step 2: Restoring secrets"
LATEST_SECRETS=$(ls -t ${BACKUP_DIR}/secrets/*.yaml* 2>/dev/null | head -1)
if [ -n "$LATEST_SECRETS" ]; then
  echo "Restoring from: ${LATEST_SECRETS}"
  
  # Decrypt if encrypted
  if [[ "$LATEST_SECRETS" == *.enc ]]; then
    TEMP_FILE=$(mktemp)
    gpg --decrypt --output "$TEMP_FILE" "$LATEST_SECRETS"
    kubectl apply -f "$TEMP_FILE"
    rm "$TEMP_FILE"
  else
    kubectl apply -f "$LATEST_SECRETS"
  fi
  echo "Secrets restored successfully"
else
  echo "WARNING: No secrets backup found, skipping"
fi

# Step 3: Restore PostgreSQL
echo
echo "Step 3: Restoring PostgreSQL database"
LATEST_POSTGRES=$(ls -t ${BACKUP_DIR}/postgres/*.sql.gz 2>/dev/null | head -1)
if [ -n "$LATEST_POSTGRES" ]; then
  echo "Restoring from: ${LATEST_POSTGRES}"
  bash scripts/restore-postgres.sh "${LATEST_POSTGRES}"
else
  echo "WARNING: No PostgreSQL backup found, skipping"
fi

# Step 4: Restore Redis
echo
echo "Step 4: Restoring Redis data"
LATEST_REDIS=$(ls -t ${BACKUP_DIR}/redis/*.rdb.gz 2>/dev/null | head -1)
if [ -n "$LATEST_REDIS" ]; then
  echo "Restoring from: ${LATEST_REDIS}"
  
  POD_NAME=$(kubectl get pod -n ${NAMESPACE} -l app=redis -o jsonpath='{.items[0].metadata.name}')
  TEMP_FILE=$(mktemp)
  gunzip -c "$LATEST_REDIS" > "$TEMP_FILE"
  
  # Stop Redis
  kubectl exec -n ${NAMESPACE} ${POD_NAME} -- redis-cli SHUTDOWN NOSAVE
  
  # Copy RDB file
  kubectl cp "$TEMP_FILE" ${NAMESPACE}/${POD_NAME}:/data/dump.rdb
  
  # Start Redis
  kubectl delete pod ${POD_NAME} -n ${NAMESPACE}
  
  rm "$TEMP_FILE"
  echo "Redis restored successfully"
else
  echo "WARNING: No Redis backup found, skipping"
fi

# Step 5: Verify deployment
echo
echo "Step 5: Verifying deployment"
sleep 30

echo "Checking pod status..."
kubectl get pods -n ${NAMESPACE}

echo
echo "Waiting for all pods to be ready..."
kubectl wait --for=condition=ready --timeout=300s pod -l app=postgres -n ${NAMESPACE} || true
kubectl wait --for=condition=ready --timeout=300s pod -l app=redis -n ${NAMESPACE} || true
kubectl wait --for=condition=ready --timeout=300s pod -l app=stt-gateway -n ${NAMESPACE} || true
kubectl wait --for=condition=ready --timeout=300s pod -l app=triton-parakeet -n ${NAMESPACE} || true

# Step 6: Run health checks
echo
echo "Step 6: Running health checks"

# Gateway health
echo "Testing gateway health..."
kubectl run health-check --rm -i --restart=Never --image=curlimages/curl:latest -- curl -f http://stt-gateway/health || echo "WARNING: Gateway health check failed"

# Database health
echo "Testing database health..."
kubectl exec -n ${NAMESPACE} $(kubectl get pod -n ${NAMESPACE} -l app=postgres -o jsonpath='{.items[0].metadata.name}') -- pg_isready || echo "WARNING: Database health check failed"

# Redis health
echo "Testing Redis health..."
kubectl exec -n ${NAMESPACE} $(kubectl get pod -n ${NAMESPACE} -l app=redis -o jsonpath='{.items[0].metadata.name}') -- redis-cli PING || echo "WARNING: Redis health check failed"

echo
echo "=========================================="
echo "Disaster recovery completed"
echo "=========================================="
echo
echo "Next steps:"
echo "1. Review pod status: kubectl get pods -n ${NAMESPACE}"
echo "2. Review logs: kubectl logs -f deployment/stt-gateway -n ${NAMESPACE}"
echo "3. Run smoke tests: bash scripts/validate_production.sh"
echo "4. Review Grafana dashboards for any issues"
