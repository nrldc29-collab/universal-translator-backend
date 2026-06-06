#!/usr/bin/env bash
# Quick backend verification — delegates to the full EN↔HT smoke suite.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec bash "$ROOT/scripts/test_translator.sh" "${1:-http://127.0.0.1:8000}"
