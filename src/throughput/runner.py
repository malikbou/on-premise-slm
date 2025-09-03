import argparse
import subprocess
import sys
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description="Wrapper for load-testing/openai_llm_benchmark.py")
    p.add_argument("--base-url", required=True)
    p.add_argument("--model", required=True)
    p.add_argument("--requests", type=int, default=100)
    p.add_argument("--concurrency", type=int, default=10)
    p.add_argument("--prompt", default="Hello, world!")
    p.add_argument("--api-key", default="")
    p.add_argument("--quiet", action="store_true")
    args = p.parse_args()

    script = Path(__file__).resolve().parents[2] / "load-testing" / "openai_llm_benchmark.py"
    cmd = [
        sys.executable,
        str(script),
        "--base-url", args.base_url,
        "--model", args.model,
        "--requests", str(args.requests),
        "--concurrency", str(args.concurrency),
        "--prompt", args.prompt,
    ]
    if args.api_key:
        cmd += ["--api-key", args.api_key]
    if args.quiet:
        cmd += ["--quiet"]

    subprocess.run(cmd, check=False)


if __name__ == "__main__":
    main()


