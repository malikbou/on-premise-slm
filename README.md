# RAG Evaluation Thesis Project

## Overview
Academic research project for benchmarking RAG (Retrieval-Augmented Generation) applications with focus on:
- Document quality optimization (PDF → Markdown conversion)
- High-quality testset generation (100 questions)
- Multi-model RAG performance evaluation
- Throughput and latency analysis
- Cross-platform deployment (Mac local → Vast.ai GPU VM)

## Architecture

### Core Components
- **RAG API** (`src/main.py`) - FastAPI service with retrieval and generation
- **RAG Benchmarking** (`src/benchmarking/benchmark.py`) - RAGAS evaluation with parallel metrics for answer quality
- **Index Builder** (`src/build_index.py`) - FAISS vector store creation
- **Throughput Testing** (`src/throughput/runner.py`) - Primary throughput/latency testing
- **Document Processing** (planned) - Docling-based PDF to Markdown conversion
- **Testset Generation** (planned) - 100 CS handbook questions for evaluation

### Technology Stack
- **Backend**: FastAPI, Python 3.11
- **Vector Store**: FAISS with multiple embedding models
- **LLM Integration**: LangChain, Ollama, LiteLLM proxy
- **Evaluation**: RAGAS framework (faithfulness, answer_relevancy, context_precision, context_recall)
- **Load Testing**: httpx, asyncio for concurrency testing
- **Containerization**: Docker, Docker Compose
- **Document Processing**: Unstructured, planned Docling integration
- **Data Visualization**: matplotlib, pandas

## Cross-Platform Deployment Strategy

### Mac Local Development (Testing)
```bash
# Quick setup for development and validation
docker-compose up -d litellm rag-api
python src/benchmarking/benchmark.py  # Small testset validation
python src/throughput/runner.py--requests 100 --concurrency 2
```

**Characteristics:**
- CPU/MPS mode with graceful CUDA fallback
- Smaller test parameters for faster iteration
- Memory monitoring tracks system RAM instead of VRAM
- Validation that pipeline works end-to-end

### Vast.ai GPU VM Deployment (Production)
```bash
# Core services (GPU VM)
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d ollama litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Preload embeddings + SLMs (optional but recommended)
docker exec ollama bash -lc "/app/scripts/preload-ollama-models.sh" || ./scripts/preload-ollama-models.sh

# Build FAISS indexes for all embeddings (inside Docker network)
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm -e OLLAMA_BASE_URL=http://ollama:11434 index-builder --preset vm

# Verify core services
curl -s http://localhost:11434/api/version | jq .
curl -s http://localhost:4000/v1/models | jq .
curl -s http://localhost:8001/info | jq .
```

## Quick Start

### Prerequisites
```bash
# Install dependencies
pip install -r src/requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys (OpenAI, etc.)
```

### Index Building Options

```bash
# Docker (builds all models automatically)
docker-compose up index-builder

# Python script (local)
python src/build_index.py  # Builds multiple embeddings by default

# Shell script (local)
./scripts/build-all-indexes.sh
```

### Local Development Workflow
```bash
# 1. Build all document indexes (automated for all embedding models)
docker-compose up index-builder

# 2. Start RAG API
docker-compose up rag-api litellm

# 3. Run quick validation
python src/benchmarking/benchmark.py
```

### Start API Endpoints (for Throughput Runner)

#### Mac (local host)
```bash
# Ensure Ollama is running on the host
ollama serve

# Build FAISS indexes for all embeddings (automated - run once)
docker-compose up index-builder

# Start LiteLLM and embedding-specific RAG APIs on localhost ports
docker-compose up -d litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Verify services are up
curl -s http://localhost:8001/info | jq .    # bge-m3
curl -s http://localhost:8002/info | jq .    # nomic-embed-text
curl -s http://localhost:8003/info | jq .    # e5
```

Run the throughput runner (local, RAG default):
```bash
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud
```

Notes:
- Use `--preset local` on the host so the script targets `localhost` ports. Service DNS names like `rag-api-nomic` will not resolve from the host.
- To free VRAM immediately after runs, use the Ollama CLI (e.g., `ollama stop "<model:tag>"`).

#### Vast.ai GPU VM (Docker network)
```bash
# Bring up Ollama (GPU) + LiteLLM + embedding RAG APIs
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d \
  ollama litellm rag-api-bge rag-api-qwen3 rag-api-e5

# (First time on this VM) build indexes for all embeddings (automated)
docker-compose up multi-index-builder

# Verify inside the network (from any service container) or expose ports as needed
```

Run the throughput runner (vm):
```bash
# Inside compose network (LLM mode examples)
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 1 --repetitions 1 --concurrency 1

docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 160 --repetitions 3 --concurrency 1,2,4,8,16
```

Notes:
- `--preset vm` configures service DNS (e.g., `rag-api-nomic`) and containerized Ollama (`http://ollama:11434`).
- To unload models immediately, exec into the Ollama container: `docker exec ollama ollama stop "<model:tag>"`.

### GPU VM Production Workflow
```bash
# 1. Deploy core services (no auto-bench)
docker compose -f docker-compose.yml -f docker-compose.vm.yml up -d ollama litellm rag-api-bge rag-api-qwen3 rag-api-e5

# 2. (Optional) Preload models and build indexes
docker exec ollama bash -lc "/app/scripts/preload-ollama-models.sh" || ./scripts/preload-ollama-models.sh
docker compose up index-builder

# 3. Run RAGAS benchmarking on demand
bash ./scripts/run-benchmarks.sh

# 4. Run throughput testing on demand
bash ./scripts/run-throughput.sh

# 5. Fetch results back to your laptop
# Example: scripts/fetch-results.sh root@<vm_ip> /root/on-premise-slm ./results_remote <ssh_port>
bash ./scripts/fetch-results.sh root@<vm_ip> /root/on-premise-slm ./results_remote 22
```

## Throughput Plots (RAG End-to-End)

- What we measure
  - RPS (Requests/s): completed requests per second at each concurrency.
  - p95 latency: tail latency; user experience under load.
  - Tail ratio (p95/avg): stability; closer to 1 is better.
  - Optional: TPS (Tokens/s when usage is returned), Error rate (cloud).

- How to run (RAG mode)
```bash
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud

python src/throughput/plot_simple.py \
  results/runs/<STAMP>_mac/throughput/benchmark-results.csv \
  -s results/runs/<STAMP>_mac/throughput/system-info.json -f png
```

- Outputs (saved to `results/runs/<STAMP>_<platform>/throughput/charts`)
  - `models_rps_vs_concurrency.png` — per-model throughput
  - `models_p95_latency_vs_concurrency.png` — per-model p95 latency
  - `models_tail_ratio_vs_concurrency.png` — per-model tail ratio
  - `provider_rps_vs_concurrency.png` — provider mean RPS (e.g., Ollama vs Cloud)
  - `provider_p95_latency_vs_concurrency.png` — provider mean p95 latency
  - `provider_tail_ratio_vs_concurrency.png` — provider mean tail ratio
  - `provider_error_rate_vs_concurrency.png` — error rate (cloud; if applicable)

### Docker Services
- **litellm**: LLM gateway proxy for cloud/local model routing
- **rag-api**: Main RAG API with FAISS retrieval
- **rag-api-bge**: Dedicated API for bge-m3 embedding model
- **rag-api-e5**: Dedicated API for multilingual-e5-large-instruct embedding model
- **rag-api-qwen3**: Dedicated API for qwen3 embedding model
- **index-builder**: Embedding model index builder
- **benchmarker**: Automated RAGAS evaluation runner
- **open-webui**: Web interface for manual testing

## Results Structure

### Organized Output
```
results/
├── runs/
│   ├── 2024-01-15_mac_local/
│   │   ├── rag_evaluation/
│   │   └── throughput_testing/
│   └── 2024-01-16_vast_ai_rtx4090/
│       ├── rag_evaluation/
│       └── throughput_testing/
├── comparisons/
│   ├── mac_vs_vast_ai_performance.png
│   └── cross_platform_analysis.csv
└── archive/
```

## License

Academic research project - see individual component licenses for dependencies.
