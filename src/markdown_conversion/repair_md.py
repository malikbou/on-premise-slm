#!/usr/bin/env python3
"""
Simple, block-aware Markdown repairer:
- Deterministic pre/post cleanup
- Block-aware chunking (tables and fenced code are atomic)
- Minimal LLM pass per chunk with one supported API signature

Usage:
  python -m src.markdown_conversion.repair_md \
    data/cs-handbook.md data/output/pdf_links.csv data/cs-handbook.fixed.md \
    --model gpt-5-mini --max-chars 8000 --max-tokens 2000
"""

import argparse
import os
import re
import sys
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from openai import OpenAI, BadRequestError


# ---------- Deterministic cleanup ----------

def normalize_links(s: str) -> str:
    pats = [
        (r"https://\[https", "https://"),
        (r"\]\]\(", "]("),
        (r"\)\)\]?", ")"),
        (r"https?://:?//+", "https://"),  # https://://, http:////
        (r"\((https?://[^\s\)]+)\)\)", r"(\1)"),
        (r"\[(https?://[^\s\]]+)\]", r"\1"),  # [URL] → URL
    ]
    for pat, repl in pats:
        s = re.sub(pat, repl, s)
    # Label common bare URLs
    s = re.sub(r"(?<!\()https://www\.ucl\.ac\.uk/academic-manual", "[UCL Academic Manual](https://www.ucl.ac.uk/academic-manual)", s)
    s = re.sub(r"(?<!\()https://www\.ucl\.ac\.uk/module-catalogue/?", "[UCL Module Catalogue](https://www.ucl.ac.uk/module-catalogue)", s)
    s = re.sub(r"(?<!\()https://moodle\.ucl\.ac\.uk/?", "[Moodle](https://moodle.ucl.ac.uk/)", s)
    s = re.sub(r"(?<!\()https://portico\.ucl\.ac\.uk/?", "[Portico](https://portico.ucl.ac.uk/)", s)
    # Emails
    s = re.sub(r"\b([A-Za-z0-9._%+-]+@ucl\.ac\.uk)\b", r"[\1](mailto:\1)", s)
    return s


def strip_furniture(s: str) -> str:
    s = re.sub(r"(?s)Handbook Index.*?(?=\n##|\Z)", "", s)
    s = re.sub(r"(?s)On this page.*?(?=\n##|\Z)", "", s)
    s = re.sub(r"^.*$|^.*$|^.*$|^.*$", "", s, flags=re.M)
    s = re.sub(r"^####+", "###", s, flags=re.M)
    return s


# ---------- Block-aware chunking (tables, fences atomic) ----------

def _block_iter(md: str) -> List[str]:
    out: List[str] = []
    i, n = 0, len(md)
    fence = re.compile(r"^```.*?$.*?^```$", re.M | re.S)
    table_row = re.compile(r"^\|.*\|$", re.M)
    while i < n:
        fm = fence.search(md, i)
        if fm and fm.start() == i:
            out.append(md[i : fm.end()])
            i = fm.end() + 1
            continue
        if table_row.match(md, i):
            j = i
            while j < n and table_row.match(md, j):
                k = md.find("\n", j)
                j = (k + 1) if k != -1 else n
            out.append(md[i:j])
            i = j
            continue
        k = md.find("\n\n", i)
        if k == -1:
            out.append(md[i:])
            break
        out.append(md[i : k + 2])
        i = k + 2
    return out


def chunk_blocks(md: str, max_chars: int) -> List[str]:
    blocks = _block_iter(md)
    chunks: List[str] = []
    cur = ""
    for b in blocks:
        if len(cur) + len(b) <= max_chars:
            cur += b
        else:
            if cur:
                chunks.append(cur)
            cur = b if len(b) <= max_chars else b
    if cur:
        chunks.append(cur)
    return chunks


# ---------- CSV (truncate once; same subset for every chunk) ----------

def load_csv_text(p: Path, max_lines: int = 4000) -> str:
    try:
        lines = p.read_text(encoding="utf-8", errors="ignore").splitlines()
        return "\n".join(lines[:max_lines])
    except Exception:
        return ""


# ---------- OpenAI single-call helper ----------

CLIENT: OpenAI | None = None

SYSTEM_PROMPT = (
    "You repair Markdown slices to be RAG-ready:\n"
    "- Fix malformed links (https://[https, https://://, stray )), doubled ]]).\n"
    "- Restore links in tables using the CSV dump: match by similar text on the same page; Email → mailto:, Meeting/Zoom/Bookings/Link/Website → [Meeting link](URI)/[Website](URI).\n"
    "- Convert bare URLs into [label](url) using the surrounding label if present.\n"
    "- Remove furniture (“Handbook Index”, “On this page”, SharePoint footers/icons).\n"
    "- Keep only #/##/### headings; unwrap paragraphs (not inside tables/lists).\n"
    "- Ensure valid GFM tables; if too wide/gnarly, keep GFM and append a CSV code-fence with a short caption.\n"
    "Return only the fixed Markdown for this slice."
)

USER_TMPL = (
    "Markdown slice (fix and return only the repaired slice):\n```\n\n{md}\n\n```\n\n"
    "PDF links subset (CSV with columns page,x0,y0,x1,y1,uri,text):\n```\n\n{csv}\n\n```"
)


def call_llm(model: str, md: str, csv_txt: str, max_tokens: int = 2000) -> str:
    assert CLIENT is not None
    msg = USER_TMPL.format(md=md.strip(), csv=csv_txt)
    kwargs = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": msg},
        ],
    }
    # Prefer model-specific token param where needed
    if isinstance(max_tokens, int) and max_tokens > 0:
        if "gpt-5" in (model or "").lower():
            kwargs["max_completion_tokens"] = max_tokens
        else:
            kwargs["max_tokens"] = max_tokens
    try:
        r = CLIENT.chat.completions.create(**kwargs)
    except BadRequestError as e:
        msg_e = str(e).lower()
        # Retry without unsupported token param
        if "max_tokens" in msg_e and "max_tokens" in kwargs:
            kwargs.pop("max_tokens", None)
            r = CLIENT.chat.completions.create(**kwargs)
        elif "max_completion_tokens" in msg_e and "max_completion_tokens" in kwargs:
            kwargs.pop("max_completion_tokens", None)
            r = CLIENT.chat.completions.create(**kwargs)
        else:
            raise
    return r.choices[0].message.content or ""


# ---------- Acceptance checks ----------

def acceptance_checks(md: str) -> list[str]:
    errs: list[str] = []
    if "https://[https" in md:
        errs.append("Found https://[https")
    if "https://://" in md:
        errs.append("Found https://://")
    if "]]" in md:
        errs.append("Found doubled ]]")
    if ("Handbook Index" in md) or ("On this page" in md):
        errs.append("Furniture not removed")
    return errs


# ---------- Main ----------

def main() -> None:
    ap = argparse.ArgumentParser(description="Repair Markdown using GPT and a PDF links CSV")
    ap.add_argument("input_md", type=Path)
    ap.add_argument("csv_path", type=Path)
    ap.add_argument("output_md", type=Path)
    ap.add_argument("--model", default="gpt-5-mini")
    ap.add_argument("--max-chars", type=int, default=8000)
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--stream", action="store_true", help="Print each repaired slice as it's produced")
    args = ap.parse_args()

    load_dotenv()
    global CLIENT
    CLIENT = OpenAI()

    raw = args.input_md.read_text(encoding="utf-8", errors="ignore")
    pre = normalize_links(strip_furniture(raw))

    csv_txt = load_csv_text(args.csv_path)
    chunks = chunk_blocks(pre, max_chars=args.max_chars)
    print(f"Chunks: {len(chunks)} (max_chars={args.max_chars})")

    out_parts: List[str] = []
    for i, ch in enumerate(chunks, 1):
        print(f"[{i}/{len(chunks)}] repairing slice len={len(ch)}")
        fixed = call_llm(args.model, ch, csv_txt, max_tokens=args.max_tokens)
        cleaned = normalize_links(fixed)
        out_parts.append(cleaned)
        if args.stream:
            print(f"\n--- SLICE {i}/{len(chunks)} BEGIN ---\n")
            # ensure a trailing newline for clean boundaries
            print(cleaned if cleaned.endswith("\n") else cleaned + "\n", end="")
            print(f"--- SLICE {i}/{len(chunks)} END ---\n")
            sys.stdout.flush()

    final = "\n\n".join(out_parts).strip() + "\n"
    final = normalize_links(strip_furniture(final))
    errs = acceptance_checks(final)
    if errs:
        print("Acceptance issues:")
        for e in errs:
            print(f"- {e}")
    args.output_md.parent.mkdir(parents=True, exist_ok=True)
    args.output_md.write_text(final, encoding="utf-8")
    print(f"Wrote {args.output_md}")


if __name__ == "__main__":
    main()
