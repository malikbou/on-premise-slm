#!/usr/bin/env bash
set -euo pipefail

# Full benchmark: all models including cloud, many questions
# Runtime: ~5+ hours
# Usage: scripts/benchmark-full.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "[benchmark-full] Starting full benchmark (all models, may take 5+ hours)..."
echo "Press Ctrl+C within 3 seconds to cancel..."
sleep 3

# Ensure dependencies are up
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d \
  litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Run full benchmark using the container's built-in command (no extra flags = full mode)
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm benchmarker python -u src/benchmarking/benchmark.py --preset vm --num-questions 99

echo "[benchmark-full] Done. See results under results/benchmarking/"
