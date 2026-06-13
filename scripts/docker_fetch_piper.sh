#!/usr/bin/env bash
# Download Piper voices for Docker builds (EN required, ES optional for EN↔HT).
set -euo pipefail

TTS_DIR="${1:-models/tts}"
mkdir -p "$TTS_DIR"

CURL_AUTH=()
if [[ -n "${HF_TOKEN:-}" ]]; then
  CURL_AUTH=(-H "Authorization: Bearer ${HF_TOKEN}")
fi

fetch_required() {
  local name="$1"
  local url="$2"
  if [[ -f "$TTS_DIR/$name" ]] && [[ "$(wc -c < "$TTS_DIR/$name")" -gt 1000 ]]; then
    echo "skip  $name (already present)"
    return 0
  fi
  local attempt
  for attempt in $(seq 1 8); do
    if curl -L --fail --retry 3 --retry-delay 10 --retry-all-errors \
      "${CURL_AUTH[@]}" \
      -o "$TTS_DIR/$name" "$url"; then
      return 0
    fi
    echo "required piper voice retry ${attempt}/8: $name" >&2
    sleep $((attempt * 10))
  done
  echo "failed to download required piper voice: $name" >&2
  return 1
}

fetch_optional() {
  local name="$1"
  local url="$2"
  if curl -L --fail --retry 3 --retry-delay 10 --retry-all-errors \
    "${CURL_AUTH[@]}" \
    -o "$TTS_DIR/$name" "$url"; then
    return 0
  fi
  echo "optional piper voice skipped: $name"
  rm -f "$TTS_DIR/$name"
  return 0
}

fetch_required "en_US-lessac-medium.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx"
sleep 2
fetch_required "en_US-lessac-medium.onnx.json" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/en/en_US/lessac/medium/en_US-lessac-medium.onnx.json"

fetch_optional "es_ES-carlfm-x_low.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx"
fetch_optional "es_ES-carlfm-x_low.onnx.json" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/es/es_ES/carlfm/x_low/es_ES-carlfm-x_low.onnx.json"
fetch_optional "nl_NL-ronnie-medium.onnx" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/ronnie/medium/nl_NL-ronnie-medium.onnx"
fetch_optional "nl_NL-ronnie-medium.onnx.json" \
  "https://huggingface.co/rhasspy/piper-voices/resolve/main/nl/nl_NL/ronnie/medium/nl_NL-ronnie-medium.onnx.json"
