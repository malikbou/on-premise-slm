#!/usr/bin/env python3
# src/markdown_conversion/dump_pdf_links.py
import fitz  # PyMuPDF
import csv
import sys
from pathlib import Path

def inflate_rect(rect, px=1.0):
    """Return a new Rect expanded by px in all directions."""
    return fitz.Rect(rect.x0 - px, rect.y0 - px, rect.x1 + px, rect.y1 + px)

def text_under_rect(page, rect, inflate=1.0):
    r = inflate_rect(fitz.Rect(rect), inflate)
    words = page.get_text("words")  # (x0,y0,x1,y1, word, block_no, line_no, word_no)
    hits = [w[4] for w in words if fitz.Rect(w[:4]).intersects(r)]
    return " ".join(hits).strip()

def main(pdf_path, out_csv):
    doc = fitz.open(pdf_path)
    rows = []
    for pno in range(len(doc)):
        page = doc[pno]
        for lk in page.get_links():
            if "uri" not in lk or "from" not in lk:
                continue
            r = fitz.Rect(lk["from"])
            uri = lk["uri"]
            txt = text_under_rect(page, r, inflate=1.5)
            rows.append({
                "page": pno + 1,
                "x0": r.x0, "y0": r.y0, "x1": r.x1, "y1": r.y1,
                "uri": uri,
                "text": txt
            })
    doc.close()
    Path(out_csv).parent.mkdir(parents=True, exist_ok=True)
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["page","x0","y0","x1","y1","uri","text"])
        w.writeheader()
        w.writerows(rows)
    print(f"Wrote {len(rows)} links -> {out_csv}")

if __name__ == "__main__":
    pdf = sys.argv[1]
    out = sys.argv[2] if len(sys.argv) > 2 else "data/output/pdf_links.csv"
    main(pdf, out)
