# Inline the validation API to avoid dependency on legacy module
from __future__ import annotations
import argparse
import json
import os
import re
from datetime import datetime
from typing import Any, Dict, List


def _load_text(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def _find_markdown_tables(md_text: str) -> List[str]:
    pattern = re.compile(r"(^\|.*\|\n\|[\s:-|]+\|[\s\S]*?(?=\n\n|\Z))", re.MULTILINE)
    return pattern.findall(md_text)


def _count_skipping_markers(md_text: str) -> int:
    return len(re.findall(r"\[SKIPPING TABLE SECTION.*?\]", md_text))


def _count_links(md_text: str) -> Dict[str, int]:
    total_urls = len(re.findall(r"https?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", md_text))
    md_links = len(re.findall(r"\[[^\]]+\]\(https?://[^)]+\)", md_text))
    emails = len(re.findall(r"\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b", md_text))
    return {"urls_total": total_urls, "md_links": md_links, "emails": emails}


def _heading_depth_distribution(md_text: str) -> Dict[str, int]:
    dist: Dict[str, int] = {}
    for line in md_text.splitlines():
        m = re.match(r"^(#{1,6})\s*(\d+(?:\.\d+)*)\b", line.strip())
        if m:
            level = len(m.group(1))
            dist[str(level)] = dist.get(str(level), 0) + 1
    return dist


def validate_tables(old_md_path: str, new_md_path: str, out_json: str | None = None) -> Dict[str, Any]:
    old_md = _load_text(old_md_path)
    new_md = _load_text(new_md_path)

    old_tables = _find_markdown_tables(old_md)
    new_tables = _find_markdown_tables(new_md)
    old_skip = _count_skipping_markers(old_md)
    new_skip = _count_skipping_markers(new_md)

    links_old = _count_links(old_md)
    links_new = _count_links(new_md)
    depth_old = _heading_depth_distribution(old_md)
    depth_new = _heading_depth_distribution(new_md)

    summary: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "old": {
            "path": old_md_path,
            "tables_found": len(old_tables),
            "skipping_markers": old_skip,
            "links": links_old,
            "heading_depth": depth_old,
        },
        "new": {
            "path": new_md_path,
            "tables_found": len(new_tables),
            "skipping_markers": new_skip,
            "links": links_new,
            "heading_depth": depth_new,
        },
        "delta": {
            "tables_found": len(new_tables) - len(old_tables),
            "skipping_markers": new_skip - old_skip,
            "links_total": links_new["urls_total"] - links_old["urls_total"],
            "md_links": links_new["md_links"] - links_old["md_links"],
            "emails": links_new["emails"] - links_old["emails"],
        },
    }

    if out_json:
        os.makedirs(os.path.dirname(out_json) or ".", exist_ok=True)
        with open(out_json, "w") as f:
            json.dump(summary, f, indent=2)

    return summary


def _cli() -> None:
    parser = argparse.ArgumentParser(description="Validate table recovery in Markdown outputs")
    parser.add_argument("--old", required=True, help="Path to old baseline markdown (with skipping markers)")
    parser.add_argument("--new", required=True, help="Path to new markdown (hybrid output)")
    parser.add_argument("--out", required=False, help="Path to save validation JSON summary")
    args = parser.parse_args()

    result = validate_tables(args.old, args.new, args.out)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    _cli()



