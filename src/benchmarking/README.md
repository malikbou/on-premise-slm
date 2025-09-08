# Malik's RAG Benchmarking Script

This document explains how to use `benchmark_malik.py` - a simplified RAG benchmarking script that provides real-time feedback and easy-to-use commands.

## Quick: Plot RAG Results (summary.json → figures)

```bash
# Basic (PNG)
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json -f png

# PDF
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json -f pdf

# With custom metric weights (will normalize to sum=1)
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json \
  -w faithfulness=0.4,answer_relevancy=0.3,context_precision=0.2,context_recall=0.1

# Optional label overrides (short names)
python src/benchmarking/plot_rag_results.py \
  results/benchmarking/TIMESTAMP/summary.json \
  --label-map label_map.json
```

Outputs: `results/benchmarking/TIMESTAMP/figures/`

Generates: Figure A (grouped bars), Figure B (ranking), Figure C (radar), Figure D (heatmaps), Figure E (rank table PNG), plus `overall_ranking.csv`, `rank_summary.md`, `rank_summary.html`.

## Overview

`benchmark_malik.py` is a streamlined version of the RAG benchmarking system that:
- Shows answer snippets as they're generated (real-time feedback)
- Automatically monitors Ollama model loading/unloading
- Supports separate generation and evaluation modes
- Uses local embedding API endpoints for fast retrieval
- Evaluates with RAGAS metrics (faithfulness, answer_relevancy, context_precision, context_recall)

## Prerequisites

### 1. Build FAISS Indexes (One-time setup)
```bash
# Build indexes for all embedding models automatically
docker-compose up multi-index-builder
```

### 2. Start Required Services
```bash
# Start embedding-specific RAG APIs and LiteLLM
docker-compose up -d litellm rag-api-bge rag-api-qwen3 rag-api-e5

# Verify services are running
curl -s http://localhost:8001/info | jq .  # bge-m3
curl -s http://localhost:8002/info | jq .  # qwen3
curl -s http://localhost:8003/info | jq .  # e5
```

### 3. Ensure Ollama is Running
```bash
# On host machine (for local preset)
ollama serve
```

## Main Commands

### Generate Answers Only
```bash
python src/benchmark_malik.py --preset local --mode generate
```

**What this does:**
- Loads your testset (default: 10 questions)
- Tests all 3 embeddings × 7 models = 21 combinations
- Shows real-time answer snippets: `Q1/10: In Year 1, the Board of Examiners...`
- Monitors Ollama models before/after each run
- Saves answers to `results/benchmarking/TIMESTAMP/`

### Evaluate Existing Answers
```bash
python src/benchmark_malik.py --preset local --mode evaluate --run-stamp TIMESTAMP
```

**Example:**
```bash
python src/benchmark_malik.py --preset local --mode evaluate --run-stamp 20250908_122129
```

**What this does:**
- Finds answer files in the specified timestamp folder
- Runs RAGAS evaluation using local Ollama judge model
- Creates `scores__embedding__model.json` files
- Creates `summary.json` with all results

### Generate + Evaluate (Full Pipeline)
```bash
python src/benchmark_malik.py --preset local --mode all
```

**What this does:**
- Runs generation mode first
- Then runs evaluation mode on the generated answers
- Complete end-to-end benchmarking

## Configuration Options

### Presets
- `--preset local` - Uses localhost ports (8001, 8002, 8003)
- `--preset vm` - Uses Docker service DNS names (for containerized execution)

### Modes
- `--mode generate` - Only generate answers
- `--mode evaluate` - Only evaluate existing answers
- `--mode all` - Generate then evaluate (default)

### Ollama Model Management
```bash
# Stop models after answering (saves VRAM)
python src/benchmark_malik.py --preset local --stop-after

# Custom stop mode (auto-detected from preset)
python src/benchmark_malik.py --preset local --stop-after --stop-mode host
```

### Custom Options
```bash
# Custom number of questions
python src/benchmark_malik.py --preset local --num-questions 5

# Custom models to test
python src/benchmark_malik.py --preset local --models "azure-gpt5,ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M"

# Custom embeddings to test
python src/benchmark_malik.py --preset local --embeddings "bge-m3,yxchia/multilingual-e5-large-instruct"
```

## Default Configuration

### Embedding Models
- `bge-m3` → http://localhost:8001
- `hf.co/Qwen/Qwen3-Embedding-0.6B-GGUF:Q8_0` → http://localhost:8002
- `yxchia/multilingual-e5-large-instruct` → http://localhost:8003

### LLM Models
- `ollama/hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf`
- `ollama/hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M`
- `ollama/hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M`
- `ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M`
- `ollama/hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M`
- `ollama/hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M`
- `azure-gpt5`

### Judge Model for Evaluation
- Uses local Ollama model (e.g., `hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M`)
- No temperature restrictions (unlike Azure models)

## Output Structure

```
results/benchmarking/TIMESTAMP/
├── answers__embedding__model.json          # Raw answers with contexts
├── scores__embedding__model.json           # RAGAS evaluation scores
└── summary.json                            # All results summary
```

## Example Workflow

### Full Benchmarking Session
```bash
# 1. One-time setup (if not done)
docker-compose up multi-index-builder

# 2. Start services
docker-compose up -d litellm rag-api-bge rag-api-qwen3 rag-api-e5

# 3. Generate answers (takes ~10-15 minutes)
python src/benchmark_malik.py --preset local --mode generate

# Note the timestamp from output, e.g., "Results: results/benchmarking/20250908_122129"

# 4. Evaluate answers (takes ~5-10 minutes)
python src/benchmark_malik.py --preset local --mode evaluate --run-stamp 20250908_122129

# 5. Check results
cat results/benchmarking/20250908_122129/summary.json
```

### Quick Test (Fewer Questions/Models)
```bash
# Test with just 3 questions and 2 models
python src/benchmark_malik.py --preset local --num-questions 3 \
  --models "ollama/hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M,azure-gpt5" \
  --embeddings "bge-m3"
```

## Features

### Real-time Feedback
- Answer snippets: `Q1/10: In Year 1, the Board of Examiners confirms marks...`
- Ollama model monitoring: Shows loaded models before/after each test
- Progress tracking: Clear indication of which embedding/model combination is running

### Memory Management
- Automatic model stopping with `--stop-after`
- Memory verification: Shows models after stopping to confirm cleanup
- VRAM-conscious for 12GB constraints

### Results Organization
- Timestamped result directories
- Separate files for answers and scores
- Summary JSON for easy comparison
- Consistent naming convention for easy parsing

## Troubleshooting

### No API Mapping Errors
```bash
# Make sure you're using the correct preset
python src/benchmark_malik.py --preset local  # NOT --preset vm
```

### Empty Retrieved Contexts
```bash
# Rebuild indexes if contexts are empty
docker-compose up multi-index-builder

# Restart RAG APIs to load fresh indexes
docker-compose restart rag-api-bge rag-api-qwen3 rag-api-e5
```

### Evaluation Errors
```bash
# Make sure LiteLLM is running for judge model
docker-compose up -d litellm

# Check that answer files exist
ls results/benchmarking/TIMESTAMP/answers__*.json
```

### Model Loading Issues
```bash
# Check what models are loaded
curl -s http://localhost:11434/api/ps

# Manually stop models if needed
ollama stop "model-name"
```

## Comparison with Other Scripts

| Feature | benchmark_malik.py | benchmark_simple.py | benchmark.py |
|---------|-------------------|-------------------|--------------|
| Real-time feedback | ✅ Answer snippets | ❌ Batch only | ❌ Batch only |
| Model monitoring | ✅ Automatic | ⚙️ Manual flag | ⚙️ Complex |
| Simplicity | ✅ Easy commands | ✅ Good | ❌ Complex |
| Memory management | ✅ Built-in | ✅ Manual | ✅ Advanced |
| Evaluation | ✅ RAGAS | ✅ RAGAS | ✅ RAGAS |

**Use benchmark_malik.py when:**
- You want real-time feedback during generation
- You prefer simple, easy-to-remember commands
- You want automatic model monitoring
- You're doing iterative development/testing

**Use benchmark_simple.py when:**
- You need maximum control over parameters
- You're running automated/batch evaluations

**Use benchmark.py when:**
- You need advanced memory management features
- You're running large-scale production benchmarks
