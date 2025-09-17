#!/usr/bin/env python3

from __future__ import annotations

import argparse
import glob
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import numpy as np


def approximate_tokens(text: str) -> int:
    # Fast heuristic: ~4 chars per token
    return int(max(0, len(text)) / 4)


def load_answers(paths_glob: str) -> List[Dict]:
    files = glob.glob(paths_glob)
    rows: List[Dict] = []
    for fp in files:
        try:
            with open(fp, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Attach meta: embedding, model from filename
            stem = Path(fp).stem
            parts = stem.split("__")
            if len(parts) >= 3:
                embedding = parts[1]
                model = "__".join(parts[2:])
            else:
                embedding = "unknown"
                model = "unknown"
            for rec in data:
                rows.append({
                    "embedding": embedding,
                    "model": model,
                    "question": rec.get("user_input", ""),
                    "contexts": rec.get("retrieved_contexts", []) or [],
                    "answer": rec.get("response", ""),
                })
        except Exception:
            continue
    return rows


def compute_stats(rows: List[Dict]) -> Tuple[Dict[str, float], List[Dict[str, object]]]:
    per_row: List[Dict[str, object]] = []
    for r in rows:
        q = r.get("question", "")
        ctx = " ".join(r.get("contexts", []))
        a = r.get("answer", "")
        input_tokens = approximate_tokens(q + "\n" + ctx)
        output_tokens = approximate_tokens(a)
        per_row.append({
            "embedding": r.get("embedding"),
            "model": r.get("model"),
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": input_tokens + output_tokens,
        })

    if not per_row:
        return {}, per_row

    inp = np.array([x["input_tokens"] for x in per_row], dtype=float)
    out = np.array([x["output_tokens"] for x in per_row], dtype=float)
    tot = inp + out

    def q(p: float, arr: np.ndarray) -> float:
        return float(np.percentile(arr, p)) if arr.size else 0.0

    summary = {
        # central
        "avg_input_tokens": float(inp.mean()),
        "avg_output_tokens": float(out.mean()),
        "avg_total_tokens": float(tot.mean()),
        "median_input_tokens": float(np.median(inp)),
        "median_output_tokens": float(np.median(out)),
        "median_total_tokens": float(np.median(tot)),
        # tails for sensitivity
        "p90_input_tokens": q(90, inp),
        "p90_output_tokens": q(90, out),
        "p90_total_tokens": q(90, tot),
    }
    return summary, per_row


def create_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Compute input/output token stats from saved answers__*.json")
    p.add_argument("--answers-glob", default="results/benchmarking/*/answers__*.json")
    p.add_argument("--out", default=None, help="Optional path to save summary JSON")
    return p


def main() -> None:
    args = create_parser().parse_args()
    rows = load_answers(args.answers_glob)
    summary, _ = compute_stats(rows)
    print(json.dumps(summary or {"error": "no_rows"}, indent=2))
    if args.out and summary:
        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)


if __name__ == "__main__":
    main()
