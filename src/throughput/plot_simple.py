#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import pandas as pd


def load_dataframe(csv_path: Path) -> pd.DataFrame:
    """Load benchmark CSV and derive minimal extra columns if available.

    - Aliases: requests_s -> rps, tokens_s -> tps
    - tail_ratio: latency_p95_s / latency_avg_s (if both present)
    """
    df = pd.read_csv(csv_path)
    if df.empty:
        return df

    if "requests_s" in df.columns and "rps" not in df.columns:
        df["rps"] = df["requests_s"]
    if "tokens_s" in df.columns and "tps" not in df.columns:
        df["tps"] = df["tokens_s"]

    # Ensure concurrency is numeric and sorted
    if "concurrency" in df.columns:
        df["concurrency"] = pd.to_numeric(df["concurrency"], errors="coerce")
        df = df.dropna(subset=["concurrency"]).copy()
        df["concurrency"] = df["concurrency"].astype(int)

    # tail ratio
    if {"latency_p95_s", "latency_avg_s"}.issubset(df.columns):
        # Avoid division by zero
        safe_mean = df["latency_avg_s"].replace(0, pd.NA)
        df["tail_ratio"] = df["latency_p95_s"] / safe_mean

    return df


def load_sysinfo(sysinfo_path: Path | None, csv_dir: Path) -> Dict[str, object]:
    """Load system-info.json if provided, otherwise attempt auto-discovery."""
    if sysinfo_path is None:
        candidate = csv_dir / "system-info.json"
        if candidate.exists():
            sysinfo_path = candidate
    if sysinfo_path and sysinfo_path.exists():
        try:
            with open(sysinfo_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def hardware_subtitle(sysinfo: Dict[str, object]) -> str:
    """Produce a short, robust hardware description string for subtitle."""
    if not sysinfo:
        return ""
    parts = []
    chip = sysinfo.get("chip") or sysinfo.get("processor") or sysinfo.get("cpu")
    if chip:
        parts.append(str(chip))
    mem = sysinfo.get("ram_gb") or sysinfo.get("memory_gb")
    if isinstance(mem, (int, float)):
        parts.append(f"{mem}GB RAM")
    total_cores = sysinfo.get("total_cores") or sysinfo.get("cpu_count")
    if total_cores:
        parts.append(f"{total_cores} CPU Cores")
    gpu_cores = sysinfo.get("gpu_cores")
    if gpu_cores:
        parts.append(f"{gpu_cores} GPU Cores")
    return ", ".join(parts)


def shorten_model_label(model: str) -> str:
    if model == "azure-gpt5":
        return "Azure GPT-5"
    last = model.split("/")[-1]
    if ":" in last:
        last = last.split(":", 1)[0]
    for tok in [
        "-Instruct-GGUF",
        "-instruct-gguf",
        "-Instruct",
        "-instruct",
        "-GGUF",
        "-gguf",
    ]:
        last = last.replace(tok, "")
    return last.strip("- ")


def plot_models_line(df: pd.DataFrame, y: str, ylabel: str, title: str, subtitle: str, out_path: Path) -> None:
    if y not in df.columns or df[y].dropna().empty:
        print(f"⚠ Skipping models plot for '{y}' (column missing or empty)")
        return

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for (provider, model), grp in df.groupby(["provider", "model" ]):
        g = grp.sort_values("concurrency")
        label = f"{provider}: {shorten_model_label(model)}"
        ax.plot(g["concurrency"], g[y], marker="o", linestyle="-", label=label)

    ax.set_xscale("log", base=2)
    # Explicit numeric ticks (e.g., 1, 2, 4, 8, ...)
    unique_conc = sorted(df["concurrency"].dropna().unique())
    ax.set_xticks(unique_conc)
    ax.set_xticklabels([str(int(x)) for x in unique_conc])
    ax.set_xlabel("Concurrent requests")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", ls=":", alpha=0.6)
    ax.legend(fontsize=8, loc="best")

    # Titles
    if subtitle:
        fig.suptitle(title, fontsize=14, fontweight="bold")
        ax.set_title(subtitle, fontsize=9, pad=6)
    else:
        fig.suptitle(title, fontsize=14, fontweight="bold")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"✓ wrote {out_path}")


def plot_provider_mean_line(df: pd.DataFrame, y: str, ylabel: str, title: str, subtitle: str, out_path: Path) -> None:
    if y not in df.columns or df[y].dropna().empty:
        print(f"⚠ Skipping provider plot for '{y}' (column missing or empty)")
        return

    g = df.groupby(["provider", "concurrency"], as_index=False)[y].mean()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    for provider, grp in g.groupby("provider"):
        gg = grp.sort_values("concurrency")
        ax.plot(gg["concurrency"], gg[y], marker="o", linestyle="-", label=provider)

    ax.set_xscale("log", base=2)
    # Explicit numeric ticks (e.g., 1, 2, 4, 8, ...)
    unique_conc = sorted(df["concurrency"].dropna().unique())
    ax.set_xticks(unique_conc)
    ax.set_xticklabels([str(int(x)) for x in unique_conc])
    ax.set_xlabel("Concurrent requests")
    ax.set_ylabel(ylabel)
    ax.grid(True, which="both", ls=":", alpha=0.6)
    ax.legend(title="Provider", fontsize=8, loc="best")

    if subtitle:
        fig.suptitle(title, fontsize=14, fontweight="bold")
        ax.set_title(subtitle, fontsize=9, pad=6)
    else:
        fig.suptitle(title, fontsize=14, fontweight="bold")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(out_path, dpi=300)
    plt.close(fig)
    print(f"✓ wrote {out_path}")


def main(csv: Path, sysinfo: Path | None = None, outdir: Path | None = None, fmt: str = "png") -> None:
    df = load_dataframe(csv)
    if df.empty:
        print(f"⚠ No rows in {csv}")
        return

    sysinfo_obj = load_sysinfo(sysinfo, csv.parent)
    subtitle = hardware_subtitle(sysinfo_obj)

    if outdir is None:
        outdir = csv.parent / "charts"

    # Core series
    series = [
        ("rps", "Requests/s", "models_rps_vs_concurrency"),
        ("latency_p95_s", "p95 latency (s)", "models_latency_p95_vs_concurrency"),
        ("tail_ratio", "p95 / mean latency", "models_tail_ratio_vs_concurrency"),
    ]

    for col, ylabel, fname in series:
        plot_models_line(
            df,
            y=col,
            ylabel=ylabel,
            title=f"{ylabel} vs concurrency",
            subtitle=subtitle,
            out_path=outdir / f"{fname}.{fmt}",
        )

    provider_series = [
        ("rps", "Requests/s", "provider_rps_vs_concurrency"),
        ("latency_p95_s", "p95 latency (s)", "provider_latency_p95_vs_concurrency"),
        ("tail_ratio", "p95 / mean latency", "provider_tail_ratio_vs_concurrency"),
    ]

    for col, ylabel, fname in provider_series:
        plot_provider_mean_line(
            df,
            y=col,
            ylabel=ylabel,
            title=f"{ylabel} vs concurrency (provider mean)",
            subtitle=subtitle,
            out_path=outdir / f"{fname}.{fmt}",
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Simple viewer for throughput plots")
    parser.add_argument("csv", help="Path to benchmark-results.csv")
    parser.add_argument("-s", "--sysinfo", default=None, help="Optional path to system-info.json")
    parser.add_argument("-o", "--outdir", default=None, help="Output directory (default: charts next to CSV)")
    parser.add_argument("-f", "--format", default="png", choices=("png", "pdf", "svg"), help="Image format")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    sysinfo_path = Path(args.sysinfo) if args.sysinfo else None
    outdir_path = Path(args.outdir) if args.outdir else None

    main(csv_path, sysinfo=sysinfo_path, outdir=outdir_path, fmt=args.format)
