#!/usr/bin/env bash
set -euo pipefail

# Preload embeddings and SLMs into the Ollama server.
# Usage (host):   ./scripts/preload-ollama-models.sh
# Usage (docker): docker exec -it ollama bash -lc "/app/scripts/preload-ollama-models.sh"

OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://localhost:11434}

echo "Preloading models into Ollama at: ${OLLAMA_BASE_URL}"

pull() {
  local name="$1"
  echo "Pulling: ${name}"
  curl -sS -X POST "${OLLAMA_BASE_URL}/api/pull" \
    -H 'Content-Type: application/json' \
    -d "{\"name\": \"${name}\"}" || true
}

# Embeddings (must match project configuration)
pull "bge-m3"
pull "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
pull "yxchia/multilingual-e5-large-instruct"

# SLMs (fixed list from src/throughput/runner.py)
pull "hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf"
pull "hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M"
pull "hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M"
pull "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M"
pull "hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M"
pull "hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M"

echo "Preload complete. Current models:"
curl -sS "${OLLAMA_BASE_URL}/api/ps" | jq . || true
