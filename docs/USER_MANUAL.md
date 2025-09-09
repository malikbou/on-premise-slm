# User Manual: On-Premise SLM RAG Evaluation

## Installation

### Prerequisites
- Python 3.8+
- Docker and Docker Compose
- Git

### Platform-Specific Setup

#### Mac Local Development
```bash
# Clone repository
git clone <repo-url>
cd on-premise-slm

# Install dependencies
pip install -r src/requirements.txt

# Start services
docker-compose up -d
```

#### Vast.ai GPU VM Deployment
```bash
# Clone repository
git clone <repo-url>
cd on-premise-slm

# Start with VM configuration
docker-compose -f docker-compose.vm.yml up -d
```

## Usage Workflows

### Cross-Platform Development
1. **Local Testing (Mac)**: Develop and test with small datasets
2. **Production Deployment (Vast.ai)**: Full-scale benchmarking with GPU acceleration

### RAG Evaluation
```bash
# Build vector index
python src/build_index.py

# Run RAGAS benchmarking
python src/benchmarking/benchmark.py

# Throughput testing
cd load-testing
python openai_llm_benchmark.py
```

### Visualize RAG Results (summary.json → figures)
```bash
# Basic (PNG)
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json -f png

# PDF
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json -f pdf
```
Outputs: `results/benchmarking/TIMESTAMP/figures/` (Figures A–E + CSV/MD/HTML)

### Visualize Throughput Results (simple)
```bash
# Basic (PNG)
python src/throughput/plot_simple.py \
  results/runs/TIMESTAMP_PLATFORM/throughput/benchmark-results.csv \
  -s results/runs/TIMESTAMP_PLATFORM/throughput/system-info.json -f png

# Example (from latest run)
python src/throughput/plot_simple.py \
  results/runs/20250909_130035_mac/throughput/benchmark-results.csv \
  -s results/runs/20250909_130035_mac/throughput/system-info.json
```
Outputs: `results/runs/TIMESTAMP_PLATFORM/throughput/charts/`

Generated figures:
- models_rps_vs_concurrency.png
- models_latency_p95_vs_concurrency.png
- models_tail_ratio_vs_concurrency.png
- provider_rps_vs_concurrency.png
- provider_latency_p95_vs_concurrency.png
- provider_tail_ratio_vs_concurrency.png

### Run Throughput Benchmark (RAG default)
```bash
# Minimal smoke test (local SLM via RAG API bge @ 8001)
python src/throughput/runner.py \
  --requests 2 --repetitions 1 --concurrency 1 \
  --models hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf \
  --skip-cloud --rag-base http://localhost:8001 --quiet

# Full RAG sweep
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud
```

## Configuration

### Environment Variables
- `OLLAMA_BASE_URL`: Ollama server endpoint
- `OPENAI_API_KEY`: OpenAI API key for evaluation
- `PLATFORM`: auto, mac_local, vast_ai_gpu

### Model Configuration
Edit `config.yaml` for LiteLLM routing and model management.

## Troubleshooting

### Common Issues
- **GPU Memory**: Use `docker-compose.vm.yml` for 12GB VRAM management
- **Mac Compatibility**: Automatic fallback to CPU/MPS when GPU unavailable
- **Model Loading**: Automatic model unloading prevents OOM errors

*This manual is automatically updated by agents when components change.*
