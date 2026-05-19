#!/usr/bin/env bash
set -euo pipefail

FAILED=0

check_pass() {
  echo "PASS: $1"
}

check_fail() {
  echo "FAIL: $1"
  FAILED=1
}

check_file() {
  if [ -f "$1" ]; then
    check_pass "Found $1"
  else
    check_fail "Missing $1"
  fi
}

check_command() {
  if command -v "$1" >/dev/null 2>&1; then
    check_pass "Command available: $1"
  else
    check_fail "Command missing: $1"
  fi
}

check_file ".env"
check_file ".env.example"
check_file "docker-compose.yml"
check_file "server/Dockerfile"
check_file "server/requirements.txt"
check_file "server/stt_server/main.py"
check_file "client/index.html"
check_file "deploy/nginx/stt-provider.conf"

check_command "docker"
check_command "python3"

if command -v docker >/dev/null 2>&1; then
  if docker compose version >/dev/null 2>&1; then
    check_pass "Docker Compose plugin available"
  else
    check_fail "Docker Compose plugin missing"
  fi
fi

if [ -f ".env" ]; then
  if grep -q "^STT_API_KEY=" .env; then
    check_pass ".env contains STT_API_KEY"
  else
    check_fail ".env missing STT_API_KEY"
  fi

  if grep -q "^ALLOWED_ORIGINS=" .env; then
    check_pass ".env contains ALLOWED_ORIGINS"
  else
    check_fail ".env missing ALLOWED_ORIGINS"
  fi
fi

if [ -f "deploy/nginx/stt-provider.conf" ]; then
  if grep -q "your-domain.com" deploy/nginx/stt-provider.conf; then
    check_fail "Nginx config still contains your-domain.com"
  else
    check_pass "Nginx domain placeholder replaced"
  fi
fi

if [ "$FAILED" -ne 0 ]; then
  echo
  echo "Preflight failed. Fix the FAIL items above before deploying."
  exit 1
fi

echo
echo "Preflight passed."
