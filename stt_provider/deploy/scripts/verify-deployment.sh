#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://localhost:8000}"
ENV_FILE="${2:-.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

STT_API_KEY="$(grep '^STT_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d '=' -f 2-)"
ADMIN_API_KEY="$(grep '^ADMIN_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d '=' -f 2-)"

if [ "$STT_API_KEY" = "" ]; then
  echo "Missing STT_API_KEY in $ENV_FILE"
  exit 1
fi

if [ "$ADMIN_API_KEY" = "" ]; then
  echo "Missing ADMIN_API_KEY in $ENV_FILE"
  exit 1
fi

pass() {
  echo "PASS: $1"
}

fail() {
  echo "FAIL: $1"
  exit 1
}

check_public_json() {
  local path="$1"
  local required="$2"

  body="$(curl -fsS "$BASE_URL$path")" || fail "$path request failed"

  echo "$body" | grep -q "$required" || fail "$path missing expected text: $required"

  pass "$path"
}

check_client_auth_json() {
  local path="$1"
  local required="$2"

  body="$(curl -fsS "$BASE_URL$path" \
    -H "Authorization: Bearer $STT_API_KEY")" || fail "$path client-auth request failed"

  echo "$body" | grep -q "$required" || fail "$path missing expected text: $required"

  pass "$path"
}

check_admin_auth_json() {
  local path="$1"
  local required="$2"

  body="$(curl -fsS "$BASE_URL$path" \
    -H "Authorization: Bearer $ADMIN_API_KEY")" || fail "$path admin-auth request failed"

  echo "$body" | grep -q "$required" || fail "$path missing expected text: $required"

  pass "$path"
}

check_public_json "/health" '"status":"ok"'
check_public_json "/v1/models" '"object":"list"'

check_client_auth_json "/v1/usage" '"sessions_started"'
check_client_auth_json "/metrics" "stt_active_connections"

check_admin_auth_json "/v1/admin/health" '"auth":"admin_api_key"'
check_admin_auth_json "/v1/admin/audit" ""

python3 "$(dirname "$0")/verify-websocket.py" \
  --base-url "$BASE_URL" \
  --api-key "$STT_API_KEY" || fail "WebSocket verification failed"

echo
echo "Deployment verification passed for: $BASE_URL"
