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
  "model": "string"
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

### Environment Variables
```bash
OLLAMA_BASE_URL=http://ollama:11434
OPENAI_API_KEY=your_key_here
PLATFORM=auto  # auto, mac_local, vast_ai_gpu
MEMORY_MANAGEMENT=auto  # auto, aggressive, relaxed, minimal
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
- Produces `benchmark-results.csv` with columns including `mode`, `provider`, `rps`, `latency_p95_s`
- CLI examples:
```bash
# Smoke test
python src/throughput/runner.py \
  --requests 2 --repetitions 1 --concurrency 1 \
  --models hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf \
  --skip-cloud --rag-base http://localhost:8001 --quiet

# Full sweep
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud
```

VM (Docker network) examples:
```bash
# Compose profile inside Docker network
bash ./scripts/run-throughput.sh

# From host targeting Docker DNS
python src/throughput/runner.py \
  --platform-preset vm \
  --rag-base http://rag-api-bge:8000 \
  --rag-testset /app/data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud
```

*This manual is automatically updated by agents when technical changes occur.*
