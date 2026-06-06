#!/usr/bin/env bash
# Download Piper voices for Docker builds (EN required, ES optional for EN↔HT).
set -euo pipefail

TTS_DIR="${1:-models/tts}"
mkdir -p "$TTS_DIR"

fetch_required() {
  local name="$1"
  local url="$2"
  curl -L --fail --retry 5 --retry-delay 5 --retry-all-errors \
    -o "$TTS_DIR/$name" "$url"
}

fetch_optional() {
  local name="$1"
  local url="$2"
  if curl -L --fail --retry 3 --retry-delay 5 --retry-all-errors \
    -o "$TTS_DIR/$name" "$url"; then
    return 0
  fi
  echo "optional piper voice skipped: $name"
  rm -f "$TTS_DIR/$name"
  return 0
}

fetch_required "en_US-lessac-medium.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
fetch_required "en_US-lessac-medium.onnx.json" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

fetch_optional "es_MX-claude-high.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx"
fetch_optional "es_MX-claude-high.onnx.json" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_MX/claude/high/es_MX-claude-high.onnx.json"
