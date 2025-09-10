#!/usr/bin/env bash
set -euo pipefail

# Build FAISS indexes for all embeddings on the VM.
# Usage: scripts/vm-build-indexes.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"
cd "$PROJECT_DIR"

docker compose up index-builder

echo "[vm-build-indexes] Index build complete."
