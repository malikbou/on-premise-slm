# Benchmarking Package

This package organizes the RAG benchmarking logic and documentation for running accuracy evaluations across local SLMs (via Ollama) and cloud LLM providers (via LiteLLM/OpenAI/Azure OpenAI).

## Goals
- Compare local SLMs vs cloud LLMs for RAG answer quality
- Keep GPU/VRAM usage within 12GB constraints on Vast.ai
- Provide reproducible, annotated results (hardware, provider, memory logs)

## Current Entry Point
- The main entrypoint remains `python src/benchmark.py` for now to avoid breaking workflows.
- This folder documents the design and will be used to host provider/memory utilities as we refactor.

## How It Works (High-Level)
1. Load a testset from `TESTSET_FILE` (streamed, memory-aware)
2. For each retrieval embedding model and LLM, call the RAG API `/query` to generate answers
3. Save raw answers and contexts
4. Evaluate with RAGAS metrics (faithfulness, answer_relevancy, context_precision, context_recall)
5. Save per-combination scores and a summary

## Configuration
- `RAG_API_BASE` (default: `http://rag-api:8000`)
- `TESTSET_FILE` (default: `data/testset/baseline_7_questions.json`)
- `MODELS_TO_TEST` (comma-separated; default: `ollama/gemma3:4b`)
- `EMBEDDING_MODELS` (comma-separated; defaults: `nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct`)
- `EMBEDDING_API_MAP` (e.g. `bge-m3=http://rag-api-bge:8000,nomic-embed-text=http://rag-api-nomic:8000,yxchia/multilingual-e5-large-instruct=http://rag-api-e5:8000`)
- `LITELLM_API_BASE` (default: `http://litellm:4000`)
- `OLLAMA_BASE_URL` (default: `http://host.docker.internal:11434`)
- `NUM_QUESTIONS_TO_TEST` (default: `1`)

For Mac host execution, set:
```bash
export RAG_API_BASE=http://localhost:8000
export LITELLM_API_BASE=http://localhost:4000
```

## Dry Run (Mac Local)
```bash
docker-compose up -d rag-api litellm
RAG_API_BASE=http://localhost:8000 \
LITELLM_API_BASE=http://localhost:4000 \
EMBEDDING_API_MAP="bge-m3=http://localhost:8001,nomic-embed-text=http://localhost:8002,yxchia/multilingual-e5-large-instruct=http://localhost:8003" \
EMBEDDING_MODELS="nomic-embed-text,bge-m3,yxchia/multilingual-e5-large-instruct" \
TESTSET_FILE=data/testset/baseline_7_questions.json \
NUM_QUESTIONS_TO_TEST=1 \
python src/benchmark.py
```

## Model Unload (Ollama) and keep_alive

- There is no HTTP /api/stop in Ollama. Use the CLI to unload models.

Host (Mac):
```bash
# Stop a specific model
ollama stop "<model:tag>"

# Stop all loaded models
ollama ps -q | xargs -I{} ollama stop "{}"
```

Docker (VM with an `ollama` container):
```bash
docker exec ollama ollama stop "<model:tag>"
docker exec ollama sh -lc 'ollama ps -q | xargs -I{} ollama stop "{}"'
```

keep_alive guidance:
- Mac/local development: prefer `keep_alive=0` for safety; no extra unload steps needed.
- VM/GPU: set a short TTL (e.g., 60–120s) so the model remains resident during runs and unloads shortly after.
  - Make the generator keep-alive configurable via an env in the RAG API (e.g., `GENERATOR_KEEP_ALIVE`).

## Roadmap
- Add provider dimension (local vs cloud) to the benchmark loop
- Memory lifecycle management (pre/post eval unload, GPU monitoring)
- Platform auto-detection (Mac vs Vast.ai GPU) with memory-aware defaults
- CLI overrides for providers/models/params
- Token/cost capture (optional) when exposed by the RAG API
