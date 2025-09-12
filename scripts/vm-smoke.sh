#!/usr/bin/env bash
set -euo pipefail

# Smoke-check core services and a minimal throughput run.
# Usage: scripts/vm-smoke.sh [/path/to/project]

PROJECT_DIR="${1:-$PWD}"
cd "$PROJECT_DIR"

echo "[vm-smoke] Checking Ollama..."
curl -fsS http://localhost:11434/api/version >/dev/null

echo "[vm-smoke] Checking LiteLLM..."
curl -fsS http://localhost:4000/v1/models >/dev/null || curl -fsS http://localhost:4000/health >/dev/null

echo "[vm-smoke] Checking RAG APIs /info..."
curl -fsS http://localhost:8001/info >/dev/null
curl -fsS http://localhost:8002/info >/dev/null || true
curl -fsS http://localhost:8003/info >/dev/null

echo "[vm-smoke] RAG /query quick call (bge + local Phi-3.5)..."
curl -fsS http://localhost:8001/query -H 'Content-Type: application/json' \
  -d '{"question":"Smoke ping: what section discusses key dates?","model_name":"ollama/hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M"}' >/dev/null || true

echo "[vm-smoke] Throughput one-shot (local SLM, 1 req, c=1)..."
docker compose -f docker-compose.yml -f docker-compose.vm.yml --profile throughput run --rm \
  throughput-runner \
  python src/throughput/runner.py \
  --mode llm --platform-preset vm \
  --skip-cloud \
  --models "hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M" \
  --requests 1 --repetitions 1 --concurrency 1 \
  --max-tokens 16 --temperature 0 --prompt "Smoke test ping" --quiet || true

echo "[vm-smoke] OK"
