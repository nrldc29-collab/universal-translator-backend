#!/usr/bin/env bash
# Generate (or discover) the Railway public URL and run production smoke.
# Requires RAILWAY_TOKEN from https://railway.com/account/tokens
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RAILWAY_ENVIRONMENT="${RAILWAY_ENVIRONMENT:-production}"
RAILWAY_PORT="${RAILWAY_PORT:-8080}"
RAILWAY_PROJECT_ID="${RAILWAY_PROJECT_ID:-0d581567-e2fa-4405-a041-1b9aaeeafceb}"
RAILWAY_ENVIRONMENT_ID="${RAILWAY_ENVIRONMENT_ID:-51f83c91-38dc-477b-a703-b013a360c90f}"
RUN_SMOKE="${RUN_SMOKE:-1}"

ensure_railway_cli() {
  export PATH="${HOME}/.railway/bin:${PATH}"
  if ! command -v railway >/dev/null 2>&1; then
    curl -fsSL https://railway.app/install.sh | bash
    export PATH="${HOME}/.railway/bin:${PATH}"
  fi
}

json_url() {
  python3 - <<'PY'
import json
import sys

def normalize(value: str) -> str:
    value = value.strip().rstrip("/")
    if not value:
        return ""
    if value.startswith("http://") or value.startswith("https://"):
        return value
    return f"https://{value}"

raw = sys.stdin.read().strip()
if not raw:
    sys.exit(1)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("http://") or line.startswith("https://"):
            print(line.rstrip("/"))
            sys.exit(0)
        if ".up.railway.app" in line:
            print(normalize(line.split()[0]))
            sys.exit(0)
    sys.exit(1)

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

resolve_public_url_graphql() {
  python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

token = os.environ.get("RAILWAY_TOKEN", "").strip()
project_id = os.environ.get("RAILWAY_PROJECT_ID", "").strip()
environment_id = os.environ.get("RAILWAY_ENVIRONMENT_ID", "").strip()
service_hint = os.environ.get("RAILWAY_SERVICE", "").strip()
port = int(os.environ.get("RAILWAY_PORT", "8080") or "8080")

if not token or not project_id or not environment_id:
    sys.exit(1)


def gql(query: str, variables: dict | None = None) -> dict:
    body = json.dumps({"query": query, "variables": variables or {}}).encode("utf-8")
    req = urllib.request.Request(
        "https://backboard.railway.com/graphql/v2",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {detail}") from exc
    if payload.get("errors"):
        raise RuntimeError(json.dumps(payload["errors"]))
    return payload["data"]


def normalize_domain(domain: str) -> str:
    domain = domain.strip().rstrip("/")
    if domain.startswith("http://") or domain.startswith("https://"):
        return domain
    return f"https://{domain}"


def pick_service(services: list[dict]) -> dict | None:
    if service_hint:
        for service in services:
            if service["id"] == service_hint or service["name"] == service_hint:
                return service
    if len(services) == 1:
        return services[0]
    repo_hint = os.path.basename(os.getcwd()).lower()
    for service in services:
        if repo_hint and repo_hint in service["name"].lower():
            return service
    for service in services:
        lowered = service["name"].lower()
        if any(token in lowered for token in ("translator", "backend", "universal")):
            return service
    return services[0] if services else None


data = gql(
    """
    query projectServices($id: String!) {
      project(id: $id) {
        services {
          edges {
            node {
              id
              name
            }
          }
        }
      }
    }
    """,
    {"id": project_id},
)
services = [edge["node"] for edge in data["project"]["services"]["edges"]]
service = pick_service(services)
if not service:
    raise RuntimeError("No Railway services found in project")

print(f"Using Railway service: {service['name']}", file=sys.stderr)

domain_data = gql(
    """
    query serviceDomains($projectId: String!, $environmentId: String!, $serviceId: String!) {
      domains(
        projectId: $projectId
        environmentId: $environmentId
        serviceId: $serviceId
      ) {
        serviceDomains {
          domain
        }
      }
    }
    """,
    {
        "projectId": project_id,
        "environmentId": environment_id,
        "serviceId": service["id"],
    },
)
existing = domain_data["domains"]["serviceDomains"]
if existing:
    print(normalize_domain(existing[0]["domain"]))
    sys.exit(0)

create_input = {
    "environmentId": environment_id,
    "serviceId": service["id"],
    "targetPort": port,
}
created = gql(
    """
    mutation createDomain($input: ServiceDomainCreateInput!) {
      serviceDomainCreate(input: $input) {
        domain
      }
    }
    """,
    {"input": create_input},
)
domain = created.get("serviceDomainCreate", {}).get("domain")
if not domain:
    domain_data = gql(
        """
        query serviceDomains($projectId: String!, $environmentId: String!, $serviceId: String!) {
          domains(
            projectId: $projectId
            environmentId: $environmentId
            serviceId: $serviceId
          ) {
            serviceDomains {
              domain
            }
          }
        }
        """,
        {
            "projectId": project_id,
            "environmentId": environment_id,
            "serviceId": service["id"],
        },
    )
    existing = domain_data["domains"]["serviceDomains"]
    if not existing:
        raise RuntimeError("serviceDomainCreate did not return a domain")
    domain = existing[0]["domain"]

print(normalize_domain(domain))
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

public_url=""
if [[ -n "${URL:-}" ]]; then
  public_url="${URL%/}"
else
  set +e
  public_url="$(resolve_public_url_graphql 2>/dev/null)"
  graphql_code=$?
  set -e
  if [[ "$graphql_code" -ne 0 || -z "$public_url" ]]; then
    ensure_railway_cli

    resolve_railway_service() {
      if [[ -n "${RAILWAY_SERVICE:-}" ]]; then
        return
      fi
      local list_json
      list_json="$(railway service list --json -e "$RAILWAY_ENVIRONMENT" -p "$RAILWAY_PROJECT_ID" 2>/dev/null || true)"
      if [[ -z "$list_json" ]]; then
        return
      fi
      RAILWAY_SERVICE="$(printf '%s' "$list_json" | python3 - <<'PY'
import json
import os
import sys

raw = sys.stdin.read().strip()
if not raw:
    sys.exit(0)
try:
    data = json.loads(raw)
except json.JSONDecodeError:
    sys.exit(0)

services = data if isinstance(data, list) else data.get("services") or data.get("items") or []
if not isinstance(services, list) or not services:
    sys.exit(0)

def service_name(item):
    if isinstance(item, str):
        return item
    if isinstance(item, dict):
        return str(item.get("name") or item.get("serviceName") or item.get("id") or "")
    return ""

names = [service_name(item) for item in services]
names = [name for name in names if name]
if len(names) == 1:
    print(names[0])
    sys.exit(0)

repo_hint = os.path.basename(os.getcwd()).lower()
for name in names:
    if repo_hint and repo_hint in name.lower():
        print(name)
        sys.exit(0)
for name in names:
    lowered = name.lower()
    if "translator" in lowered or "backend" in lowered or "universal" in lowered:
        print(name)
        sys.exit(0)
PY
)"
    }

    resolve_railway_service

    domain_args=(--json -p "$RAILWAY_PORT" -e "$RAILWAY_ENVIRONMENT" --project "$RAILWAY_PROJECT_ID")
    status_args=(--json -e "$RAILWAY_ENVIRONMENT" -p "$RAILWAY_PROJECT_ID")
    if [[ -n "${RAILWAY_SERVICE:-}" ]]; then
      domain_args+=(-s "$RAILWAY_SERVICE")
      status_args+=(-s "$RAILWAY_SERVICE")
      echo "Using Railway service: $RAILWAY_SERVICE"
    fi

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
