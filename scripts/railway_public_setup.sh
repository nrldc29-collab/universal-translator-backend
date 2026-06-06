#!/usr/bin/env bash
# Generate (or discover) the Railway public URL and run production smoke.
# Requires RAILWAY_TOKEN from https://railway.com/account/tokens
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAILWAY_ENVIRONMENT="${RAILWAY_ENVIRONMENT:-production}"
RAILWAY_PORT="${RAILWAY_PORT:-8080}"
RUN_SMOKE="${RUN_SMOKE:-1}"

ensure_railway_cli() {
  export PATH="${HOME}/.railway/bin:${PATH}"
  if ! command -v railway >/dev/null 2>&1; then
    curl -fsSL https://railway.app/install.sh | sh
    export PATH="${HOME}/.railway/bin:${PATH}"
  fi
}

json_url() {
  python3 - <<'PY'
import json
import sys

raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    token = raw.split()[0]
    if token.startswith("http"):
        print(token.rstrip("/"))
        sys.exit(0)
    sys.exit(1)

def normalize(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"

if isinstance(data, dict):
    for key in ("url", "domain", "hostname", "publicUrl", "public_url"):
        if key in data and data[key]:
            url = normalize(str(data[key]))
            if url:
                print(url)
                sys.exit(0)
    for key in ("domains", "serviceDomains"):
        items = data.get(key)
        if isinstance(items, list):
            for item in items:
                if isinstance(item, str):
                    url = normalize(item)
                elif isinstance(item, dict):
                    url = normalize(str(item.get("domain") or item.get("url") or ""))
                else:
                    url = ""
                if url:
                    print(url)
                    sys.exit(0)
sys.exit(1)
PY
}

wait_for_health() {
  local base_url="$1"
  for _ in $(seq 1 60); do
    if curl -sf "${base_url%/}/health" >/dev/null 2>&1; then
      return 0
    fi
    sleep 5
  done
  return 1
}

if [[ -z "${RAILWAY_TOKEN:-}" ]]; then
  echo "RAILWAY_TOKEN is required." >&2
  echo "Create one at https://railway.com/account/tokens, then rerun:" >&2
  echo "  RAILWAY_TOKEN=... bash scripts/railway_public_setup.sh" >&2
  echo "Or use Railway dashboard → Service → Settings → Networking → Generate Domain." >&2
  exit 1
fi

ensure_railway_cli

domain_args=(--json -p "$RAILWAY_PORT" -e "$RAILWAY_ENVIRONMENT")
status_args=(--json -e "$RAILWAY_ENVIRONMENT")
if [[ -n "${RAILWAY_PROJECT_ID:-}" ]]; then
  domain_args+=(--project "$RAILWAY_PROJECT_ID")
  status_args+=(--project "$RAILWAY_PROJECT_ID")
fi
if [[ -n "${RAILWAY_SERVICE:-}" ]]; then
  domain_args+=(-s "$RAILWAY_SERVICE")
  status_args+=(-s "$RAILWAY_SERVICE")
fi

public_url=""
if [[ -n "${URL:-}" ]]; then
  public_url="${URL%/}"
else
  set +e
  domain_json="$(railway domain "${domain_args[@]}" 2>&1)"
  domain_code=$?
  set -e
  public_url="$(printf '%s' "$domain_json" | json_url || true)"
  if [[ -z "$public_url" && "$domain_code" -ne 0 ]]; then
    set +e
    status_json="$(railway service status "${status_args[@]}" 2>&1)"
    set -e
    public_url="$(printf '%s' "$status_json" | json_url || true)"
  fi
fi

if [[ -z "$public_url" ]]; then
  echo "Could not determine the Railway public URL." >&2
  [[ -n "${domain_json:-}" ]] && echo "$domain_json" >&2
  exit 1
fi

echo "Public URL: $public_url"
echo "Generate Railway variables with:"
echo "  ./Get-Railway-Variables.sh demo \"\" $public_url"

if ! wait_for_health "$public_url"; then
  echo "Timed out waiting for ${public_url}/health" >&2
  exit 1
fi

curl -sf "${public_url%/}/health" | python3 -m json.tool

if [[ "$RUN_SMOKE" != "1" ]]; then
  exit 0
fi

if [[ -z "${USERS:-}" ]]; then
  echo "Set USERS=user:pass (from Railway Variables or deploy logs) to run full EN↔HT smoke." >&2
  echo "  USERS=demo:YOUR-PASSWORD bash scripts/railway_public_setup.sh" >&2
  exit 0
fi

SMOKE_REMOTE=1 USERS="$USERS" python3 "$ROOT/scripts/smoke_local.py" "$public_url"
