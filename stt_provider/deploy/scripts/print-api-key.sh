#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:-/opt/true-streaming-stt-provider/.env}"

if [ ! -f "$ENV_FILE" ]; then
  echo "Missing env file: $ENV_FILE"
  exit 1
fi

if [ "$(id -u)" -ne 0 ]; then
  echo "Run this on the VPS with sudo:"
  echo "sudo bash deploy/scripts/print-api-key.sh"
  exit 1
fi

API_KEY="$(grep '^STT_API_KEY=' "$ENV_FILE" | head -n 1 | cut -d '=' -f 2-)"

if [ "$API_KEY" = "" ]; then
  echo "STT_API_KEY is empty or missing in $ENV_FILE"
  exit 1
fi

echo "STT_API_KEY:"
echo "$API_KEY"
