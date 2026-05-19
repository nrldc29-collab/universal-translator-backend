#!/usr/bin/env bash
set -euo pipefail

# PostgreSQL Restore Script for STT Platform
# Restores PostgreSQL database from backup file

NAMESPACE="stt"
BACKUP_FILE="${1:-}"

if [ -z "$BACKUP_FILE" ]; then
  echo "Usage: $0 <backup-file>"
  echo "Example: $0 /backups/postgres/stt_backup_20240101_120000.sql.gz"
  exit 1
fi

if [ ! -f "$BACKUP_FILE" ]; then
  echo "ERROR: Backup file not found: ${BACKUP_FILE}"
  exit 1
fi

# Get PostgreSQL pod
POD_NAME=$(kubectl get pod -n ${NAMESPACE} -l app=postgres -o jsonpath='{.items[0].metadata.name}')

if [ -z "$POD_NAME" ]; then
  echo "ERROR: PostgreSQL pod not found"
  exit 1
fi

# Get PostgreSQL password
POSTGRES_PASSWORD=$(kubectl get secret stt-platform-secrets -n ${NAMESPACE} -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 -d)

# Decompress if needed
if [[ "$BACKUP_FILE" == *.gz ]]; then
  TEMP_FILE=$(mktemp)
  gunzip -c "$BACKUP_FILE" > "$TEMP_FILE"
  BACKUP_FILE="$TEMP_FILE"
fi

# Confirm restore
echo "WARNING: This will replace the current database with the backup"
echo "Backup file: ${BACKUP_FILE}"
read -p "Are you sure? (yes/no): " confirm

if [ "$confirm" != "yes" ]; then
  echo "Restore cancelled"
  exit 0
fi

# Restore database
echo "Restoring PostgreSQL database from: ${BACKUP_FILE}"
kubectl exec -i -n ${NAMESPACE} ${POD_NAME} -- psql -U stt -d stt < "${BACKUP_FILE}"

# Clean up temp file
if [ -n "$TEMP_FILE" ] && [ -f "$TEMP_FILE" ]; then
  rm "$TEMP_FILE"
fi

echo "Database restore completed successfully"
