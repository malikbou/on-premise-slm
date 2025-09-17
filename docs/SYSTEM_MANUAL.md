# System Manual: Technical Implementation

## Architecture Overview

### Core Components
1. **RAG API** (`src/main.py`): FastAPI service with retrieval and generation
2. **Index Builder** (`src/build_index.py`): FAISS vector store creation
3. **RAGAS Benchmarker** (`src/benchmarking/benchmark.py`): Quality evaluation with parallel metrics
4. **Throughput Tester** (`load-testing/openai_llm_benchmark.py`): Performance analysis
5. **Results Visualizer** (`src/benchmarking/plot_rag_results.py`): Figure generation from RAG evaluation

### Service Architecture
```
┌─────────────────┐    ┌──────────────┐    ┌─────────────┐
│   LiteLLM       │    │   RAG API    │    │   Ollama    │
│   (Proxy)       │◄──►│   (FastAPI)  │◄──►│   (Models)  │
└─────────────────┘    └──────────────┘    └─────────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐    ┌──────────────┐
│   OpenAI API    │    │   FAISS      │
│   (Evaluation)  │    │   (Vector DB)│
└─────────────────┘    └──────────────┘
```

## API Documentation

### RAG Query Endpoint
```bash
POST /query
Content-Type: application/json

{
  "question": "string",
  "model_name": "string"  # Local SLM: "ollama/<ollama-model-id>", Cloud: LiteLLM alias (e.g., "azure-gpt5")
}
```

- Model naming semantics:
  - Local SLMs: pass as `ollama/<ollama-model-id>` (e.g., `ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M`).
  - Cloud models: pass the LiteLLM alias directly (e.g., `azure-gpt5`, `gemini-2.5-pro`, `claude-opus-4-1-20250805`).

### Info
```bash
GET /info
```
Response fields:
```json
{
  "index_dir": "/app/.rag_cache/<embedding_slug>/faiss_index",
  "embedding_model": "<embedding-id>",
  "ollama_base_url": "http://ollama:11434",
  "litellm_api_base": "http://litellm:4000"
}
```

### Health Check
```bash
GET /health
```

## Configuration Reference

### Docker Services
- `litellm`: LLM proxy and routing
- `rag-api`: Main RAG application
- `index-builder`: Vector store preparation
- `benchmarker`: RAGAS evaluation

LiteLLM routing (from `config.yaml`):
- Requests with `model_name` starting `ollama/*` are forwarded to `OLLAMA_BASE_URL`.
- Aliases: `azure-gpt5`, `gemini-2.5-pro`, `claude-opus-4-1-20250805` map to their providers.

### Environment Variables
```bash
OLLAMA_BASE_URL=http://ollama:11434
OPENAI_API_KEY=your_key_here
PLATFORM=auto  # auto, mac_local, vast_ai_gpu
MEMORY_MANAGEMENT=auto  # auto, aggressive, relaxed, minimal
INDEX_DIR=.rag_cache/<embedding_slug>/faiss_index
EMBEDDING_MODEL=hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0
LITELLM_API_BASE=http://litellm:4000
```

### Index Build CLI
Build FAISS indexes before starting the API.
```bash
# Mac host (containers call host Ollama)
docker compose up -d litellm
docker compose run --rm -e OLLAMA_BASE_URL=http://host.docker.internal:11434 index-builder --preset local

# VM (inside Docker network)
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm \
  -e OLLAMA_BASE_URL=http://ollama:11434 \
  index-builder --preset vm
```

## Cross-Platform Deployment

### Mac Local (Development)
- CPU/MPS fallback when no GPU available
- Relaxed memory management
- Smaller batch sizes for testing

### Vast.ai GPU VM (Production)
- CUDA optimization with 12GB VRAM management
- Aggressive memory cleanup between models
- Full-scale benchmarking capabilities
- Compose profiles for on-demand runs: `benchmarker` and `throughput-runner`
- Helper scripts: `scripts/run-benchmarks.sh`, `scripts/run-throughput.sh`, `scripts/fetch-results.sh`

## Technical Implementation Details

### GPU Memory Management
- Automatic model unloading after evaluation
- Memory monitoring at key stages
- Platform-specific optimization

### Evaluation Framework
- RAGAS metrics: Answer relevancy, faithfulness, context recall/precision
- Parallel processing with ThreadPoolExecutor
- Memory-optimized testset loading

### Results Visualization
RAG Quality Figures
- Input: `results/benchmarking/TIMESTAMP/summary.json`
- Output: `results/benchmarking/TIMESTAMP/figures/` (Figures A–E + CSV/MD/HTML)
- CLI:
```bash
python src/benchmarking/plot_rag_results.py results/benchmarking/TIMESTAMP/summary.json -f png
```

Throughput Figures (Simple Plotter)
- Input: `results/runs/TIMESTAMP_PLATFORM/throughput/benchmark-results.csv`
- Optional: `results/runs/TIMESTAMP_PLATFORM/throughput/system-info.json`
- Output: `results/runs/TIMESTAMP_PLATFORM/throughput/charts/`
- CLI:
```bash
python src/throughput/plot_simple.py \
  results/runs/TIMESTAMP_PLATFORM/throughput/benchmark-results.csv \
  -s results/runs/TIMESTAMP_PLATFORM/throughput/system-info.json -f png
```

Throughput Runner (RAG default)
- Default `--mode` is `rag`
- Default RAG API base: `http://localhost:8001`
- Produces `benchmark-results.csv` with `mode`, `provider`, `rps`, `latency_p95_s`
- CLI examples:
```bash
# VM: quick test (inside compose network)
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 1 --repetitions 1 --concurrency 1

# VM: full benchmark
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 2048 --repetitions 2 --concurrency 1,2,4,8,16,32,64,128,256,512,1024

# VM: medium run
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 160 --repetitions 3 --concurrency 1,2,4,8,16
```

## Open WebUI Integration

Use Open WebUI as the chat frontend while retrieval and routing stay in the RAG API and LiteLLM.

### General settings (one-time)

Open WebUI → General:

- OpenAI API → Manage OpenAI API Connections:
  - Add: `https://api.openai.com/v1` (optional, for direct OpenAI usage)
  - Add: `http://rag-api-bge:8000/v1` (RAG API OpenAI-compatible surface)
    - This points to the FastAPI `/v1` endpoints implemented in `src/main.py`.

- Ollama API → Manage Ollama API Connections:
  - Add: `http://host.docker.internal:11434` (Mac host Ollama from within container)
  - VM variant: `http://ollama:11434` (if Ollama runs as a container in the same network)

- Direct Connections:
  - Allow users to connect their own OpenAI-compatible endpoints.

- Cache Base Model List:
  - If enabled, base models are fetched at startup/save only. Faster UI, but won’t show new models until next refresh/save.

Settings are persisted in the `open_webui_data` volume and survive restarts.

### Model selection and RAG toggle

- In a new chat, select a model returned by `/v1/models` (e.g., `ollama/<model-id>` or a LiteLLM cloud alias like `gpt-4o-mini`).
- Disable Open WebUI’s built-in RAG for these models to avoid double context injection:
  - Settings → Documents/RAG → turn off document ingestion/RAG for these models.

### Streaming

- The RAG API supports SSE streaming on `/v1/chat/completions` (`stream=true`). Open WebUI will display tokens as they arrive and terminates on `[DONE]`.

### References

- Open WebUI: https://docs.openwebui.com/
- Enhanced RAG guidance: https://docs.openwebui.com/features/rag#enhanced-rag-pipeline
- HTTPS/WebSockets (if fronted by Nginx): https://docs.openwebui.com/tutorials/https-nginx

*This manual is automatically updated by agents when technical changes occur.*
