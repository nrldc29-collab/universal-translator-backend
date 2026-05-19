#!/usr/bin/env bash
set -euo pipefail

# Redis Backup Script for STT Platform
# Creates automated backups of Redis data

NAMESPACE="stt"
BACKUP_DIR="/backups/redis"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/redis_backup_${TIMESTAMP}.rdb"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Get Redis pod
POD_NAME=$(kubectl get pod -n ${NAMESPACE} -l app=redis -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
  echo "ERROR: Redis pod not found"
  exit 1
fi

# Trigger Redis save
echo "Triggering Redis save"
kubectl exec -n ${NAMESPACE} ${POD_NAME} -- redis-cli BGSAVE

# Wait for save to complete
echo "Waiting for Redis save to complete"
sleep 5

# Copy RDB file from pod
echo "Copying Redis RDB file"
kubectl cp ${NAMESPACE}/${POD_NAME}:/data/dump.rdb "${BACKUP_FILE}"

# Compress backup
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Upload to S3 (if AWS CLI is configured)
if command -v aws &> /dev/null; then
  S3_BUCKET="${S3_BUCKET:-s3://your-backup-bucket/stt/redis}"
  echo "Uploading backup to S3: ${S3_BUCKET}"
  aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/redis_backup_${TIMESTAMP}.rdb.gz"
fi

# Clean up old backups
echo "Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "redis_backup_*.rdb.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed successfully: ${BACKUP_FILE}"
