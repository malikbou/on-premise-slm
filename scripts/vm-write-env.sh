#!/usr/bin/env bash
set -euo pipefail

# Write a .env file for the VM from current environment variables.
# Usage: scripts/vm-write-env.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"

# Import persisted environment (if on-start exported to /etc/environment)
if [ -f /etc/environment ]; then
  set -a
  # shellcheck disable=SC1091
  . /etc/environment || true
  set +a
fi

# Helper to resolve final value: prefer non-empty ENV; else preserve existing .env; else default
resolve_val() {
  var_name="$1"; default_val="$2"
  env_val="${!var_name-}"
  prev_val=""
  if [ -f "$PROJECT_DIR/.env" ]; then
    prev_val=$(grep -E "^${var_name}=" "$PROJECT_DIR/.env" | tail -n1 | cut -d= -f2- || true)
  fi
  if [ -n "$env_val" ]; then
    printf '%s' "$env_val"
  elif [ -n "$prev_val" ]; then
    printf '%s' "$prev_val"
  else
    printf '%s' "$default_val"
  fi
}

PLATFORM_VAL="$(resolve_val PLATFORM vast_ai_gpu)"
OLLAMA_BASE_URL_VAL="$(resolve_val OLLAMA_BASE_URL http://ollama:11434)"
LITELLM_API_BASE_VAL="$(resolve_val LITELLM_API_BASE http://litellm:4000)"
EMBEDDING_MODELS_VAL="$(resolve_val EMBEDDING_MODELS bge-m3,hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0,yxchia/multilingual-e5-large-instruct)"
NUM_QUESTIONS_TO_TEST_VAL="$(resolve_val NUM_QUESTIONS_TO_TEST 100)"
RESULTS_DIR_VAL="$(resolve_val RESULTS_DIR results)"

OPENAI_API_KEY_VAL="$(resolve_val OPENAI_API_KEY "")"
GEMINI_API_KEY_VAL="$(resolve_val GEMINI_API_KEY "")"
ANTHROPIC_API_KEY_VAL="$(resolve_val ANTHROPIC_API_KEY "")"
AZURE_OPENAI_API_BASE_VAL="$(resolve_val AZURE_OPENAI_API_BASE "")"
AZURE_OPENAI_API_VERSION_VAL="$(resolve_val AZURE_OPENAI_API_VERSION 2024-12-01-preview)"
AZURE_OPENAI_API_KEY_VAL="$(resolve_val AZURE_OPENAI_API_KEY "")"
AZURE_OPENAI_API_BASE_4_1_VAL="$(resolve_val AZURE_OPENAI_API_BASE_4_1 "")"
AZURE_OPENAI_API_VERSION_4_1_VAL="$(resolve_val AZURE_OPENAI_API_VERSION_4_1 "")"
AZURE_OPENAI_API_KEY_4_1_VAL="$(resolve_val AZURE_OPENAI_API_KEY_4_1 "")"

{
  echo "PLATFORM=$PLATFORM_VAL"
  echo "OLLAMA_BASE_URL=$OLLAMA_BASE_URL_VAL"
  echo "LITELLM_API_BASE=$LITELLM_API_BASE_VAL"
  echo "EMBEDDING_MODELS=$EMBEDDING_MODELS_VAL"
  echo "NUM_QUESTIONS_TO_TEST=$NUM_QUESTIONS_TO_TEST_VAL"
  echo "RESULTS_DIR=$RESULTS_DIR_VAL"
  echo "OPENAI_API_KEY=$OPENAI_API_KEY_VAL"
  echo "GEMINI_API_KEY=$GEMINI_API_KEY_VAL"
  echo "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY_VAL"
  echo "AZURE_OPENAI_API_BASE=$AZURE_OPENAI_API_BASE_VAL"
  echo "AZURE_OPENAI_API_VERSION=$AZURE_OPENAI_API_VERSION_VAL"
  echo "AZURE_OPENAI_API_KEY=$AZURE_OPENAI_API_KEY_VAL"
  echo "AZURE_OPENAI_API_BASE_4_1=$AZURE_OPENAI_API_BASE_4_1_VAL"
  echo "AZURE_OPENAI_API_VERSION_4_1=$AZURE_OPENAI_API_VERSION_4_1_VAL"
  echo "AZURE_OPENAI_API_KEY_4_1=$AZURE_OPENAI_API_KEY_4_1_VAL"
} > "$PROJECT_DIR/.env"

# Optionally include EMBEDDING_API_MAP if provided
if [ -n "${EMBEDDING_API_MAP:-}" ]; then
  echo "EMBEDDING_API_MAP=$EMBEDDING_API_MAP" >> "$PROJECT_DIR/.env"
fi

echo "[vm-write-env] Wrote $PROJECT_DIR/.env"
