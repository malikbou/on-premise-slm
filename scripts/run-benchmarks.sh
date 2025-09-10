#!/usr/bin/env bash
set -euo pipefail

# Run RAGAS benchmarking inside Docker (VM profile enabled in compose).
# Usage: scripts/run-benchmarks.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="${1:-$(cd "$SCRIPT_DIR/.." && pwd)}"

cd "$PROJECT_DIR"
docker compose --profile benchmark up benchmarker

echo "[run-benchmarks] Done. See results under results/benchmarking/"
