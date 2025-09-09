#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import ScalarFormatter, MaxNLocator


# Style constants (aligned to other plots in repo)
FIGSIZE_MM: Tuple[int, int] = (160, 100)
DPI: int = 300
MARKER: str = "o"
LINESTYLE: str = "-"
XTICK_ROT: int = 30
XTICK_FSIZE: int = 8


def _mm_to_in(mm: float) -> float:
    return mm / 25.4


def _plain_numbers(ax) -> None:
    for axis in (ax.xaxis, ax.yaxis):
        fmt = ScalarFormatter(useOffset=False)
        fmt.set_scientific(False)
        axis.set_major_formatter(fmt)


def _set_all_xticks(ax, vals) -> None:
    vals = sorted(vals)
    ax.set_xticks(vals)
    ax.set_xticklabels([str(v) for v in vals], rotation=XTICK_ROT, ha="right", fontsize=XTICK_FSIZE)


def _set_dense_yticks(ax) -> None:
    ax.yaxis.set_major_locator(MaxNLocator(nbins=12, integer=True, prune=None))


def _hardware_context_line(sysinfo: Dict[str, object]) -> str:
    platform = sysinfo.get("platform", "?")
    gpu = sysinfo.get("gpu", sysinfo.get("cpu", "unknown"))
    ram = sysinfo.get("ram_gb", "?")
    vram = sysinfo.get("vram_gb")
    hw = f"{platform} | {gpu} | RAM {ram}GB"
    if vram is not None:
        hw += f" | VRAM {vram}GB"
    return hw


def _plot_multi(ax, df: pd.DataFrame, y: str, ylabel: str) -> None:
    # Each (provider, model) series
    for (provider, model), grp in df.groupby(["provider", "model" ]):
        g = grp.sort_values("concurrency")
        label = f"{provider}: {model.split('/')[-1]}"
        ax.plot(g["concurrency"], g[y], marker=MARKER, linestyle=LINESTYLE, label=label)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Concurrent requests")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ylabel} vs concurrency")
    ax.grid(True, which="both", ls=":")
    ax.legend(title="Series", fontsize=8)

    _plain_numbers(ax)
    _set_all_xticks(ax, df["concurrency"].unique())
    _set_dense_yticks(ax)


def _plot_provider_compare(ax, df: pd.DataFrame, y: str, ylabel: str) -> None:
    # One line per provider, aggregating across models (mean at each concurrency)
    g = df.groupby(["provider", "concurrency"], as_index=False)[y].mean()
    for provider, grp in g.groupby("provider"):
        gg = grp.sort_values("concurrency")
        ax.plot(gg["concurrency"], gg[y], marker=MARKER, linestyle=LINESTYLE, label=provider)

    ax.set_xscale("log", base=2)
    ax.set_xlabel("Concurrent requests")
    ax.set_ylabel(ylabel)
    ax.set_title(f"{ylabel} vs concurrency (provider mean)")
    ax.grid(True, which="both", ls=":")
    ax.legend(title="Provider")

    _plain_numbers(ax)
    _set_all_xticks(ax, df["concurrency"].unique())
    _set_dense_yticks(ax)


def main(csv_path: Path, fmt: str = "png", sysinfo_path: Path | None = None, outdir: Path | None = None) -> None:
    df = pd.read_csv(csv_path)
    if df.empty:
        print(f"⚠ No rows in {csv_path}")
        return

    # Compute additional series available in the older plotter
    # Ensure aliases exist regardless of which column names used
    if "requests_s" in df.columns and "rps" not in df.columns:
        df["rps"] = df["requests_s"]
    if "tokens_s" in df.columns and "tps" not in df.columns:
        df["tps"] = df["tokens_s"]

    df["tail_ratio"] = df.apply(
        lambda r: (float(r["latency_p95_s"]) / float(r["latency_avg_s"])) if r.get("latency_avg_s", 0) else float("nan"),
        axis=1,
    )

    # Load hardware context if provided
    sysinfo: Dict[str, object] = {}
    if not sysinfo_path:
        # Try to auto-locate next to CSV
        candidate = csv_path.parent / "system-info.json"
        if candidate.exists():
            sysinfo_path = candidate
    if sysinfo_path and Path(sysinfo_path).exists():
        with open(sysinfo_path, "r", encoding="utf-8") as f:
            sysinfo = json.load(f)

    title_suffix = _hardware_context_line(sysinfo) if sysinfo else ""

    # Output directory: default to charts subfolder next to CSV
    if outdir is None:
        outdir = csv_path.parent / "charts"
    outdir.mkdir(parents=True, exist_ok=True)
    figsize = (_mm_to_in(FIGSIZE_MM[0]), _mm_to_in(FIGSIZE_MM[1]))

    series = [
        ("rps", "Completed Requests/s", f"rps_vs_concurrency.{fmt}"),
        ("tps", "Tokens/s", f"tps_vs_concurrency.{fmt}"),
        ("latency_avg_s", "Average latency (s)", f"latency_avg_vs_concurrency.{fmt}"),
        ("latency_p95_s", "p95 latency (s)", f"latency_p95_vs_concurrency.{fmt}"),
        ("tail_ratio", "p95 / mean latency", f"tail_ratio_vs_concurrency.{fmt}"),
    ]

    # Per-series, multi-line plots for each (provider,model)
    for col, label, name in series:
        fig, ax = plt.subplots(figsize=figsize)
        _plot_multi(ax, df, col, label)
        if title_suffix:
            ax.set_title(f"{label} vs concurrency\n{title_suffix}")
        fig.tight_layout()
        out = outdir / name
        fig.savefig(out, dpi=DPI if fmt == "png" else None)
        plt.close(fig)
        print(f"✓ wrote {out}")

    # Provider mean comparison (local vs cloud trend)
    for col, label, name in series:
        fig, ax = plt.subplots(figsize=figsize)
        _plot_provider_compare(ax, df, col, label)
        if title_suffix:
            ax.set_title(f"{label} vs concurrency (provider mean)\n{title_suffix}")
        fig.tight_layout()
        out = outdir / ("provider_mean_" + name)
        fig.savefig(out, dpi=DPI if fmt == "png" else None)
        plt.close(fig)
        print(f"✓ wrote {out}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Plot throughput results for SLM vs Cloud runs")
    ap.add_argument("csv", help="Path to benchmark-results.csv")
    ap.add_argument("-f", "--format", default="png", choices=("png", "pdf", "svg"), help="Output image format")
    ap.add_argument("-s", "--sysinfo", default=None, help="Path to system-info.json (optional)")
    ap.add_argument("-o", "--outdir", default=None, help="Output directory (default: charts subfolder next to CSV)")
    args = ap.parse_args()

    csv_path = Path(args.csv)
    sysinfo_path = Path(args.sysinfo) if args.sysinfo else None
    outdir_path = Path(args.outdir) if args.outdir else None
    main(csv_path, fmt=args.format, sysinfo_path=sysinfo_path, outdir=outdir_path)
