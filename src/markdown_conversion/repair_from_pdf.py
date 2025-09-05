#!/usr/bin/env python3
"""
Vision one-shot PDF → Markdown repair using OpenAI Responses API.

Usage:
  python -m src.markdown_conversion.repair_from_pdf \
    --pdf "data/Computer Science Student Handbook 2024-25.pdf" \
    --out data/cs-handbook.frompdf.md \
    --model gpt-4o-mini [--in-md data/cs-handbook-hybrid.md] [--max-tokens 0]
"""

import argparse
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI


SYSTEM = """
You are a PDF → Markdown repairer. Produce clean, RAG-ready Markdown:
- Fix malformed links; autolink emails; remove furniture (Handbook Index, On this page, SharePoint icons).
- Normalize headings to #/##/###; unwrap paragraphs outside tables/lists.
- Ensure valid GFM tables. If a table is irreducibly wide, keep GFM and append a CSV code-fence copy below with a one-line caption.
- CRITICAL: Populate links INSIDE TABLE CELLS.
  * If a header indicates Email, convert foo@ucl.ac.uk -> [foo@ucl.ac.uk](mailto:foo@ucl.ac.uk).
  * If a header indicates Meeting/Zoom/Bookings/Link/Website, ensure exactly one clickable link like [Meeting link](URI) or [Website](URI).
  * For person names with no visible URL, synthesize a UCL directory search URL:
    https://search2.ucl.ac.uk/s/search.html?query={Name}&collection=website-meta&profile=_directory&tab=directory&sumbit=Go
  * Prefer hosts ending with ucl.ac.uk or containing outlook.office.com, zoom.us for labels.
Return only the final Markdown.
"""


def _is_gpt5_mini(model: str) -> bool:
    m = model.lower()
    return m.startswith("gpt-5-mini") or m == "gpt-5-mini"


def main() -> None:
    ap = argparse.ArgumentParser(description="Vision one-shot PDF → Markdown repair")
    ap.add_argument("--pdf", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--in-md", default="", help="Optional Docling Markdown to provide as additional context")
    ap.add_argument("--max-tokens", type=int, default=0)
    args = ap.parse_args()

    load_dotenv()
    client = OpenAI()

    # Read inputs
    in_md_text = ""
    if args.in_md and Path(args.in_md).exists():
        in_md_text = Path(args.in_md).read_text(encoding="utf-8", errors="ignore")

    # Build input: PDF as file input plus optional text
    content: List[dict] = [
        {"role": "developer", "content": SYSTEM},
        {"role": "user", "content": [
            {"type": "input_text", "text": "Repair this PDF into RAG-ready Markdown (return only Markdown):"},
            {"type": "input_file", "file_path": str(Path(args.pdf))},
        ]},
    ]
    if in_md_text:
        content[1]["content"] += [
            {"type": "input_text", "text": "Additional Docling Markdown context (same document):"},
            {"type": "input_text", "text": in_md_text},
        ]

    kwargs = {
        "model": args.model,
        "input": content,
        "background": True,
        "stream": True,
        "store": True,
    }
    if not _is_gpt5_mini(args.model):
        kwargs["reasoning"] = {"effort": "minimal"}
    if isinstance(args.max_tokens, int) and args.max_tokens > 0:
        kwargs["max_completion_tokens"] = args.max_tokens

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

    if resp_id:
        r = client.responses.retrieve(resp_id)
        if hasattr(r, "output_text") and r.output_text:
            text = r.output_text
        else:
            text = "".join(collected)
    else:
        text = "".join(collected)

    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(text, encoding="utf-8")
    print(f"\n\nWrote {args.out}")


if __name__ == "__main__":
    main()
