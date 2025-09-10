#!/usr/bin/env bash
set -euo pipefail

# Run RAGAS benchmarking inside Docker (VM profile enabled in compose).
# Usage: scripts/run-benchmarks.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$PROJECT_DIR"
# Fast sanity run: VM DNS, generate only, small sample
docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile benchmark run --rm \
  benchmarker \
  python -u src/benchmarking/benchmark.py \
  --preset vm --mode generate --num-questions 5

echo "[run-benchmarks] Done. See results under results/benchmarking/"
