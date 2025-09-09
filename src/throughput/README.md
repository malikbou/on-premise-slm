# Throughput Benchmarking (RAG Default)

This module benchmarks end-to-end throughput against the RAG API by default and can optionally benchmark direct LLM endpoints. Each run produces a timestamped directory with a CSV, hardware metadata, and charts.

## Quickstart (RAG mode)

Prerequisites:
- RAG API running (BGE preset):
  - `docker-compose up -d rag-api-bge` (listens at `http://localhost:8001`)
- Ollama running locally on the host: `http://localhost:11434`

Minimal smoke test:
```bash
python src/throughput/runner.py \
  --requests 2 --repetitions 1 --concurrency 1 \
  --models hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf \
  --skip-cloud --rag-base http://localhost:8001 --quiet
```

Full run (RAG mode, local SLMs + optional cloud via LiteLLM):
```bash
python src/throughput/runner.py \
  --rag-base http://localhost:8001 \
  --rag-testset data/testset/ucl-cs_single_hop_testset_gpt-4.1_20250906_111904.json \
  --repetitions 3 --requests 20 --concurrency 1,2,4,8,16 \
  --cloud-model azure-gpt5  # requires LiteLLM at http://localhost:4000
```

Notes:
- Default mode is `rag`.
- Providers are standardized: `ollama` and `cloud`.
- CSV includes a `mode` column (rag|llm).
- RAG API expects `model_name` like `ollama/<id>` for local SLMs, or a LiteLLM alias for cloud.

## Quickstart (direct LLM mode)

```bash
python src/throughput/runner.py --mode llm \
  --requests 20 --repetitions 3 --concurrency 1,2,4 \
  --skip-cloud  # run only Ollama via OpenAI-compatible endpoint
```

## Plotting (simple)

Generate the six core figures from a run CSV:
```bash
python src/throughput/plot_simple.py \
  results/runs/TIMESTAMP_PLATFORM/throughput/benchmark-results.csv \
  -s results/runs/TIMESTAMP_PLATFORM/throughput/system-info.json -f png
```
Outputs are written to `.../throughput/charts/`.

## Output Structure

```
results/runs/<YYYYMMDD_HHMMSS>_<platform>/throughput/
  ├─ benchmark-results.csv
  ├─ system-info.json
  └─ charts/
     ├─ models_rps_vs_concurrency.png
     ├─ models_latency_p95_vs_concurrency.png
     ├─ models_tail_ratio_vs_concurrency.png
     ├─ provider_rps_vs_concurrency.png
     ├─ provider_latency_p95_vs_concurrency.png
     └─ provider_tail_ratio_vs_concurrency.png
```

## CSV Schema (key columns)

- `timestamp`
- `mode` (rag|llm)
- `provider` (ollama|cloud)
- `base_url`, `model`, `concurrency`, `repetitions`, `requests`
- `successes`, `errors`, `rps`, `tps`, `latency_avg_s`, `latency_p50_s`, `latency_p95_s`
- `temperature`, `max_tokens`, `prompt_len`
- `region`, `platform`, `cpu`, `ram_gb`, `gpu`, `vram_gb`, `python`, `lib_versions`, `commit_sha`

## Tips

- On Mac, use `rag-api-bge` (`http://localhost:8001`) and ensure the FAISS index exists (build via `python src/build_index.py`).
- For cloud via LiteLLM: `docker-compose up -d litellm`, then run with `--cloud-model azure-gpt5`.
