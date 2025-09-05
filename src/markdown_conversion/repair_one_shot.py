#!/usr/bin/env python3
"""
One-shot Markdown repair using OpenAI Responses API with background+stream.

Usage:
  python -m src.markdown_conversion.repair_one_shot \
    --in-md data/cs-handbook.md \
    --csv data/output/pdf_links.csv \
    --out data/cs-handbook.final.md \
    --model gpt-5-mini \
    [--max-tokens 0] [--fail-on-missing]
"""

import argparse
from pathlib import Path
from typing import List, Tuple

from dotenv import load_dotenv
from openai import OpenAI


def _is_gpt5_mini(model: str) -> bool:
    m = model.lower()
    return m.startswith("gpt-5-mini") or m == "gpt-5-mini"


def _table_blocks(md: str) -> List[List[str]]:
    """Return list of table blocks (each a list of lines) for GFM tables.
    Very lightweight detector: consecutive lines starting with '|' and at least
    one separator line with dashes. Idempotent and tolerant to spacing.
    """
    blocks: List[List[str]] = []
    cur: List[str] = []
    for line in md.splitlines():
        if line.strip().startswith("|"):
            cur.append(line)
            continue
        # boundary
        if cur:
            # ensure it's a real table (has a separator row with ---)
            if any("---" in l for l in cur[:3]):
                blocks.append(cur)
            cur = []
    if cur:
        if any("---" in l for l in cur[:3]):
            blocks.append(cur)
    return blocks


def _split_cells(row: str) -> List[str]:
    # naive split on '|' and strip; drop first/last if empty borders
    parts = [c.strip() for c in row.split("|")]
    if parts and parts[0] == "":
        parts = parts[1:]
    if parts and parts[-1] == "":
        parts = parts[:-1]
    return parts


def _cell_has_link(cell: str) -> bool:
    # minimal: markdown link or mailto or bare http(s)
    if "](" in cell:
        return True
    lc = cell.lower()
    if "mailto:" in lc:
        return True
    if "http://" in lc or "https://" in lc:
        return True
    return False


def _cell_should_link(cell: str, headers: List[str]) -> bool:
    # If it looks like an email or a capitalized name, or header hints
    import re
    c = cell.strip()
    if not c:
        return False
    if "@" in c and "." in c:
        return True
    # simple Name Surname detector (two+ capitalized words)
    tokens = [t for t in re.split(r"\s+", c) if t]
    caps = sum(1 for t in tokens if t[:1].isupper())
    if len(tokens) >= 2 and caps >= 2:
        return True
    # header keywords
    header_text = " ".join(h.lower() for h in headers)
    if any(k in header_text for k in ["email", "meeting", "zoom", "bookings", "website", "link"]):
        # assume cells under such columns should be links
        return True
    return False


def acceptance_checks(md: str) -> Tuple[int, int]:
    """Return (missing_links, total_should_link) across all tables.
    We conservatively flag cells that appear to need links but lack them.
    """
    missing = 0
    total = 0
    for block in _table_blocks(md):
        if len(block) < 2:
            continue
        header = block[0]
        headers = _split_cells(header)
        for row in block[2:]:  # skip header and separator
            cells = _split_cells(row)
            for cell in cells:
                if _cell_should_link(cell, headers):
                    total += 1
                    if not _cell_has_link(cell):
                        missing += 1
    return missing, total


SYSTEM = """
You repair imperfect Markdown to be RAG-ready.
Must do:
- Fix malformed links (https://[https, https://://, stray "))", doubled "]] ").
- Autolink emails.
- Strip furniture (Handbook Index, On this page, SharePoint icons).
- Keep only #/##/### headings; unwrap paragraphs (not inside tables/lists).
- Ensure valid GFM tables. If a table is very wide, keep GFM and append a CSV code-fence copy below it with a one-line caption.
- Use the provided PDF links CSV (page,x0,y0,x1,y1,uri,text) to restore links INSIDE TABLE CELLS:
  * If a column header indicates Email, convert foo@ucl.ac.uk -> [foo@ucl.ac.uk](mailto:foo@ucl.ac.uk).
  * If a header indicates Meeting/Zoom/Bookings/Link/Website, ensure exactly one clickable link like [Meeting link](URI) or [Website](URI).
  * Match cell words to the CSV 'text' and pick its URI; if multiple, prefer hosts ending with ucl.ac.uk or containing outlook.office.com, zoom.us.
Return ONLY the repaired Markdown for the slice.
"""


def run(in_md: str, out_path: str, model: str, csv_path: str = "", max_tokens: int = 0, fail_on_missing: bool = False) -> None:
    load_dotenv()
    client = OpenAI()

    md = Path(in_md).read_text(encoding="utf-8", errors="ignore")
    csv_txt = ""
    if csv_path and Path(csv_path).exists():
        csv_txt = Path(csv_path).read_text(encoding="utf-8", errors="ignore")

    user_input: List[dict] = [
        {"role": "developer", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "input_text", "text": "Repair the following Markdown (return only Markdown):"},
            {"type": "input_text", "text": md},
        ]},
    ]
    if csv_txt:
        user_input[1]["content"] += [
            {"type": "input_text", "text": "PDF link dump (CSV: page,x0,y0,x1,y1,uri,text):"},
            {"type": "input_text", "text": csv_txt},
        ]

    kwargs = {
        "model": model,
        "input": user_input,
        "background": True,
        "stream": True,
        "store": True,
    }
    # Only pass optional fields when likely supported
    if not _is_gpt5_mini(model):
        kwargs["reasoning"] = {"effort": "minimal"}
        # omit verbosity knob unless supported; safe to exclude by default

    if isinstance(max_tokens, int) and max_tokens > 0:
        # Prefer max_completion_tokens for newer models; Responses API tolerates omission otherwise
        kwargs["max_completion_tokens"] = max_tokens

    stream = client.responses.create(**kwargs)

    collected: List[str] = []
    resp_id: str | None = None
    for event in stream:
        if not resp_id and hasattr(event, "response_id"):
            resp_id = event.response_id
        t = getattr(event, "delta", None)
        if t:
            print(t, end="", flush=True)
            collected.append(t)

    # If stream dropped, try to retrieve
    if resp_id:
        r = client.responses.retrieve(resp_id)
        if hasattr(r, "output_text") and r.output_text:
            text = r.output_text
        else:
            text = "".join(collected)
    else:
        text = "".join(collected)

    # Acceptance checks
    missing, total = acceptance_checks(text)
    if total:
        print(f"\nTable link acceptance: missing {missing} / should-link {total}")
    if fail_on_missing and missing > 0:
        print("One-shot acceptance failed: missing links in table cells.")

    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    print(f"\n\nWrote {out_path}")
    if fail_on_missing and missing > 0:
        raise SystemExit(2)


def main() -> None:
    ap = argparse.ArgumentParser(description="One-shot Markdown repair (background+stream)")
    ap.add_argument("--in-md", required=True)
    ap.add_argument("--csv", required=False, default="")
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--max-tokens", type=int, default=0)
    ap.add_argument("--fail-on-missing", action="store_true")
    args = ap.parse_args()
    run(args.in_md, args.out, args.model, args.csv, args.max_tokens, args.fail_on_missing)


if __name__ == "__main__":
    main()
