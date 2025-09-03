from typing import List, Tuple


def _markdown_table(rows: List[List[str]]) -> str:
    if not rows:
        return ""
    norm = [[str(c).strip() for c in r] for r in rows]
    header = norm[0] if norm else []
    delim = ["---" for _ in header]
    lines = ["| " + " | ".join(header) + " |", "| " + " | ".join(delim) + " |"]
    for r in norm[1:]:
        lines.append("| " + " | ".join(r) + " |")
    return "\n".join(lines)


def recover_tables(pdf_path: str, page_indices: List[int] | None = None) -> List[Tuple[int, str]]:
    try:
        import pdfplumber
    except Exception:
        return []
    recovered: List[Tuple[int, str]] = []
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = list(range(len(pdf.pages))) if page_indices is None else page_indices
            for p in pages:
                try:
                    page = pdf.pages[p]
                    tables = page.extract_tables() or []
                    for tbl in tables:
                        md = _markdown_table(tbl)
                        if md.strip():
                            recovered.append((p + 1, md))
                except Exception:
                    continue
    except Exception:
        return []
    return recovered


