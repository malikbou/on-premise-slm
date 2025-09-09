import argparse
import asyncio
import json
import os
import platform as py_platform
import random
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np
import pandas as pd


FIXED_SLM_MODELS: List[str] = [
    "hf.co/microsoft/Phi-3-mini-4k-instruct-gguf:Phi-3-mini-4k-instruct-q4.gguf",
    "hf.co/MaziyarPanahi/Phi-3.5-mini-instruct-GGUF:Q4_K_M",
    "hf.co/MaziyarPanahi/Phi-4-mini-instruct-GGUF:Q4_K_M",
    "hf.co/bartowski/Llama-3.2-3B-Instruct-GGUF:Q4_K_M",
    "hf.co/tiiuae/Falcon3-3B-Instruct-GGUF:Q4_K_M",
    "hf.co/Qwen/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
]


def _env(key: str, default: Optional[str] = None) -> Optional[str]:
    return os.getenv(key, default)


def parse_concurrency_list(csv: str) -> List[int]:
    try:
        return [int(x.strip()) for x in csv.split(",") if x.strip()]
    except Exception:
        return [1, 2, 4, 8, 16]


def detect_platform_label() -> str:
    system = py_platform.system()
    if system == "Darwin":
        return "mac"
    # Linux: try to detect GPU presence
    try:
        out = subprocess.run(["nvidia-smi", "-L"], capture_output=True, text=True, timeout=1)
        if out.returncode == 0 and out.stdout:
            return "vm"
    except Exception:
        pass
    return "other"


def get_system_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {
        "os": py_platform.platform(),
        "python": sys.version.split(" ")[0],
    }
    # CPU / RAM (best-effort without psutil)
    try:
        info["cpu"] = py_platform.processor() or py_platform.machine()
    except Exception:
        info["cpu"] = None

    # RAM detection (best-effort, no psutil)
    try:
        if py_platform.system() == "Darwin":
            # sysctl returns bytes
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=1)
            if out.returncode == 0 and out.stdout.strip().isdigit():
                mem_bytes = int(out.stdout.strip())
                info["ram_gb"] = int(round(mem_bytes / (1024 ** 3)))
        elif py_platform.system() == "Linux":
            # Parse /proc/meminfo MemTotal: kB
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        parts = line.split()
                        if len(parts) >= 2 and parts[1].isdigit():
                            kb = int(parts[1])
                            info["ram_gb"] = int(round(kb / (1024 ** 2)))
                        break
    except Exception:
        info["ram_gb"] = None

    # GPU info (best-effort via torch or nvidia-smi)
    try:
        import torch  # type: ignore

        if getattr(torch, "cuda", None) and torch.cuda.is_available():
            info["gpu"] = torch.cuda.get_device_name(0)
            info["vram_gb"] = int(torch.cuda.get_device_properties(0).total_memory / (1024 ** 3))
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            info["gpu"] = "Apple Silicon MPS"
            info["vram_gb"] = None
    except Exception:
        # Fallback to nvidia-smi
        try:
            q = subprocess.run(
                [
                    "nvidia-smi",
                    "--query-gpu=name,memory.total",
                    "--format=csv,noheader",
                    "-i",
                    "0",
                ],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if q.returncode == 0 and q.stdout:
                name_mem = q.stdout.strip().split(",")
                if len(name_mem) >= 2:
                    info["gpu"] = name_mem[0].strip()
                    # e.g., "24564 MiB"
                    try:
                        mem_mib = int(name_mem[1].strip().split(" ")[0])
                        info["vram_gb"] = int(round(mem_mib / 1024))
                    except Exception:
                        info["vram_gb"] = None
        except Exception:
            pass

    # Git commit
    try:
        r = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True, timeout=1)
        if r.returncode == 0:
            info["commit_sha"] = r.stdout.strip()
    except Exception:
        info["commit_sha"] = None

    # Library versions
    try:
        import httpx as _httpx
        import numpy as _np
        import pandas as _pd

        info["lib_versions"] = {
            "httpx": getattr(_httpx, "__version__", None),
            "numpy": getattr(_np, "__version__", None),
            "pandas": getattr(_pd, "__version__", None),
        }
    except Exception:
        info["lib_versions"] = None

    return info


def ensure_run_dir(root: Path, platform_label: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = root / f"{ts}_{platform_label}" / "throughput"
    (run_dir / "charts").mkdir(parents=True, exist_ok=True)
    return run_dir


def build_headers(api_key: str) -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    return headers


async def chat_completion(
    client: httpx.AsyncClient,
    base_url: str,
    model: str,
    prompt: str,
    max_tokens: int,
    temperature: float,
    provider: str,
    api_key: str,
    capture_responses: bool,
    backoff_attempts: int = 5,
) -> Tuple[Optional[float], Optional[int], Optional[Dict[str, Any]]]:
    url = f"{base_url.rstrip('/')}/v1/chat/completions"
    headers = build_headers(api_key)
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    # Azure via LiteLLM: use max_completion_tokens and force temperature=1 (only default supported)
    if provider == "cloud" and ("azure" in model.lower()):
        payload["max_completion_tokens"] = max_tokens
        payload["temperature"] = 1
    else:
        payload["max_tokens"] = max_tokens
        payload["temperature"] = temperature
    # Ollama-specific hint to unload after requests
    if provider == "ollama":
        payload["keep_alive"] = 0

    attempt = 0
    while True:
        t0 = time.perf_counter()
        try:
            r = await client.post(url, headers=headers, json=payload, timeout=60)
            latency = time.perf_counter() - t0
            if r.status_code == 429 or 500 <= r.status_code < 600:
                raise httpx.HTTPStatusError("retryable", request=r.request, response=r)
            r.raise_for_status()
            data = r.json()
            usage = data.get("usage", {})
            tokens = usage.get(
                "total_tokens", usage.get("prompt_tokens", 0) + usage.get("completion_tokens", 0)
            )
            return latency, tokens, data if capture_responses else None
        except Exception as e:
            attempt += 1
            if attempt >= backoff_attempts:
                return None, None, None
            # jittered exponential backoff (esp. for cloud)
            sleep_s = (2 ** (attempt - 1)) * (0.25 + random.random() * 0.5)
            await asyncio.sleep(sleep_s)


async def run_model_once(
    provider: str,
    base_url: str,
    model: str,
    prompt: str,
    requests_n: int,
    concurrency: int,
    max_tokens: int,
    temperature: float,
    api_key: str,
    capture_responses: bool,
) -> Tuple[List[float], List[int], List[Dict[str, Any]], float]:
    latencies: List[float] = []
    tokens: List[int] = []
    responses: List[Dict[str, Any]] = []

    sem = asyncio.Semaphore(concurrency)

    async def worker() -> None:
        async with sem:
            l, t, resp = await chat_completion(
                client, base_url, model, prompt, max_tokens, temperature, provider, api_key, capture_responses
            )
            if l is not None:
                latencies.append(l)
                tokens.append(int(t or 0))
                if capture_responses and resp is not None:
                    responses.append(resp)

    async with httpx.AsyncClient(http2=True, timeout=None) as client:  # type: ignore
        # Warm-up single request (ignore result)
        await chat_completion(
            client, base_url, model, prompt, max_tokens, temperature, provider, api_key, False
        )
        tic = time.perf_counter()
        tasks = [asyncio.create_task(worker()) for _ in range(requests_n)]
        await asyncio.gather(*tasks)
        toc = time.perf_counter()

    wall = toc - tic
    return latencies, tokens, responses, wall


def summarize(latencies: List[float], tokens: List[int], successes: int, total_requests: int, total_wall: float) -> Dict[str, Any]:
    row: Dict[str, Any] = {
        "n_requests": total_requests,
        "n_success": successes,
        "rps": (successes / total_wall) if total_wall > 0 else 0.0,
        "tps": (sum(tokens) / total_wall) if total_wall > 0 else 0.0,
        "latency_avg_s": float(statistics.mean(latencies)) if latencies else 0.0,
        "latency_p50_s": float(np.percentile(latencies, 50)) if latencies else 0.0,
        "latency_p95_s": float(np.percentile(latencies, 95)) if latencies else 0.0,
        "errors": int(total_requests - successes),
    }
    return row


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="SLM vs Cloud Throughput Orchestrator")
    p.add_argument("--mode", choices=["llm", "rag"], default=_env("MODE", "llm"), help="Benchmark mode: direct LLM API or RAG /query")
    p.add_argument("--ollama-base", default=_env("OLLAMA_BASE_URL", "http://localhost:11434"))
    p.add_argument("--litellm", default=_env("LITELLM_API_BASE", "http://localhost:4000"))
    p.add_argument("--cloud-model", default=_env("CLOUD_MODEL", "azure-gpt5"))
    p.add_argument(
        "--models",
        default=",".join(FIXED_SLM_MODELS),
        help="Comma-separated Ollama model IDs (fixed list by default)",
    )
    # RAG API options
    p.add_argument("--rag-base", default=_env("RAG_API_BASE", "http://localhost:8000"), help="Base URL for RAG API (src/main.py)")
    p.add_argument("--rag-testset", default=_env("RAG_TESTSET", "data/testset/baseline_7_questions.json"), help="JSON file with a list of objects containing 'user_input' fields")
    p.add_argument("--concurrency", default="1,2,4,8,16", help="Comma-separated concurrencies")
    p.add_argument("--repetitions", type=int, default=3)
    p.add_argument("--requests", type=int, default=100, help="Requests per repetition per concurrency")
    p.add_argument("--max-tokens", type=int, default=128)
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--prompt", default="Hello, world!")
    p.add_argument("--results-dir", default=_env("RESULTS_DIR", "results/runs"))
    p.add_argument("--platform-preset", choices=["local", "vm"], default=_env("PLATFORM", ""))
    p.add_argument("--stop-mode", choices=["host", "container"], default="")
    p.add_argument("--ollama-container", default="ollama")
    p.add_argument("--capture-responses", action="store_true")
    p.add_argument("--api-key", default="", help="Optional bearer token (e.g., for LiteLLM if needed)")
    p.add_argument("--region", default=_env("AZURE_REGION", ""))
    p.add_argument("--quiet", action="store_true")
    # Provider toggles
    p.add_argument("--skip-cloud", action="store_true", help="Skip cloud (LiteLLM) runs")
    p.add_argument("--skip-ollama", action="store_true", help="Skip local Ollama runs")
    return p


def resolve_stop_mode(args: argparse.Namespace) -> str:
    if args.stop_mode:
        return args.stop_mode
    if args.platform_preset == "local":
        return "host"
    if args.platform_preset == "vm":
        return "container"
    return "host"


def stop_ollama_model_safe(model_id: str, stop_mode: str, container_name: str) -> None:
    # Use existing helper if available (and pass name with "ollama/" prefix, as expected there)
    try:
        from src.benchmarking.benchmark import stop_ollama_model as _stop  # type: ignore

        _stop(f"ollama/{model_id}", stop_mode, container_name)
        return
    except Exception:
        pass

    # Fallback to direct commands
    try:
        if stop_mode == "host":
            cmd = ["ollama", "stop", model_id]
        else:
            cmd = ["docker", "exec", container_name, "ollama", "stop", model_id]
        subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except Exception:
        pass


async def run() -> None:
    args = create_parser().parse_args()

    def vprint(*msg: Any) -> None:
        if not args.quiet:
            print(*msg)

    platform_label = detect_platform_label() if not args.platform_preset else ("mac" if args.platform_preset == "local" else "vm")
    results_root = Path(args.results_dir)
    run_dir = ensure_run_dir(results_root, platform_label)

    # System info
    sysinfo = get_system_info()
    sysinfo.update({
        "platform": platform_label,
        "region": args.region or None,
    })
    with open(run_dir / "system-info.json", "w") as f:
        json.dump(sysinfo, f, indent=2)

    vprint("Throughput Orchestrator (mode:", args.mode, ")")
    vprint("Run directory:", run_dir)
    vprint("Platform:", platform_label, "| GPU:", sysinfo.get("gpu"), "| VRAM (GB):", sysinfo.get("vram_gb"))
    vprint("Concurrency levels:", args.concurrency, "| Repetitions:", args.repetitions, "| Requests per rep:", args.requests)

    # Prepare work
    slm_models: List[str] = [m.strip() for m in args.models.split(",") if m.strip()]
    conc_list = parse_concurrency_list(args.concurrency)

    rows: List[Dict[str, Any]] = []

    # Helper to record a row
    def record_row(provider: str, base_url: str, model: str, concurrency: int, repetitions: int, prompt: str,
                   summary: Dict[str, Any]) -> Dict[str, Any]:
        row: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "provider": provider,
            "base_url": base_url,
            "model": model,
            "concurrency": concurrency,
            "repetitions": repetitions,
            "requests": int(summary.get("n_requests", 0)),
            "successes": int(summary.get("n_success", 0)),
            "errors": int(summary.get("errors", 0)),
            "rps": float(summary.get("rps", 0.0)),
            "tps": float(summary.get("tps", 0.0)),
            "latency_avg_s": float(summary.get("latency_avg_s", 0.0)),
            "latency_p50_s": float(summary.get("latency_p50_s", 0.0)),
            "latency_p95_s": float(summary.get("latency_p95_s", 0.0)),
            "temperature": float(args.temperature),
            "max_tokens": int(args.max_tokens),
            "prompt_len": len(prompt),
            "region": args.region or None,
            "platform": platform_label,
            "cpu": sysinfo.get("cpu"),
            "ram_gb": None,
            "gpu": sysinfo.get("gpu"),
            "vram_gb": sysinfo.get("vram_gb"),
            "python": sysinfo.get("python"),
            "lib_versions": sysinfo.get("lib_versions"),
            "commit_sha": sysinfo.get("commit_sha"),
        }
        return row

    # Benchmark helper to run repetitions and summarize (direct LLM endpoints)
    async def benchmark(provider: str, base_url: str, model: str, concurrency: int) -> Dict[str, Any]:
        vprint(f"Starting: provider={provider} model={model} c={concurrency}")
        all_latencies: List[float] = []
        all_tokens: List[int] = []
        total_success = 0
        total_wall = 0.0
        total_attempts = args.requests * args.repetitions

        for rep in range(1, args.repetitions + 1):
            vprint(f"  Rep {rep}/{args.repetitions} ...")
            lat, tok, _resp, wall = await run_model_once(
                provider,
                base_url,
                model,
                args.prompt,
                args.requests,
                concurrency,
                args.max_tokens,
                args.temperature,
                args.api_key,
                args.capture_responses,
            )
            total_wall += wall
            total_success += len(lat)
            all_latencies.extend(lat)
            all_tokens.extend(tok)

        summary = summarize(all_latencies, all_tokens, total_success, total_attempts, total_wall)
        vprint(
            f"  Done: success={summary['n_success']}/{summary['n_requests']} | rps={summary['rps']:.2f} | ",
            f"tps={summary['tps']:.1f} | avg={summary['latency_avg_s']:.3f}s | p95={summary['latency_p95_s']:.3f}s",
        )
        return summary

    # -------- RAG mode helpers --------
    def load_rag_questions(path: Path) -> List[str]:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Expect list of objects with 'user_input'
            questions = [str(item.get("user_input", "")) for item in data if isinstance(item, dict) and item.get("user_input")]
            questions = [q for q in questions if q.strip()]
            return questions or ["Summarize the key deadlines from the handbook."]
        except Exception:
            return ["Summarize the key deadlines from the handbook."]

    async def rag_query(
        client: httpx.AsyncClient,
        rag_base: str,
        model_name: str,
        question: str,
    ) -> Tuple[Optional[float], Optional[int]]:
        url = f"{rag_base.rstrip('/')}/query"
        payload = {"question": question, "model_name": model_name}
        t0 = time.perf_counter()
        try:
            r = await client.post(url, json=payload, timeout=120)
            latency = time.perf_counter() - t0
            r.raise_for_status()
            # No token usage available from RAG API response
            return latency, 0
        except Exception:
            return None, None

    async def run_model_once_rag(
        rag_base: str,
        model_full: str,
        questions: List[str],
        requests_n: int,
        concurrency: int,
    ) -> Tuple[List[float], List[int], float]:
        latencies: List[float] = []
        tokens: List[int] = []
        sem = asyncio.Semaphore(concurrency)

        async def worker(idx: int) -> None:
            async with sem:
                q = questions[idx % len(questions)]
                l, t = await rag_query(client, rag_base, model_full, q)
                if l is not None:
                    latencies.append(l)
                    tokens.append(int(t or 0))

        async with httpx.AsyncClient(http2=True, timeout=None) as client:  # type: ignore
            # Warm-up single request
            await rag_query(client, rag_base, model_full, questions[0])
            tic = time.perf_counter()
            tasks = [asyncio.create_task(worker(i)) for i in range(requests_n)]
            await asyncio.gather(*tasks)
            toc = time.perf_counter()

        wall = toc - tic
        return latencies, tokens, wall

    async def benchmark_rag(provider: str, rag_base: str, model_full: str, concurrency: int, questions: List[str]) -> Dict[str, Any]:
        vprint(f"Starting (RAG): provider={provider} model={model_full} c={concurrency}")
        all_latencies: List[float] = []
        all_tokens: List[int] = []
        total_success = 0
        total_wall = 0.0
        total_attempts = args.requests * args.repetitions
        for rep in range(1, args.repetitions + 1):
            vprint(f"  Rep {rep}/{args.repetitions} ...")
            lat, tok, wall = await run_model_once_rag(
                rag_base,
                model_full,
                questions,
                args.requests,
                concurrency,
            )
            total_wall += wall
            total_success += len(lat)
            all_latencies.extend(lat)
            all_tokens.extend(tok)
        summary = summarize(all_latencies, all_tokens, total_success, total_attempts, total_wall)
        vprint(
            f"  Done: success={summary['n_success']}/{summary['n_requests']} | rps={summary['rps']:.2f} | ",
            f"avg={summary['latency_avg_s']:.3f}s | p95={summary['latency_p95_s']:.3f}s",
        )
        return summary

    # Run SLMs (Ollama)
    if args.mode == "llm":
        if not args.skip_ollama:
            for model in slm_models:
                for c in conc_list:
                    summary = await benchmark("ollama", args.ollama_base, model, c)
                    rows.append(record_row("ollama", args.ollama_base, model, c, args.repetitions, args.prompt, summary))
                # After finishing model, unload
                vprint(f"Unloading Ollama model: {model} ...")
                stop_ollama_model_safe(model, resolve_stop_mode(args), args.ollama_container)

    # Run Cloud (LiteLLM/Azure)
    if args.mode == "llm":
        if not args.skip_cloud:
            cloud_model = args.cloud_model
            for c in conc_list:
                summary = await benchmark("cloud", args.litellm, cloud_model, c)
                rows.append(record_row("cloud", args.litellm, cloud_model, c, args.repetitions, args.prompt, summary))

    # RAG mode: call /query on RAG API base, passing model_name as full identifier
    if args.mode == "rag":
        questions = load_rag_questions(Path(args.rag_testset))
        if not args.skip_ollama:
            for model in slm_models:
                full_name = f"ollama/{model}"
                for c in conc_list:
                    summary = await benchmark_rag("rag-ollama", args.rag_base, full_name, c, questions)
                    rows.append(record_row("rag-ollama", args.rag_base, full_name, c, args.repetitions, questions[0], summary))
                vprint(f"Unloading Ollama model: {model} ...")
                stop_ollama_model_safe(model, resolve_stop_mode(args), args.ollama_container)
        if not args.skip_cloud:
            full_name = args.cloud_model
            for c in conc_list:
                summary = await benchmark_rag("rag-cloud", args.rag_base, full_name, c, questions)
                rows.append(record_row("rag-cloud", args.rag_base, full_name, c, args.repetitions, questions[0], summary))

    # Save CSV
    df = pd.DataFrame(rows)
    csv_path = run_dir / "benchmark-results.csv"
    df.to_csv(csv_path, index=False)
    vprint(f"Saved results -> {csv_path}")


def main() -> None:
    asyncio.run(run())


if __name__ == "__main__":
    main()
