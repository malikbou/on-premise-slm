#!/usr/bin/env bash
set -euo pipefail

# Run throughput runner via compose profile (inside Docker network).
# Usage: scripts/run-throughput.sh [extra args]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$PROJECT_DIR"
docker compose --profile throughput run --rm throughput-runner

echo "[run-throughput] Done. See results under results/runs/<STAMP>_vm/throughput/"
