#!/usr/bin/env bash
set -euo pipefail

# Bring up core services on the VM.
# Usage: scripts/vm-core-up.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"
cd "$PROJECT_DIR"

docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d ollama litellm rag-api-bge rag-api-qwen3 rag-api-e5

echo "[vm-core-up] Core services started."
