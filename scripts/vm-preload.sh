#!/usr/bin/env bash
set -euo pipefail

# Preload embeddings and SLMs into the VM's Ollama.
# Usage: scripts/vm-preload.sh [OLLAMA_BASE_URL]

BASE="${1:-${OLLAMA_BASE_URL:-http://localhost:11434}}"

echo "[vm-preload] Preloading into: $BASE"

pull(){
  local name="$1"
  echo "Pulling: ${name}"
  curl -sS -X POST "$BASE/api/pull" -H 'Content-Type: application/json' -d "{\"name\": \"${name}\"}" || true
}

# Embeddings
pull "bge-m3"
pull "hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0"
pull "yxchia/multilingual-e5-large-instruct"

# SLMs (fixed list used by throughput runner)
pull "hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf"
pull "hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M"
pull "hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M"
pull "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M"
pull "hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M"
pull "hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M"

echo "[vm-preload] Done."
