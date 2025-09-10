#!/usr/bin/env bash
set -euo pipefail

# Run RAGAS benchmarking inside Docker (VM profile enabled in compose).
# Usage: scripts/run-benchmarks.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$PROJECT_DIR"
# Ensure RAG API dependencies are up on the VM network
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d \
  litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Streamed run (recommended): VM DNS, generate-only quick sanity
docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile benchmark up benchmarker

echo "[run-benchmarks] Done. See results under results/benchmarking/"
