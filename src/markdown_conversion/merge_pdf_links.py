#!/usr/bin/env python3
"""
Merge PDF-annotated hyperlinks into a Markdown skeleton and produce a RAG-ready Markdown.

Steps:
- Extract all link annotations from the source PDF (page,bbox,uri,text)
- Load the Markdown skeleton, apply cleanup and normalization
- Inline canonical links where keywords appear (Academic Manual, Module Catalogue)
- Autolink emails in tables and paragraphs; fix malformed links
- Normalize and deduplicate tables; unwrap paragraphs
- Save final Markdown and a simple link coverage report

Usage:
  python -m src.markdown_conversion.merge_pdf_links \
    --pdf "data/Computer Science Student Handbook 2024-25.pdf" \
    --skeleton data/cs-handbook-hybrid.md \
    --out data/processed/cs-handbook.rag.md \
    [--links-out data/output/pdf_links_full.csv]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterable, List, Tuple

from . import postprocess as pp
from .repair_md import normalize_links as _normalize_links
from .dump_pdf_links import main as dump_links


def read_links_csv(csv_path: Path) -> list[tuple[int, float, float, float, float, str, str]]:
    rows: list[tuple[int, float, float, float, float, str, str]] = []
    if not csv_path.exists():
        return rows
    with csv_path.open("r", encoding="utf-8", newline="") as f:
        r = csv.DictReader(f)
        for row in r:
            try:
                page = int(float(row.get("page", "0") or 0))
                x0 = float(row.get("x0", 0) or 0)
                y0 = float(row.get("y0", 0) or 0)
                x1 = float(row.get("x1", 0) or 0)
                y1 = float(row.get("y1", 0) or 0)
                uri = (row.get("uri", "") or "").strip()
                text = (row.get("text", "") or "").strip()
                if uri:
                    rows.append((page, x0, y0, x1, y1, uri, text))
            except Exception:
                # skip malformed
                continue
    return rows


def autolink_emails_in_tables(md: str) -> str:
    """Autolink emails inside GFM table lines only.
    Keeps other table content unchanged.
    """
    import re

    email_re = re.compile(r"\b([A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,})\b")
    out_lines: list[str] = []
    in_code = False
    for ln in md.splitlines():
        t = ln.strip()
        if t.startswith("```"):
            in_code = not in_code
            out_lines.append(ln)
            continue
        if in_code:
            out_lines.append(ln)
            continue
        if ln.lstrip().startswith("|"):
            # Replace bare emails with mailto links
            def _repl(m: "re.Match[str]") -> str:
                e = m.group(1)
                # don't double-link if already inside a link
                if f"[{e}](mailto:{e})" in ln:
                    return e
                return f"[{e}](mailto:{e})"

            fixed = email_re.sub(_repl, ln)
            out_lines.append(fixed)
            continue
        out_lines.append(ln)
    return "\n".join(out_lines).strip() + "\n"


def build(md_in: Path, pdf_path: Path, out_md: Path, links_out_csv: Path | None = None) -> tuple[int, int]:
    # 1) Extract links from PDF
    csv_out = links_out_csv or Path("data/output/pdf_links_full.csv")
    csv_out.parent.mkdir(parents=True, exist_ok=True)
    dump_links(str(pdf_path), str(csv_out))

    link_rows = read_links_csv(csv_out)
    all_urls = [u for (_, _, _, _, _, u, _) in link_rows if u]
    unique_urls: list[str] = []
    seen = set()
    for u in all_urls:
        if u not in seen:
            seen.add(u)
            unique_urls.append(u)

    # 2) Load skeleton
    md_text = md_in.read_text(encoding="utf-8", errors="ignore")

    # 3) Deterministic cleanup and normalization pipeline
    md_text = pp.postprocess_markdown(md_text)
    md_text = pp.remove_navigation_cruft_and_bloat(md_text)
    md_text = pp.fix_malformed_double_links(md_text)
    # Autolink non-table content
    md_text = pp.autolink_emails_and_urls(md_text)
    # Ensure emails inside tables are linked
    md_text = autolink_emails_in_tables(md_text)
    # Improve visible URL labels for known domains
    md_text = pp.improve_url_display_text(md_text)
    # Inline canonical links by keyword using actual annotations
    md_text = pp.inline_annotations_by_keyword(md_text, annotations=unique_urls)
    # Create authentic inline links for textual references (e.g., Academic Manual Chapter X, Section Y)
    md_text = pp.create_authentic_inline_links(md_text, annotations=unique_urls)
    # Tables and paragraph shaping
    md_text = pp.normalize_tables(md_text)
    md_text = pp.deduplicate_tables(md_text)
    md_text = pp.clean_symbols(md_text)
    md_text = pp.reflow_paragraphs(md_text)
    md_text = pp.deduplicate_headings(md_text)

    # 3b) Append explicit external links by PDF page to guarantee coverage
    page_map: dict[int, list[tuple[str, str]]] = {}
    for (page, _x0, _y0, _x1, _y1, uri, text) in link_rows:
        items = page_map.setdefault(page, [])
        # De-duplicate within page while preserving order
        if uri not in (u for (_t, u) in items):
            label = text.strip() if text and len(text.strip()) >= 3 else uri
            items.append((label, uri))
    pdf_links: list[tuple[int, list[tuple[str, str]]]] = sorted(page_map.items(), key=lambda kv: kv[0])
    md_text = pp.append_links_from_pdf_annotations(md_text, pdf_links)

    # Final normalization to fix residual malformed link patterns
    md_text = _normalize_links(md_text)

    # 4) Save output
    out_md.parent.mkdir(parents=True, exist_ok=True)
    out_md.write_text(md_text, encoding="utf-8")

    # 5) Coverage report: how many PDF URLs ended up present in output
    import re

    present_urls = set(m.group(0) for m in re.finditer(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", md_text))
    covered = sum(1 for u in unique_urls if u in present_urls)
    total = len(unique_urls)

    cov_path = out_md.with_suffix(out_md.suffix + ".links_coverage.txt")
    cov_path.write_text(
        f"PDF unique URLs: {total}\nPresent in output: {covered}\nCoverage: {covered}/{total}\n",
        encoding="utf-8",
    )
    return covered, total


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge PDF links into Markdown skeleton")
    ap.add_argument("--pdf", required=True, help="Source PDF path")
    ap.add_argument("--skeleton", required=True, help="Skeleton Markdown path")
    ap.add_argument("--out", required=True, help="Output Markdown path")
    ap.add_argument("--links-out", default="data/output/pdf_links_full.csv", help="Where to store extracted links CSV")
    args = ap.parse_args()

    covered, total = build(
        Path(args.skeleton),
        Path(args.pdf),
        Path(args.out),
        Path(args.links_out),
    )
    print(f"Coverage: {covered}/{total}")


if __name__ == "__main__":
    main()
