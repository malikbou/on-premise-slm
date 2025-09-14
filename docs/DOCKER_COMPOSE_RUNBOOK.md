### Docker Compose Runbook (Local Mac vs VM)

This runbook gives copy-pasteable commands to run the RAG stack locally on Mac (host Ollama) and on a VM (containerized Ollama). It also clarifies .env precedence, verification, and quick troubleshooting.

---

### One-time config check (recommended)

- Ensure `rag-api-qwen3` points to the correct FAISS path (matches the index builder slug for `hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0`):

```yaml
# docker-compose.yml
services:
  rag-api-qwen3:
    environment:
      - INDEX_DIR=/app/.rag_cache/hf_co_qwen_qwen3_embedding_0_6b_gguf_q8_0/faiss_index
      - EMBEDDING_MODEL=hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
      - OLLAMA_BASE_URL=http://host.docker.internal:11434
```

Tip: If `.env` has `OLLAMA_BASE_URL`, prefer removing it and pass per-command with `-e OLLAMA_BASE_URL=...` for `index-builder`.

---

### Local (Mac) — Host Ollama (Metal)

1) Reset any mixed stacks

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml down
docker compose -f docker-compose.yml down
```

2) Start host Ollama and warm models

```bash
ollama serve
# In another terminal:
ollama pull bge-m3
ollama pull hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
ollama pull yxchia/multilingual-e5-large-instruct
ollama pull hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M
ollama pull hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M
ollama pull hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf
```

3) Build FAISS indexes (containers call host Ollama)

```bash
docker compose up -d litellm

# IMPORTANT: point index-builder to host Ollama from inside container
docker compose run --rm \
  -e OLLAMA_BASE_URL=http://host.docker.internal:11434 \
  index-builder --preset local
```

4) Start RAG APIs (all use host Ollama)

```bash
docker compose up -d rag-api-bge rag-api-qwen3 rag-api-e5
```

5) Verify

```bash
curl -s localhost:8001/info | jq .
curl -s localhost:8002/info | jq .
curl -s localhost:8003/info | jq .
# Expect: "ollama_base_url": "http://host.docker.internal:11434" for all
```

6) Run the benchmark from host

```bash
python src/benchmarking/benchmark.py --preset local --num-questions 10 --ollama-base "http://localhost:11434"
```

7) If all else fails, rebuild again from scratch
```bash
# 0) Stop repo stacks (ignore errors)
docker compose -f docker-compose.yml -f docker-compose.vm.yml down -v --remove-orphans || true
docker compose -f docker-compose.yml down -v --remove-orphans || true

# 1) Quit Docker Desktop
osascript -e 'quit app "Docker"' || true
pkill -f com.docker || true
sleep 2
open -a Docker
# Wait until Docker is running
while ! docker system info >/dev/null 2>&1; do sleep 2; done

# 2) Global cleanup (containers, images, volumes, networks, build cache)
docker ps -aq | xargs -n1 docker rm -f 2>/dev/null || true
docker images -q | xargs -n1 docker rmi -f 2>/dev/null || true
docker volume ls -q | xargs -n1 docker volume rm 2>/dev/null || true
docker network ls -q | grep -Ev '^(bridge|host|none)$' | xargs -n1 docker network rm 2>/dev/null || true
docker builder prune -af
docker system prune -af --volumes

# 3) Optional: reset buildx builders and contexts (leave default)
docker buildx ls | awk 'NR>1 {print $1}' | grep -v '^default$' | xargs -n1 docker buildx rm 2>/dev/null || true
docker context ls --format '{{.Name}}' | grep -v '^default$' | xargs -n1 docker context rm 2>/dev/null || true

# 4) Verify empty state
docker ps -a
docker images
docker volume ls
docker network ls
```
---

### VM — Containerized Ollama (NVIDIA GPU)

1) Reset

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml down
```

2) Start stack with VM overlay (brings up `ollama` container)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  up -d ollama litellm rag-api-bge rag-api-qwen3 rag-api-e5
```

3) Warm models inside the `ollama` container

```bash
docker exec -it ollama ollama pull bge-m3
docker exec -it ollama ollama pull hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
docker exec -it ollama ollama pull yxchia/multilingual-e5-large-instruct
docker exec -it ollama ollama pull hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M
docker exec -it ollama ollama pull hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M
docker exec -it ollama ollama pull hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf
```

4) Build FAISS indexes (containers call `ollama` service)

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  index-builder --preset vm
```

5) Verify

```bash
curl -s localhost:8001/info | jq .
curl -s localhost:8002/info | jq .
curl -s localhost:8003/info | jq .
# Expect: "ollama_base_url": "http://ollama:11434" for all
```

6) Run the benchmark inside the compose network

```bash
docker compose -f docker-compose.yml -f docker-compose.vm.yml \
  run --rm benchmarker --preset vm
```

```bash
docker compose -f /root/on-premise-slm/docker-compose.yml -f /root/on-premise-slm/docker-compose.vm.yml run --rm benchmarker python -u src/benchmarking/benchmark.py --preset vm --mode generate --num-questions 3
```


```bash
docker compose -f /root/on-premise-slm/docker-compose.yml -f /root/on-premise-slm/docker-compose.vm.yml run --rm throughput-runner python -u src/throughput/runner.py --mode llm --platform-preset vm --ollama-base http://ollama:11434 --litellm http://litellm:4000 --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" --requests 1 --repetitions 1 --concurrency 1
```

Full Benchmark:
```bash
docker compose -f /root/on-premise-slm/docker-compose.yml -f /root/on-premise-slm/docker-compose.vm.yml run --rm throughput-runner python -u src/throughput/runner.py --mode llm --platform-preset vm --ollama-base http://ollama:11434 --litellm http://litellm:4000 --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" --requests 2048 --repetitions 2 --concurrency 1,2,4,8,16,32,64,128,256,512,1024
```

```bash
docker compose -f /root/on-premise-slm/docker-compose.yml -f /root/on-premise-slm/docker-compose.vm.yml run --rm throughput-runner python -u src/throughput/runner.py --mode llm --platform-preset vm --ollama-base http://ollama:11434 --litellm http://litellm:4000 --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" --requests 160 --repetitions 3 --concurrency 1,2,4,8,16
```

Evaluate this crap
```bash
docker compose run --rm benchmarker python src/benchmarking/benchmark.py \
  --mode evaluate --preset vm \
  --judge-provider litellm --judge-model azure-gpt4-1-mini \
  --run-stamp 20250913_170609
```
---

### .env vs service `environment:` precedence

- Compose loads `.env` via `env_file`, but any `environment:` entries on a service override `.env`.
- In this repo:
  - `rag-api-*` define `OLLAMA_BASE_URL` in `environment:` → they ignore `.env` for that var.
  - `index-builder` does NOT set `OLLAMA_BASE_URL` in `environment:` → it uses `.env` unless you pass `-e OLLAMA_BASE_URL=...`.
- Best practice: remove `OLLAMA_BASE_URL` from `.env` and pass it per run, as in the commands above.

---

### Sanity checks

```bash
# Show effective env for a service
docker compose -f docker-compose.yml config | sed -n '/rag-api-bge:/,/^[^ ]/p' | sed -n '/environment:/,/^[^ ]/p'
docker compose -f docker-compose.yml -f docker-compose.vm.yml config | sed -n '/rag-api-bge:/,/^[^ ]/p' | sed -n '/environment:/,/^[^ ]/p'

# Quick health/info
curl -s localhost:8001/health | jq .
curl -s localhost:8001/info | jq .

# Check host Ollama loaded models
curl -s http://localhost:11434/api/ps | jq .
```

---

### Troubleshooting quick hits

- `ollama_base_url` shows `http://ollama:11434` on Mac → You used the VM overlay locally. Bring down stacks and restart using only `docker-compose.yml`.
- Empty responses / `no_valid_answers` → Usually the RAG API couldn’t reach Ollama or first-call timeouts while pulling models. Warm models and increase `/query` timeout if needed.
- `INDEX_DIR` not found on `/info` → Rebuild indexes using the exact slug paths (see One-time config section).
