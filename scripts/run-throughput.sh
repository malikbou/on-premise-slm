#!/usr/bin/env bash
set -euo pipefail

# Run throughput runner via compose profile (inside Docker network).
# Usage: scripts/run-throughput.sh [optional runner args]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$PROJECT_DIR"
# Include both compose files so the VM-only service is available
if [ "$#" -gt 0 ]; then
  docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile throughput run --rm throughput-runner "$@"
else
  docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile throughput run --rm throughput-runner
fi

echo "[run-throughput] Done. See results under results/runs/<STAMP>_vm/throughput/"
