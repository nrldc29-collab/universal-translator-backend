#!/usr/bin/env bash
set -euo pipefail

# PostgreSQL Backup Script for STT Platform
# Creates automated backups of PostgreSQL database with retention policy

NAMESPACE="stt"
BACKUP_DIR="/backups/postgres"
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/stt_backup_${TIMESTAMP}.sql"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Get PostgreSQL pod
POD_NAME=$(kubectl get pod -n ${NAMESPACE} -l app=postgres -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
  echo "ERROR: PostgreSQL pod not found"
  exit 1
fi

# Get PostgreSQL password
POSTGRES_PASSWORD=$(kubectl get secret stt-platform-secrets -n ${NAMESPACE} -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# Create backup
echo "Creating PostgreSQL backup: ${BACKUP_FILE}"
kubectl exec -n ${NAMESPACE} ${POD_NAME -- pg_dump -U stt -d stt > "${BACKUP_FILE}"

# Compress backup
gzip "${BACKUP_FILE}"
BACKUP_FILE="${BACKUP_FILE}.gz"

# Upload to S3 (if AWS CLI is configured)
if command -v aws &> /dev/null; then
  S3_BUCKET="${S3_BUCKET:-s3://your-backup-bucket/stt/postgres}"
  echo "Uploading backup to S3: ${S3_BUCKET}"
  aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/stt_backup_${TIMESTAMP}.sql.gz"
fi

# Clean up old backups
echo "Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "stt_backup_*.sql.gz" -mtime +${RETENTION_DAYS} -delete

# Clean up old S3 backups (if AWS CLI is configured)
if command -v aws &> /dev/null; then
  aws s3 ls "${S3_BUCKET}" | while read -r line; do
    FILE_DATE=$(echo "$line" | awk '{print $1}')
    FILE_NAME=$(echo "$line" | awk '{print $4}')
    if [[ "$FILE_NAME" == stt_backup_*.sql.gz ]]; then
      FILE_SECONDS=$(date -d "$FILE_DATE" +%s)
      CURRENT_SECONDS=$(date +%s)
      AGE_DAYS=$(( (CURRENT_SECONDS - FILE_SECONDS) / 86400 ))
      if [ $AGE_DAYS -gt $RETENTION_DAYS ]; then
        echo "Deleting old S3 backup: ${S3_BUCKET}/${FILE_NAME}"
        aws s3 rm "${S3_BUCKET}/${FILE_NAME}"
      fi
    fi
  done
fi

echo "Backup completed successfully: ${BACKUP_FILE}"
