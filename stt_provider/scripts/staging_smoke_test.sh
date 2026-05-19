#!/usr/bin/env bash
set -euo pipefail

: "${STAGING_STT_API_KEY:?STAGING_STT_API_KEY is required}"

echo "==> Running staging smoke test: us-east-1"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://staging-us-east-1.example.com/stt/stream" \
  --api-key "$STAGING_STT_API_KEY" \
  --expected-region "us-east-1"

echo "==> Running staging smoke test: us-west-2"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://staging-us-west-2.example.com/stt/stream" \
  --api-key "$STAGING_STT_API_KEY" \
  --expected-region "us-west-2"

echo "==> Running staging smoke test: eu-west-1"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://staging-eu-west-1.example.com/stt/stream" \
  --api-key "$STAGING_STT_API_KEY" \
  --expected-region "eu-west-1"

echo "==> Staging smoke tests passed"
