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
python src/benchmark.py

# Throughput testing
cd load-testing
python openai_llm_benchmark.py
```

### Markdown Conversion and Repair
```bash
# 1) Convert PDF to Markdown with Docling
python -m src.markdown_conversion.cli convert \
  --input "data/Computer Science Student Handbook 2024-25.pdf" \
  --output data/cs-handbook-hybrid.md --save-metrics

# 2) Dump PDF link annotations (once)
python -m src.markdown_conversion.dump_pdf_links \
  "data/Computer Science Student Handbook 2024-25.pdf" data/output/pdf_links.csv

# 3) Repair Markdown using OpenAI (requires OPENAI_API_KEY)
python -m src.markdown_conversion.cli repair \
  --links data/output/pdf_links.csv \
  --in-md data/cs-handbook-hybrid.md \
  --out-md data/cs-handbook-repaired.md \
  --model gpt-4o-mini \
  --max-tokens 2500 \
  --delay-s 0.2

# 4) Index repaired Markdown
HANDBOOK_MD_PATH=data/cs-handbook-repaired.md python src/build_index.py
```

Troubleshooting:
- Ensure `OPENAI_API_KEY` is exported in your environment.
- If requests are large, pass repeated `--pages` ranges to narrow CSV per slice.

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
