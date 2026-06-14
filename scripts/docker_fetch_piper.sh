#!/usr/bin/env bash
# Download all bundled Piper voices for Docker builds.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python "$ROOT/scripts/setup_models.py" --piper-only
