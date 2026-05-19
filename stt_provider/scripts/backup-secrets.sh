#!/usr/bin/env bash
set -euo pipefail

# Secrets Backup Script for STT Platform
# Backs up Kubernetes secrets to encrypted file

NAMESPACE="stt"
BACKUP_DIR="/backups/secrets"
RETENTION_DAYS=90
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/secrets_backup_${TIMESTAMP}.yaml.enc"

# Create backup directory
mkdir -p "${BACKUP_DIR}"

# Get all secrets in namespace
echo "Backing up secrets from namespace: ${NAMESPACE}"
kubectl get secrets -n ${NAMESPACE} -o yaml > "${BACKUP_DIR}/secrets_backup_${TIMESTAMP}.yaml"

# Encrypt backup (if GPG is available)
if command -v gpg &> /dev/null; then
  RECIPIENT="${GPG_RECIPIENT:-your-email@example.com}"
  echo "Encrypting secrets backup"
  gpg --encrypt --recipient "${RECIPIENT}" --output "${BACKUP_FILE}" "${BACKUP_DIR}/secrets_backup_${TIMESTAMP}.yaml"
  rm "${BACKUP_DIR}/secrets_backup_${TIMESTAMP}.yaml"
  echo "Encrypted backup created: ${BACKUP_FILE}"
else
  echo "WARNING: GPG not found, secrets backup is not encrypted"
  BACKUP_FILE="${BACKUP_DIR}/secrets_backup_${TIMESTAMP}.yaml"
fi

# Upload to S3 (if AWS CLI is configured)
if command -v aws &> /dev/null; then
  S3_BUCKET="${S3_BUCKET:-s3://your-backup-bucket/stt/secrets}"
  echo "Uploading backup to S3: ${S3_BUCKET}"
  aws s3 cp "${BACKUP_FILE}" "${S3_BUCKET}/secrets_backup_${TIMESTAMP}.yaml.enc"
fi

# Clean up old backups
echo "Cleaning up backups older than ${RETENTION_DAYS} days"
find "${BACKUP_DIR}" -name "secrets_backup_*.yaml*" -mtime +${RETENTION_DAYS} -delete

echo "Secrets backup completed successfully"
