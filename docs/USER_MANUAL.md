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
