#!/usr/bin/env bash
set -euo pipefail

# Simple benchmark: local models only, 5 questions, 1 embedding
# Runtime: ~2-5 minutes
# Usage: scripts/benchmark-simple.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"

echo "[benchmark-simple] Starting simple benchmark (local models only)..."

# Ensure dependencies are up
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d \
  litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Run simple benchmark using the container's built-in command + our flags
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm benchmarker python -u src/benchmarking/benchmark.py --preset vm --mode generate --num-questions 5 \
  --models  "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M,ollama/hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M,ollama/hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M"

echo "[benchmark-simple] Done. See results under results/benchmarking/"
