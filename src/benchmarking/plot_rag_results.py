#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.ticker import ScalarFormatter
import matplotlib as mpl


# --- Figure/style constants (aligned with load-testing/results/plot_results.py) ---
FIGSIZE_MM: Tuple[int, int] = (160, 100)
DPI: int = 300
XTICK_ROT: int = 30
XTICK_FSIZE: int = 8
GRID_STYLE: str = ":"


def _mm_to_in(mm: float) -> float:
    return mm / 25.4


def _plain_numbers_x(ax) -> None:
    fmt = ScalarFormatter(useOffset=False)
    fmt.set_scientific(False)
    ax.xaxis.set_major_formatter(fmt)


def _plain_numbers_y(ax) -> None:
    fmt = ScalarFormatter(useOffset=False)
    fmt.set_scientific(False)
    ax.yaxis.set_major_formatter(fmt)


def _ensure_outdir(outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)


# --- Model name normalization helpers ---
def _normalize_embedding_name(name: str) -> str:
    n = name
    if n.startswith("hf.co_"):
        n = n[len("hf.co_") :]
    # Convert the first underscore into a path separator for readability
    if "_" in n:
        parts = n.split("_", 1)
        n = f"{parts[0]}/{parts[1]}"
    return n


def _normalize_llm_name(name: str) -> str:
    n = name
    if n.startswith("ollama_"):
        n = n[len("ollama_") :]
    if n.startswith("hf.co_"):
        n = n[len("hf.co_") :]
    # Convert the first underscore into a path separator for readability
    if "_" in n:
        parts = n.split("_", 1)
        n = f"{parts[0]}/{parts[1]}"
    return n


# --- Data parsing and aggregation ---
METRICS: Tuple[str, ...] = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


@dataclass(frozen=True)
class Weights:
    faithfulness: float = 0.4
    answer_relevancy: float = 0.3
    context_precision: float = 0.2
    context_recall: float = 0.1

    def as_dict(self) -> Dict[str, float]:
        return {
            "faithfulness": self.faithfulness,
            "answer_relevancy": self.answer_relevancy,
            "context_precision": self.context_precision,
            "context_recall": self.context_recall,
        }


def parse_weights(expr: str | None) -> Weights:
    if not expr:
        return Weights()
    items = {}
    for kv in expr.split(","):
        if not kv:
            continue
        if "=" not in kv:
            raise ValueError(
                f"Invalid weight '{kv}'. Use key=value, comma-separated (e.g., faithfulness=0.4,answer_relevancy=0.3,...)"
            )
        k, v = kv.split("=", 1)
        k = k.strip()
        v = float(v.strip())
        if k not in METRICS:
            raise KeyError(f"Unknown metric in weights: {k}")
        items[k] = v
    # Fill defaults for any missing metrics
    w = Weights(**{**Weights().__dict__, **items})
    total = sum(w.as_dict().values())
    # Normalize to sum=1 if not already
    if not math.isclose(total, 1.0, rel_tol=1e-6):
        scaled = {k: v / total for k, v in w.as_dict().items()}
        w = Weights(
            faithfulness=scaled["faithfulness"],
            answer_relevancy=scaled["answer_relevancy"],
            context_precision=scaled["context_precision"],
            context_recall=scaled["context_recall"],
        )
    return w


def load_summary(path: Path) -> pd.DataFrame:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    rows: List[Dict[str, object]] = []
    for pair_key, metrics in data.items():
        try:
            emb_key, llm_key = pair_key.split("__", 1)
        except ValueError:
            # Fallback: cannot split — treat entire key as pair id
            emb_key, llm_key = pair_key, "unknown"

        row: Dict[str, object] = {
            "pair_id": pair_key,
            "embedding_raw": emb_key,
            "llm_raw": llm_key,
            "embedding": _normalize_embedding_name(emb_key),
            "llm": _normalize_llm_name(llm_key),
        }
        for m in METRICS:
            row[m] = float(metrics.get(m, float("nan")))
        rows.append(row)

    df = pd.DataFrame(rows)
    return df


def compute_aggregate(df: pd.DataFrame, weights: Weights) -> pd.DataFrame:
    w = weights.as_dict()
    df = df.copy()
    df["aggregate"] = (
        df["faithfulness"].fillna(0) * w["faithfulness"]
        + df["answer_relevancy"].fillna(0) * w["answer_relevancy"]
        + df["context_precision"].fillna(0) * w["context_precision"]
        + df["context_recall"].fillna(0) * w["context_recall"]
    )
    return df


# --- Label shortening and mapping ---
def _shorten_quant_text(text: str) -> Tuple[str, str | None]:
    """Extract quantization like Q8, Q5, q4 and return (clean_text, quant_label)."""
    quant = None
    # Look after colon or anywhere in text for Q or q followed by digits
    m = re.search(r"[Qq](\d+)", text)
    if m:
        quant = f"Q{m.group(1)}"
    # Remove colon suffix segments commonly containing quant info
    cleaned = text.split(":", 1)[0]
    return cleaned, quant


def _shorten_llm_label(llm: str) -> str:
    seg = llm.split("/")[-1]
    seg, quant = _shorten_quant_text(seg)
    # Remove common noise tokens
    for tok in ["-Instruct-GGUF", "-instruct-gguf", "-Instruct", "-instruct", "-GGUF", "-gguf"]:
        seg = seg.replace(tok, "")
    # Compact multiple hyphens
    seg = re.sub(r"-+", "-", seg)
    seg = seg.strip("- ")
    if quant:
        seg = f"{seg} ({quant})"
    return seg


def _shorten_embedding_label(emb: str) -> str:
    # Keep last path segment for readability
    seg = emb.split("/")[-1]
    # Remove generic words
    for tok in ["-instruct", "instruct", "-Embedding", "-embedding", "Embedding", "embedding", "-GGUF", "-gguf", "GGUF", "gguf"]:
        seg = seg.replace(tok, "")
    seg, quant = _shorten_quant_text(seg)
    # Specific patterns: e5 family → keep concise
    m = re.search(r"(e5[^-]*-[a-zA-Z0-9]+)", seg)
    if m:
        seg = m.group(1)
    # Compact repeated hyphens
    seg = re.sub(r"-+", "-", seg)
    seg = seg.strip("- ")
    if quant:
        seg = f"{seg} ({quant})"
    return seg


def _load_label_map(path: Path | None) -> Tuple[Dict[str, str], Dict[str, str]]:
    if not path:
        return {}, {}
    try:
        with path.open("r", encoding="utf-8") as f:
            mapping = json.load(f)
        llm_map = mapping.get("llm", {}) or {}
        emb_map = mapping.get("embedding", {}) or {}
        if not isinstance(llm_map, dict) or not isinstance(emb_map, dict):
            raise ValueError("label map JSON must contain 'llm' and 'embedding' dicts")
        return llm_map, emb_map
    except Exception as e:
        print(f"⚠ Failed to read label map '{path}': {e}. Proceeding without custom labels.")
        return {}, {}


# --- Plotting helpers ---
def _figsize_inches() -> Tuple[float, float]:
    return (_mm_to_in(FIGSIZE_MM[0]), _mm_to_in(FIGSIZE_MM[1]))


def _save(fig, outpath: Path, fmt: str) -> None:
    outname = outpath.with_suffix(f".{fmt}")
    fig.tight_layout()
    fig.savefig(outname, dpi=DPI if fmt == "png" else None, bbox_inches="tight")
    plt.close(fig)
    print(f"✓ wrote {outname}")


def plot_grouped_bars(
    df: pd.DataFrame,
    metric: str,
    outdir: Path,
    fmt: str,
    llm_map: Dict[str, str],
    emb_map: Dict[str, str],
) -> None:
    # Apply label maps or shorteners for readability
    llm_labels = {
        llm: llm_map.get(llm, _shorten_llm_label(llm)) for llm in sorted(df["llm"].unique())
    }
    emb_labels = {
        emb: emb_map.get(emb, _shorten_embedding_label(emb)) for emb in sorted(df["embedding"].unique())
    }

    pivot = (
        df.replace({"llm": llm_labels, "embedding": emb_labels})
        .pivot_table(index="llm", columns="embedding", values=metric, aggfunc="mean")
        .sort_index()
    )
    n_llms = len(pivot.index)
    n_embs = len(pivot.columns)
    if n_llms == 0 or n_embs == 0:
        print(f"⚠ No data to plot for metric '{metric}'. Skipping.")
        return

    x = np.arange(n_llms)
    total_width = 0.82
    bar_width = total_width / n_embs
    offsets = np.linspace(-total_width / 2 + bar_width / 2, total_width / 2 - bar_width / 2, n_embs)

    fig, ax = plt.subplots(figsize=_figsize_inches())
    for i, emb in enumerate(pivot.columns):
        values = pivot[emb].values
        ax.bar(x + offsets[i], values, width=bar_width, label=str(emb))

    ax.set_xticks(x)
    ax.set_xticklabels([str(v) for v in pivot.index], rotation=XTICK_ROT, ha="right", fontsize=XTICK_FSIZE)
    ax.set_ylabel(metric.replace("_", " ").capitalize())
    ax.set_title(f"{metric.replace('_', ' ').capitalize()} by LLM (grouped by embedding)")
    ax.grid(True, which="both", ls=GRID_STYLE, axis="y")
    # Place legend outside the plotting area on the right
    n_embs = len(pivot.columns)
    ax.legend(
        title="Embedding",
        fontsize=8,
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        borderaxespad=0.0,
        frameon=False,
        ncol=1 if n_embs <= 12 else 2,
    )
    # Only format Y axis numerically; keep custom categorical X labels
    _plain_numbers_y(ax)

    _save(fig, outdir / f"figure_A_{metric}", fmt)


def plot_ranking(
    df: pd.DataFrame,
    outdir: Path,
    fmt: str,
    save_csv: bool,
    llm_map: Dict[str, str],
    emb_map: Dict[str, str],
) -> None:
    ranked = df.copy()
    # Apply readable labels
    ranked["llm"] = ranked["llm"].map(lambda s: llm_map.get(s, _shorten_llm_label(s)))
    ranked["embedding"] = ranked["embedding"].map(lambda s: emb_map.get(s, _shorten_embedding_label(s)))
    ranked["pair"] = ranked["embedding"] + " | " + ranked["llm"]
    ranked = ranked.sort_values("aggregate", ascending=True)

    fig, ax = plt.subplots(figsize=_figsize_inches())
    ax.barh(ranked["pair"], ranked["aggregate"], color="tab:blue")
    ax.set_xlabel("Aggregate score")
    ax.set_title("Overall performance ranking (weighted mean)")
    ax.grid(True, which="both", ls=GRID_STYLE, axis="x")
    # Only format X axis numerically; keep categorical Y labels
    _plain_numbers_x(ax)

    _save(fig, outdir / "figure_B_overall_ranking", fmt)

    if save_csv:
        cols = [
            "pair_id",
            "embedding",
            "llm",
            "faithfulness",
            "answer_relevancy",
            "context_precision",
            "context_recall",
            "aggregate",
        ]
        table = ranked[cols]
        csv_path = (outdir / "overall_ranking.csv")
        table.to_csv(csv_path, index=False)
        print(f"✓ wrote {csv_path}")


def plot_radar_profiles(
    df: pd.DataFrame,
    outdir: Path,
    fmt: str,
    emb_map: Dict[str, str],
) -> None:
    # Average metrics per embedding
    by_emb = df.groupby("embedding")[list(METRICS)].mean()
    if by_emb.empty:
        print("⚠ No data for radar profiles. Skipping.")
        return

    categories = list(METRICS)
    angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False)
    angles = np.concatenate([angles, [angles[0]]])  # close the loop

    for emb, row in by_emb.iterrows():
        values = [row[m] for m in categories]
        values = np.concatenate([values, [values[0]]])  # close the loop

        fig = plt.figure(figsize=_figsize_inches())
        ax = fig.add_subplot(111, polar=True)
        ax.plot(angles, values, marker="o", linewidth=2)
        ax.fill(angles, values, alpha=0.25)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels([c.replace("_", " ") for c in categories])
        ax.set_yticklabels([])
        emb_label = emb_map.get(emb, _shorten_embedding_label(emb))
        ax.set_title(f"Performance profile — {emb_label}")
        ax.grid(True, which="both", ls=GRID_STYLE)

        # Sanitize file-friendly name to avoid suffix truncation
        safe = (
            str(emb_label)
            .replace("/", "-")
            .replace(":", "-")
            .replace(".", "-")
        )
        _save(fig, outdir / f"figure_C_profile_{safe}", fmt)


def plot_heatmaps(
    df: pd.DataFrame,
    outdir: Path,
    fmt: str,
    llm_map: Dict[str, str],
    emb_map: Dict[str, str],
) -> None:
    # Prepare labels
    df_lab = df.copy()
    df_lab["llm"] = df_lab["llm"].map(lambda s: llm_map.get(s, _shorten_llm_label(s)))
    df_lab["embedding"] = df_lab["embedding"].map(lambda s: emb_map.get(s, _shorten_embedding_label(s)))

    cmap = mpl.colormaps.get("viridis")
    vmin, vmax = 0.0, 1.0

    for metric in METRICS:
        pivot = (
            df_lab.pivot_table(index="embedding", columns="llm", values=metric, aggfunc="mean")
            .sort_index(axis=0)
            .sort_index(axis=1)
        )
        if pivot.empty:
            print(f"⚠ No data for heatmap '{metric}'. Skipping.")
            continue

        fig, ax = plt.subplots(figsize=_figsize_inches())
        im = ax.imshow(pivot.values, cmap=cmap, vmin=vmin, vmax=vmax, aspect="auto")

        # Axis labels
        ax.set_yticks(np.arange(pivot.shape[0]))
        ax.set_yticklabels(list(pivot.index))
        ax.set_xticks(np.arange(pivot.shape[1]))
        ax.set_xticklabels(list(pivot.columns), rotation=XTICK_ROT, ha="right", fontsize=XTICK_FSIZE)
        ax.set_xlabel("LLMs")
        ax.set_ylabel("Embeddings")
        ax.set_title(f"Heatmap — {metric.replace('_', ' ').capitalize()}")

        # Colorbar
        cbar = fig.colorbar(im, ax=ax)
        cbar.ax.set_ylabel("Score (0–1)", rotation=-90, va="bottom")

        _save(fig, outdir / f"heatmap_{metric}", fmt)


def main(
    summary_json: Path,
    fmt: str = "png",
    weights_expr: str | None = None,
    outdir: Path | None = None,
    save_csv: bool = True,
    label_map_path: Path | None = None,
) -> None:
    # Default output directory: sibling 'figures' under the timestamp folder
    default_outdir = summary_json.parent / "figures"
    outdir = outdir or default_outdir
    _ensure_outdir(outdir)

    df = load_summary(summary_json)
    weights = parse_weights(weights_expr)
    df = compute_aggregate(df, weights)

    llm_map, emb_map = _load_label_map(label_map_path)

    # Figure A: grouped bars for each metric
    for metric in METRICS:
        plot_grouped_bars(df, metric, outdir, fmt, llm_map, emb_map)

    # Figure B: overall ranking
    plot_ranking(df, outdir, fmt, save_csv=save_csv, llm_map=llm_map, emb_map=emb_map)

    # Figure C: radar profiles per embedding
    plot_radar_profiles(df, outdir, fmt, emb_map=emb_map)

    # Heatmaps per metric (embedding rows x LLM columns)
    plot_heatmaps(df, outdir, fmt, llm_map=llm_map, emb_map=emb_map)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Generate RAG benchmark visualizations from summary.json")
    ap.add_argument("summary_json", help="Path to results summary.json")
    ap.add_argument("-f", "--format", default="png", choices=("png", "pdf", "svg"), help="Output image format")
    ap.add_argument(
        "-w",
        "--weights",
        default=None,
        help=(
            "Metric weights as comma-separated key=value list (e.g., "
            "faithfulness=0.4,answer_relevancy=0.3,context_precision=0.2,context_recall=0.1). "
            "Will be normalized to sum to 1."
        ),
    )
    ap.add_argument("-o", "--outdir", default=None, help="Output directory (default: <timestamp>/figures next to summary.json)")
    ap.add_argument("--no-csv", action="store_true", help="Do not write the ranking CSV table")
    ap.add_argument(
        "--label-map",
        default=None,
        help=(
            "Optional JSON file with {'llm': {'raw':'Short'}, 'embedding': {'raw':'Short'}} to override label shortening."
        ),
    )
    args = ap.parse_args()

    summary_path = Path(args.summary_json)
    outdir_path = Path(args.outdir) if args.outdir else None
    main(
        summary_path,
        fmt=args.format,
        weights_expr=args.weights,
        outdir=outdir_path,
        save_csv=(not args.no_csv),
        label_map_path=Path(args.label_map) if args.label_map else None,
    )
