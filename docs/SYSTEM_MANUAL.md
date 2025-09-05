# System Manual: Technical Implementation

## Architecture Overview

### Core Components
1. **RAG API** (`src/main.py`): FastAPI service with retrieval and generation
2. **Index Builder** (`src/build_index.py`): FAISS vector store creation
3. **RAGAS Benchmarker** (`src/benchmark.py`): Quality evaluation with parallel metrics
4. **Throughput Tester** (`load-testing/openai_llm_benchmark.py`): Performance analysis
5. **Markdown Repairer** (`src/markdown_conversion/repair_with_openai.py` via `cli repair`):
   Section-by-section OpenAI pass that uses `data/output/pdf_links.csv` to restore links (esp. in tables), normalize headings, unwrap paragraphs, and ensure valid GFM tables.

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
### Repair Step Details
- Inputs: Docling+postprocess Markdown (`data/cs-handbook-hybrid.md`), PDF link dump (`data/output/pdf_links.csv`).
- Process: Splits by `#`/`##`, injects CSV subset (optionally page-bounded), prompts OpenAI to fix links/tables and cleanup.
- Output: `data/cs-handbook-repaired.md`, suitable for chunking in `build_index.py`.
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

## Technical Implementation Details

### GPU Memory Management
- Automatic model unloading after evaluation
- Memory monitoring at key stages
- Platform-specific optimization

### Evaluation Framework
- RAGAS metrics: Answer relevancy, faithfulness, context recall/precision
- Parallel processing with ThreadPoolExecutor
- Memory-optimized testset loading

*This manual is automatically updated by agents when technical changes occur.*
