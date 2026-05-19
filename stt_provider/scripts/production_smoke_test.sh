#!/usr/bin/env bash
set -euo pipefail

: "${PRODUCTION_STT_API_KEY:?PRODUCTION_STT_API_KEY is required}"

echo "==> Running production smoke test: us-east-1"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://us-east-1.example.com/stt/stream" \
  --api-key "$PRODUCTION_STT_API_KEY" \
  --expected-region "us-east-1"

echo "==> Running production smoke test: us-west-2"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://us-west-2.example.com/stt/stream" \
  --api-key "$PRODUCTION_STT_API_KEY" \
  --expected-region "us-west-2"

echo "==> Running production smoke test: eu-west-1"
python scripts/regional_smoke_test.py \
  --websocket-url "wss://eu-west-1.example.com/stt/stream" \
  --api-key "$PRODUCTION_STT_API_KEY" \
  --expected-region "eu-west-1"

echo "==> Production smoke tests passed"
