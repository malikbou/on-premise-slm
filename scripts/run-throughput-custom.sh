#!/usr/bin/env bash
set -euo pipefail

# Run throughput with custom runner args.
# Usage: scripts/run-throughput-custom.sh -- [args for runner]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile throughput run --rm throughput-runner "$@"
