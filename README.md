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
- **RAG Benchmarking** (`src/benchmark.py`) - RAGAS evaluation with parallel metrics for answer quality
- **Index Builder** (`src/build_index.py`) - FAISS vector store creation
- **Throughput Testing** (`load-testing/openai_llm_benchmark.py`) - Primary throughput/latency testing (vLLM vs Ollama)
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
python src/benchmark.py  # Small testset validation
python load-testing/openai_llm_benchmark.py --requests 100 --concurrency 2
```

**Characteristics:**
- CPU/MPS mode with graceful CUDA fallback
- Smaller test parameters for faster iteration
- Memory monitoring tracks system RAM instead of VRAM
- Validation that pipeline works end-to-end

### Vast.ai GPU VM Deployment (Production)
```bash
# Full deployment for thesis benchmarking
docker-compose -f docker-compose.vm.yml up -d
python src/benchmark.py  # Full 100-question evaluation
python load-testing/openai_llm_benchmark.py --requests 1000 --concurrency 16
```

**Characteristics:**
- 12GB VRAM constraints with aggressive model cleanup
- Full evaluation parameters and concurrency ranges
- GPU memory monitoring and optimization
- Complete thesis-quality benchmarking

### Platform Detection & Auto-Configuration
The system automatically detects the platform and adjusts:
- **Mac**: Conservative parameters, CPU/MPS mode, development-focused
- **GPU VM**: Full parameters, CUDA optimization, production-focused
- **CPU Fallback**: Minimal parameters for compatibility

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

You now have multiple ways to build FAISS indexes for your embedding models:

#### Option 1: Automated Multi-Index Builder (Recommended)
```bash
# Docker (builds all models automatically)
docker-compose up multi-index-builder

# Python script (local)
python src/build_all_indexes.py

# Shell script (local)
./scripts/build-all-indexes.sh
```

#### Option 2: Individual Index Building
```bash
# Build specific embedding model indexes
EMBEDDING_MODEL=bge-m3 docker-compose up index-builder
EMBEDDING_MODEL=nomic-embed-text docker-compose up index-builder
EMBEDDING_MODEL="yxchia/multilingual-e5-large-instruct" docker-compose up index-builder
```

**Embedding Models Configuration:**
- Default models: `bge-m3`, `hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0`, `yxchia/multilingual-e5-large-instruct`
- Override via environment: `EMBEDDING_MODELS="model1,model2,model3"`

### Local Development Workflow
```bash
# 1. Build all document indexes (automated for all embedding models)
docker-compose up multi-index-builder

# 2. Start RAG API
docker-compose up rag-api litellm

# 3. Run quick validation
python src/benchmark.py
```

### Start API Endpoints (for Simple Benchmarker)

#### Mac (local host)
```bash
# Ensure Ollama is running on the host
ollama serve

# Build FAISS indexes for all embeddings (automated - run once)
docker-compose up multi-index-builder

# Alternative: Build individual indexes (if needed)
# EMBEDDING_MODEL=bge-m3 docker-compose up index-builder
# EMBEDDING_MODEL=nomic-embed-text docker-compose up index-builder
# EMBEDDING_MODEL="yxchia/multilingual-e5-large-instruct" docker-compose up index-builder

# Start LiteLLM and embedding-specific RAG APIs on localhost ports
docker-compose up -d litellm rag-api-bge rag-api-nomic rag-api-e5

# Verify services are up
curl -s http://localhost:8001/info | jq .    # bge-m3
curl -s http://localhost:8002/info | jq .    # nomic-embed-text
curl -s http://localhost:8003/info | jq .    # e5
```

Run the simple benchmarker (local):
```bash
python src/benchmark_simple.py \
  --preset local \
  --testset data/testset/baseline_7_questions.json \
  --num-questions 10 \
  --embeddings nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct \
  --models "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M,azure-gpt5"
```

Notes:
- Use `--preset local` on the host so the script targets `localhost` ports. Service DNS names like `rag-api-nomic` will not resolve from the host.
- To free VRAM immediately after runs, use the Ollama CLI (e.g., `ollama stop "<model:tag>"`).

#### Vast.ai GPU VM (Docker network)
```bash
# Bring up Ollama (GPU) + LiteLLM + embedding RAG APIs
docker-compose -f docker-compose.yml -f docker-compose.vm.yml up -d \
  ollama litellm rag-api-bge rag-api-nomic rag-api-e5

# (First time on this VM) build indexes for all embeddings (automated)
docker-compose up multi-index-builder

# Alternative: Build individual indexes (if needed)
# EMBEDDING_MODEL=bge-m3 docker-compose up index-builder
# EMBEDDING_MODEL=nomic-embed-text docker-compose up index-builder
# EMBEDDING_MODEL="yxchia/multilingual-e5-large-instruct" docker-compose up index-builder

# Verify inside the network (from any service container) or expose ports as needed
```

Run the simple benchmarker (vm):
```bash
python src/benchmark_simple.py \
  --preset vm \
  --testset data/testset/baseline_7_questions.json \
  --num-questions 10 \
  --embeddings nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct \
  --models "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M,azure-gpt5"
```

Notes:
- `--preset vm` configures service DNS (e.g., `rag-api-nomic`) and containerized Ollama (`http://ollama:11434`).
- To unload models immediately, exec into the Ollama container: `docker exec ollama ollama stop "<model:tag>"`.

### GPU VM Production Workflow
```bash
# 1. Deploy full stack
docker-compose -f docker-compose.vm.yml up -d

# 2. Run complete evaluation
python src/benchmark.py

# 3. Throughput testing
cd load-testing
python openai_llm_benchmark.py --requests 1000 --concurrency 16
```

## Agent-Assisted Development

This project uses specialized AI agents for different tasks. Each agent has specific instructions:

### Document Processing Agent
```bash
# Read agent instructions and process documents
# Agent reads: .agent-prompts/document-processor.md
# Task: Convert PDF to high-quality Markdown with Docling, recover 15+ missing tables
```

### Testset Generation Agent
```bash
# Generate 100 high-quality questions using knowledge graph
# Agent reads: .agent-prompts/testset-generator.md
# Task: Leverage existing generate_testset_kg.py for multi-hop questions
```

### RAG Benchmarking Agent
```bash
# Optimize RAGAS evaluation with GPU memory management
# Agent reads: .agent-prompts/rag-benchmarker.md
# Task: Implement systematic model unloading for 12GB VRAM constraints
```

### Throughput Testing Agent
```bash
# Enhance load testing with hardware info and organization
# Agent reads: .agent-prompts/throughput-tester.md
# Task: Add hardware context to charts and organize results
```

## Configuration

### Environment Variables
```bash
# Core Configuration
OPENAI_API_KEY=your_openai_key
OLLAMA_BASE_URL=http://localhost:11434
LITELLM_API_BASE=http://localhost:4000

# Benchmarking Configuration
MODELS_TO_TEST=ollama/gemma2:2b,ollama/Qwen2.5-3B-Instruct-GGUF:Q4_K_M,ollama/Llama-3.2-3B-Instruct-GGUF:Q4_K_M
EMBEDDING_MODELS=nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct
NUM_QUESTIONS_TO_TEST=10  # Use 100 for full evaluation

# Platform-Specific (auto-detected)
PLATFORM=auto  # auto, mac_local, vast_ai_gpu
MEMORY_MANAGEMENT=auto  # auto, aggressive, relaxed, minimal

# Azure OpenAI (optional)
# Use the deployment-as-model form via LiteLLM alias 'azure-gpt5' or direct 'azure/<deployment_name>'
AZURE_OPENAI_API_BASE=https://emtechfoundrytrial2.cognitiveservices.azure.com
AZURE_OPENAI_API_VERSION=2024-12-01-preview
AZURE_OPENAI_API_KEY=your_azure_key
```

### Docker Services
- **litellm**: LLM gateway proxy for cloud/local model routing
- **rag-api**: Main RAG API with FAISS retrieval
- **rag-api-bge**: Dedicated API for bge-m3 embedding model
- **rag-api-nomic**: Dedicated API for nomic-embed-text embedding model
- **rag-api-e5**: Dedicated API for multilingual-e5-large-instruct embedding model
- **index-builder**: Single embedding model index builder
- **multi-index-builder**: Automated multi-embedding index builder (builds all models)
- **benchmarker**: Automated RAGAS evaluation runner
- **ollama-benchmark**: Throughput testing runner
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

### Hardware Context
All results include comprehensive hardware information:
- System specifications (CPU, RAM, GPU)
- Platform identification (Mac local vs Vast.ai VM)
- Memory usage tracking (system RAM vs VRAM)
- Environment metadata for reproducibility

## Key Files

### Core Implementation
- `src/main.py` - RAG API with multi-model support
- `src/benchmark.py` - RAGAS evaluation with memory management
- `src/build_index.py` - Single embedding model FAISS index creation
- `src/build_all_indexes.py` - Automated multi-embedding model index builder
- `scripts/build-all-indexes.sh` - Shell script for automated index building
- `load-testing/openai_llm_benchmark.py` - Throughput testing
- `load-testing/results/plot_results.py` - Chart generation

### Configuration & Documentation
- `.cursorrules` - Project context for AI assistants
- `.agent-prompts/` - Task-specific agent instructions
- `config.yaml` - LiteLLM proxy configuration
- `docker-compose.yml` - Local development setup
- `docker-compose.vm.yml` - GPU VM deployment setup

### Data & Results
- `data/cs-handbook.md` - Source document (current)
- `testset/` - Question datasets for evaluation
- `results/` - Organized benchmark results
- `load-testing/results/` - Throughput testing output

## Development Workflow

### 1. Local Testing (Mac)
- Quick validation with small parameters
- End-to-end pipeline verification
- Agent-assisted development iteration

### 2. Agent Enhancement
- Use `.agent-prompts/` for specific tasks
- Cross-platform compatibility ensured
- Memory management optimization

### 3. Production Deployment (Vast.ai)
- Full parameter benchmarking
- GPU memory optimization
- Thesis-quality result generation

### 4. Result Analysis
- Hardware-contextualized charts
- Cross-platform performance comparison
- Academic presentation preparation

## Memory Management

### Critical for 12GB VRAM Constraints
- Systematic model unloading between evaluations
- Memory-aware batch sizing and concurrency limits
- Platform-specific optimization (aggressive on GPU, relaxed on Mac)
- Real-time VRAM monitoring with PyTorch CUDA utilities

### Cross-Platform Adaptation
- **Mac**: System RAM monitoring, conservative parameters
- **Vast.ai**: VRAM monitoring, aggressive cleanup, full parameters
- **Auto-detection**: Platform identification and appropriate configuration

## Academic Standards

- **Reproducibility**: Complete hardware and environment logging
- **Rigor**: Established RAGAS metrics for credible evaluation
- **Documentation**: Comprehensive agent instructions and configuration
- **Presentation**: Professional charts suitable for thesis documentation
- **Cross-Platform**: Validated across development and production environments

## License

Academic research project - see individual component licenses for dependencies.
