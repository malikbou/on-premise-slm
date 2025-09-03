import html
import re
from typing import Iterable, List, Tuple
from urllib.parse import urlparse


def _section_iter(lines: List[str]) -> Iterable[Tuple[int, int]]:
    """Yield (start_idx, end_idx_exclusive) for sections by heading boundaries."""
    n = len(lines)
    starts = [i for i, ln in enumerate(lines) if ln.lstrip().startswith("#")]
    starts.append(n)
    for i in range(len(starts) - 1):
        yield starts[i], starts[i + 1]


def remove_toc_and_index_sections(md: str) -> str:
    lines = md.splitlines()
    keep: List[str] = []
    for a, b in _section_iter(lines):
        block = lines[a:b]
        title = block[0] if block else ""
        if re.search(r"(?i)^(#+\s*)?(contents|table of contents|handbook index)\b", title.strip()):
            continue
        keep.extend(block)
    return "\n".join(keep).strip() + "\n"


def remove_sections_by_title_regex(md: str, pattern: str) -> str:
    """Remove entire sections whose heading title matches regex pattern (case-insensitive)."""
    lines = md.splitlines()
    keep: List[str] = []
    pat = re.compile(pattern, re.IGNORECASE)
    for a, b in _section_iter(lines):
        block = lines[a:b]
        title = block[0] if block else ""
        if title.strip().startswith("#") and pat.search(title):
            continue
        keep.extend(block)
    return "\n".join(keep).strip() + "\n"


def _most_common_short_lines(lines: List[str], min_repeats: int = 10, max_words: int = 7) -> List[str]:
    counts = {}
    for ln in lines:
        t = ln.strip()
        if not t:
            continue
        if len(t.split()) <= max_words:
            counts[t] = counts.get(t, 0) + 1
    return [t for t, c in counts.items() if c >= min_repeats]


def remove_repeated_headers_footers(md: str) -> str:
    lines = md.splitlines()
    common = set(_most_common_short_lines(lines))
    if not common:
        return md
    filtered = [ln for ln in lines if ln.strip() not in common]
    return "\n".join(filtered).strip() + "\n"


def normalize_heading_levels_from_numbers(md: str, base_level: int | None = None) -> str:
    lines = md.splitlines()
    # Detect minimal depth among numbered headings to calibrate base.
    depths: List[int] = []
    for ln in lines:
        if ln.lstrip().startswith("#"):
            m = re.match(r"^#+\s*(\d+(?:\.\d+)*)\b", ln.strip())
            if m:
                num = m.group(1)
                depths.append(num.count("."))
    if depths:
        min_depth = min(depths)
    else:
        min_depth = 0
    if base_level is None:
        # We want the minimal depth to map to H2
        base_level = max(1, 2 - min_depth)

    out: List[str] = []
    for ln in lines:
        if ln.lstrip().startswith("#"):
            m = re.match(r"^(#+)\s*(\d+(?:\.\d+)*)\b(.*)$", ln.strip())
            if m:
                _, num, rest = m.groups()
                depth = num.count(".")
                level = max(1, base_level + depth)
                out.append("#" * level + f" {num}{rest}")
                continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def unescape_html_entities(md: str) -> str:
    return html.unescape(md)


def append_links_from_pdf_annotations(md: str, pdf_links: List[Tuple[int, List[Tuple[str, str]]]]) -> str:
    """Append per-section External links collected per page.
    pdf_links: list of (page_number, [(text, uri), ...])
    """
    if not pdf_links:
        return md
    lines = md.splitlines()
    # Simple placement: append at end
    out: List[str] = lines + ["", "## External Links", ""]
    for page_no, items in pdf_links:
        if not items:
            continue
        out.append(f"### Page {page_no}")
        for text, uri in items:
            text_disp = (text or uri).strip()
            out.append(f"- [{text_disp}]({uri})")
        out.append("")
    return "\n".join(out).strip() + "\n"


def insert_quick_links(md: str, links: List[str], top_n: int = 20) -> str:
    if not links:
        return md
    # Remove any existing Quick Links sections to deduplicate
    md = remove_sections_by_title_regex(md, r"^#+\s*Quick Links\s*$")
    unique: List[str] = []
    seen = set()
    for u in links:
        if u not in seen:
            seen.add(u)
            unique.append(u)
        if len(unique) >= top_n:
            break
    block = ["## Quick Links", ""] + [f"- [{u}]({u})" for u in unique] + [""]
    lines = md.splitlines()
    # Insert after first main section heading if present, else after initial HTML comment, else at top
    insert_at = None
    pat_section1 = re.compile(r"^##\s*(Section\s+1\b|1[\s.])", re.IGNORECASE)
    for i, ln in enumerate(lines[:600]):
        if pat_section1.search(ln.strip()):
            insert_at = i + 1
            break
    if insert_at is None:
        insert_at = 0
        if lines and lines[0].startswith("<!--"):
            for i, ln in enumerate(lines[:50]):
                if ln.strip().endswith("-->"):
                    insert_at = i + 1
                    break
    new_lines = lines[:insert_at] + block + lines[insert_at:]
    return "\n".join(new_lines).strip() + "\n"


def add_per_section_link_summaries(md: str, max_links_per_section: int = 10) -> str:
    lines = md.splitlines()
    out: List[str] = []
    for a, b in _section_iter(lines):
        block = lines[a:b]
        if not block:
            continue
        title = block[0]
        out.extend(block)
        # Skip if already contains a Links subheading
        if any(re.match(r"^#{2,6}\s*Links\s*$", ln.strip()) for ln in block[1:]):
            continue
        # Collect URLs in section body
        urls = _re_url.findall("\n".join(block[1:]))
        # Deduplicate while preserving order
        seen = set()
        dedup: List[str] = []
        for u in urls:
            if u not in seen:
                seen.add(u)
                dedup.append(u)
            if len(dedup) >= max_links_per_section:
                break
        if dedup:
            # Determine level of the section to place a subheading one deeper (max 6)
            m = re.match(r"^(#{1,6})\s", title)
            lvl = len(m.group(1)) if m else 2
            sub_lvl = min(6, max(1, lvl + 1))
            out.append(f"{'#' * sub_lvl} Links")
            out.extend([f"- [{u}]({u})" for u in dedup])
            out.append("")
    return "\n".join(out).strip() + "\n"


def _replace_first_hostname_with_link(text: str, url: str) -> tuple[str, bool]:
    host = urlparse(url).netloc
    if not host:
        return text, False
    idx = text.find(host)
    if idx == -1:
        return text, False
    # Replace only the first occurrence
    before = text[:idx]
    after = text[idx + len(host):]
    return before + f"[{host}]({url})" + after, True


def inline_links_from_section_summaries(md: str, per_section_limit: int = 3) -> str:
    """Convert per-section 'Links' lists into inline links within the same section.
    Strategy: for each URL, try to find its hostname in the section body and link it.
    If not found, append a small inline '↗' link to the section heading.
    Then remove the 'Links' subheading block.
    """
    lines = md.splitlines()
    out: List[str] = []
    i = 0
    n = len(lines)
    while i < n:
        # Find next section
        start = i
        while start < n and not lines[start].lstrip().startswith('#'):
            out.append(lines[start])
            start += 1
        if start >= n:
            break
        # Find section end
        end = start + 1
        while end < n and not lines[end].lstrip().startswith('#'):
            end += 1
        block = lines[start:end]
        title = block[0]
        body = block[1:]

        # Locate a 'Links' subheading inside body
        link_sub_idx = None
        for j, ln in enumerate(body):
            if re.match(r"^#{2,6}\s*Links\s*$", ln.strip()):
                link_sub_idx = j
                break

        urls: List[str] = []
        if link_sub_idx is not None:
            # Collect list items after 'Links' until blank line or next heading
            k = link_sub_idx + 1
            while k < len(body):
                ln = body[k]
                if not ln.strip():
                    k += 1
                    break
                if ln.lstrip().startswith('#'):
                    break
                m = re.search(r"\((https?://[^)]+)\)", ln)
                if m:
                    urls.append(m.group(1))
                k += 1
            # Remove the Links block
            body = body[:link_sub_idx] + body[k:]

        # Try inline insertions for a limited number of URLs
        inserted = 0
        if urls:
            new_body: List[str] = []
            for ln in body:
                if inserted >= per_section_limit:
                    new_body.append(ln)
                    continue
                for u in list(urls):
                    if inserted >= per_section_limit:
                        break
                    ln2, ok = _replace_first_hostname_with_link(ln, u)
                    if ok:
                        ln = ln2
                        urls.remove(u)
                        inserted += 1
                new_body.append(ln)
            body = new_body

        # If some URLs remain, append tiny inline markers to the title
        if urls:
            markers = " ".join([f"[↗]({u})" for u in urls[:per_section_limit - inserted] if u])
            if markers:
                title = title + " " + markers

        out.append(title)
        out.extend(body)
        i = end

    # Append the rest (if any trailing lines after last section)
    while i < n:
        out.append(lines[i])
        i += 1
    return "\n".join(out).strip() + "\n"


def trim_before_first_main_section(md: str) -> str:
    """Trim everything before the first main numbered section heading (e.g., '## 1' or '## Section 1')."""
    lines = md.splitlines()
    start_idx = 0
    pat = re.compile(r"^#{2,}\s*(Section\s+1\b|1[\s.])", re.IGNORECASE)
    for i, ln in enumerate(lines[:500]):  # look near the top
        if pat.search(ln.strip()):
            start_idx = i
            break
    return "\n".join(lines[start_idx:]).strip() + "\n"


def postprocess_markdown(
    md: str,
    *,
    drop_toc_and_index: bool = True,
    drop_repeated_headers: bool = True,
    normalize_headings: bool = True,
    html_unescape: bool = True,
) -> str:
    if drop_toc_and_index:
        md = remove_toc_and_index_sections(md)
    if drop_repeated_headers:
        md = remove_repeated_headers_footers(md)
    if normalize_headings:
        md = normalize_heading_levels_from_numbers(md)
    if html_unescape:
        md = unescape_html_entities(md)
    return md


# --- Additional passes: stronger noise removal and autolinking ---

_re_page_line = re.compile(r"^(page\s*\d+(\s*of\s*\d+)?)$", re.IGNORECASE)
_re_digits_only = re.compile(r"^\d{1,4}$")


def remove_additional_noise(md: str) -> str:
    out: List[str] = []
    for ln in md.splitlines():
        t = ln.strip()
        if not t:
            out.append(ln)
            continue
        if _re_page_line.match(t):
            continue
        if _re_digits_only.match(t):
            continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"


_re_url = re.compile(r"(?<!\]\()\bhttps?://[\w\-._~:/?#\[\]@!$&'()*+,;=%]+", re.IGNORECASE)
_re_email = re.compile(r"(?<!\]\()\b[A-Za-z0-9._%+-]+@(?:[A-Za-z0-9-]+\.)+[A-Za-z]{2,}\b")


def autolink_emails_and_urls(md: str) -> str:
    lines = md.splitlines()
    out: List[str] = []
    in_code = False
    for ln in lines:
        s = ln
        stripped = s.strip()
        if stripped.startswith("```"):
            in_code = not in_code
            out.append(s)
            continue
        if in_code:
            out.append(s)
            continue
        if s.lstrip().startswith("|"):
            # Avoid altering tables for now
            out.append(s)
            continue
        # Autolink URLs not already in markdown link syntax
        s = _re_url.sub(lambda m: f"[{m.group(0)}]({m.group(0)})", s)
        # Autolink emails
        s = _re_email.sub(lambda m: f"[{m.group(0)}](mailto:{m.group(0)})", s)
        out.append(s)
    return "\n".join(out).strip() + "\n"



