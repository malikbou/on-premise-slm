#!/usr/bin/env bash
set -euo pipefail

# Run throughput runner via compose profile (inside Docker network).
# Usage: scripts/run-throughput.sh [optional runner args]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_DIR"
# Include both compose files so the VM-only service is available
# Default to the fast LLM path you validated; override with scripts/run-throughput-custom.sh for custom args
docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile throughput run --rm \
  throughput-runner \
  python src/throughput/runner.py \
  --mode llm --platform-preset vm \
  --litellm http://litellm:4000 \
  --cloud-model azure-gpt5 \
  --repetitions 1 \
  --requests 5 \
  --concurrency 1,2,4,8 \
  --max-tokens 64 \
  --temperature 0

echo "[run-throughput] Done. See results under results/runs/<STAMP>_vm/throughput/"
