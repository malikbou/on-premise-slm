#!/usr/bin/env bash
set -euo pipefail

# Full throughput: all models including cloud, high concurrency
# Runtime: ~5+ hours
# Usage: scripts/throughput-full.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "[throughput-full] Starting full throughput test (all models, may take 5+ hours)..."
echo "Press Ctrl+C within 10 seconds to cancel..."

# Run full throughput test using the container's built-in command + full test overrides
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm throughput-runner python src/throughput/runner.py \
  --mode rag --platform-preset vm --rag-base http://rag-api-bge:8000 \
  --requests 160 --repetitions 3 --concurrency "1,2,4,8,16" \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805"

echo "[throughput-full] Done. See results under results/runs/"
