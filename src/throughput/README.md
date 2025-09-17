# Throughput Benchmarking (RAG-first)

This module benchmarks end-to-end RAG throughput and latency across local SLMs (Ollama) and cloud models (via LiteLLM). It favors simple defaults and thesis-ready plots.

## Requirements

- RAG API running (default: `http://localhost:8001`) with a built FAISS index
  - Build indexes once: `docker-compose up index-builder`
  - Start API: `docker-compose up -d litellm rag-api-bge` (bge-m3 at port 8001)
- Ollama running on the host for SLMs: `ollama serve`
- LiteLLM (optional) for cloud models: `docker-compose up -d litellm`

Health checks:
```bash
curl -s http://localhost:8001/health
curl -s http://localhost:8001/info | jq .
```

## Quick start

Minimal smoke test (1 model, small load):
```bash
python src/throughput/runner.py \
  --requests 2 --repetitions 1 --concurrency 1 \
  --models hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf \
  --skip-cloud --rag-base http://localhost:8001 --quiet
```

Full RAG run (default mode is RAG):
```bash
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 --skip-cloud
```

Enable cloud (via LiteLLM):
```bash
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --cloud-model azure-gpt5 --litellm http://localhost:4000 \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16
```

Outputs are written to:
```
results/runs/<YYYYMMDD_HHMMSS>_<platform>/throughput/
  ├── benchmark-results.csv
  ├── system-info.json
  └── charts/
```

## CSV schema

Columns include (non-exhaustive):
- `timestamp`, `mode` (rag|llm), `provider` (ollama|cloud), `base_url`, `model`
- `concurrency`, `repetitions`, `requests`, `successes`, `errors`
- `rps`, `tps`, `latency_avg_s`, `latency_p50_s`, `latency_p95_s`
- `temperature`, `max_tokens`, `prompt_len`, `region`, `platform`
- Hardware and versions: `cpu`, `ram_gb`, `gpu`, `vram_gb`, `python`, `lib_versions`, `commit_sha`

## Plotting (simple)

Generate the key figures with the simplified plotter:
```bash
python src/throughput/plot_simple.py \
  results/runs/<STAMP_PLATFORM>/throughput/benchmark-results.csv \
  -s results/runs/<STAMP_PLATFORM>/throughput/system-info.json -f png
```

Produced charts (in `charts/`):
- `models_rps_vs_concurrency.png`
- `models_latency_p95_vs_concurrency.png`
- `models_tail_ratio_vs_concurrency.png`
- `provider_rps_vs_concurrency.png`
- `provider_latency_p95_vs_concurrency.png`
- `provider_tail_ratio_vs_concurrency.png`

Notes:
- X-axis uses log2 scaling with numeric ticks (1,2,4,8,...).
- Subtitle shows hardware context when `system-info.json` is present.

## Tips

- Memory management: Models are stopped once per model sweep; no per-request keep-alive hints are sent.
- Start with small `--requests` and one model to validate end-to-end, then scale up.
- Use `--skip-cloud` for local-only runs; enable cloud later with `--litellm` and `--cloud-model`.

## Troubleshooting

- 0 successes: verify `--rag-base` matches a healthy API (`/health`, `/info`) and that the FAISS index exists.
- From host vs container: RAG APIs expose 8001/8002/8003; inside containers use service DNS (e.g., `rag-api-bge:8000`).
- Ollama connectivity (host): RAG APIs in Docker use `http://host.docker.internal:11434` to reach host Ollama.

## VM examples (LLM mode inside compose)
```bash
# Quick test
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 1 --repetitions 1 --concurrency 1

# Full benchmark
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 2048 --repetitions 2 --concurrency 1,2,4,8,16,32,64,128,256,512,1024

# Medium run
docker compose -f docker-compose.yml -f docker-compose.vm.yml run --rm throughput-runner \
  python -u src/throughput/runner.py --mode llm --platform-preset vm \
  --ollama-base http://ollama:11434 --litellm http://litellm:4000 \
  --cloud-models "azure-gpt5,gemini-2.5-pro,claude-opus-4-1-20250805" \
  --requests 160 --repetitions 3 --concurrency 1,2,4,8,16
```
