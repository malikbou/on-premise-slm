#!/usr/bin/env bash
set -euo pipefail

# Write a .env file for the VM from current environment variables.
# Usage: scripts/vm-write-env.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"

cat > "$PROJECT_DIR/.env" <<EONV
PLATFORM=${PLATFORM:-vast_ai_gpu}
OLLAMA_BASE_URL=${OLLAMA_BASE_URL:-http://ollama:11434}
LITELLM_API_BASE=${LITELLM_API_BASE:-http://litellm:4000}
EMBEDDING_MODELS=${EMBEDDING_MODELS:-bge-m3,hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0,yxchia/multilingual-e5-large-instruct}
EMBEDDING_API_MAP=${EMBEDDING_API_MAP:-bge-m3=http://rag-api-bge:8000,hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0=http://rag-api-qwen3:8000,yxchia/multilingual-e5-large-instruct=http://rag-api-e5:8000}
NUM_QUESTIONS_TO_TEST=${NUM_QUESTIONS_TO_TEST:-100}
RESULTS_DIR=${RESULTS_DIR:-results}
OPENAI_API_KEY=${OPENAI_API_KEY:-}
AZURE_OPENAI_API_BASE=${AZURE_OPENAI_API_BASE:-}
AZURE_OPENAI_API_VERSION=${AZURE_OPENAI_API_VERSION:-2024-12-01-preview}
AZURE_OPENAI_API_KEY=${AZURE_OPENAI_API_KEY:-}
EONV

echo "[vm-write-env] Wrote $PROJECT_DIR/.env"
