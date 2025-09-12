#!/usr/bin/env bash
set -euo pipefail

# One-shot: write env, start core, preload, build indexes, and show curls.
# Usage: scripts/vm-quickstart.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"

"$PROJECT_DIR/scripts/vm-write-env.sh" "$PROJECT_DIR"
"$PROJECT_DIR/scripts/vm-core-up.sh" "$PROJECT_DIR"
"$PROJECT_DIR/scripts/vm-preload.sh" "http://localhost:11434"
"$PROJECT_DIR/scripts/vm-build-indexes.sh" "$PROJECT_DIR"

echo "[vm-quickstart] Curl checks:"
curl -s http://localhost:11434/api/version | jq . || true
curl -s http://localhost:4000/v1/models | jq . || true
curl -s http://localhost:8001/info | jq . || true

echo "[vm-quickstart] Running smoke checks..."
"$PROJECT_DIR/scripts/vm-smoke.sh" "$PROJECT_DIR" || true

echo "[vm-quickstart] Done."
