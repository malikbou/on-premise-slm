#!/usr/bin/env bash
set -euo pipefail

# Simple throughput: local models only, fewer requests/concurrency
# Runtime: ~2-3 minutes
# Usage: scripts/throughput-simple.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "[throughput-simple] Starting simple throughput test (local models only)..."

# Run simple throughput test using the container's built-in command + simple overrides
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm throughput-runner python src/throughput/runner.py \
  --mode rag --platform-preset vm --rag-base http://rag-api-bge:8000 \
  --requests 1 --repetitions 1 --concurrency "1,2" --skip-cloud

echo "[throughput-simple] Done. See results under results/runs/"
