#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
ENV_FILE="${2:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

ADMIN_API_KEY="$(grep '^ADMIN_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d '=' -f 2-)"

if [ "$ADMIN_API_KEY" = "" ]; then
  echo "ADMIN_API_KEY is empty or missing in $ENV_FILE"
  exit 1
fi

curl -X POST "$BASE_URL/v1/usage/reset" \
  -H "Authorization: Bearer $ADMIN_API_KEY"
