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
    min_depth = min(depths) if depths else 0
    if base_level is None:
        # Map minimal depth to H2 (## x)
        base_level = max(1, 2 - min_depth)

    out: List[str] = []
    current_number_stack: list[int] = []
    current_number_level: int | None = None
    for ln in lines:
        raw = ln
        if ln.lstrip().startswith("#"):
            m_num = re.match(r"^(#+)\s*(\d+(?:\.\d+)*)\b(.*)$", ln.strip())
            if m_num:
                _, num, rest = m_num.groups()
                depth = num.count(".")
                level = max(1, base_level + depth)
                out.append("#" * level + f" {num}{rest}")
                current_number_stack = [int(x) for x in num.split('.')]
                current_number_level = level
                continue
            # Unnumbered heading following a numbered context: demote to be a child
            m_head = re.match(r"^(#{1,6})\s+(.*)$", ln.strip())
            if m_head and current_number_stack and current_number_level is not None:
                _, title = m_head.groups()
                # Force as child of the numeric parent (parent level + 1)
                level = min(6, current_number_level + 1)
                out.append("#" * level + f" {title}")
                continue
        # Reset stack if a blank line or non-heading content persists for long? Keep simple: retain
        out.append(raw)
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
    """Trim everything before the first main section. Prefer numeric '## 1' over '## Section 1'."""
    lines = md.splitlines()
    start_idx = 0
    # Prefer numeric section heading if present near top
    pat_numeric = re.compile(r"^#{2,}\s*1[\s.]", re.IGNORECASE)
    pat_textual = re.compile(r"^#{2,}\s*Section\s+1\b", re.IGNORECASE)
    found = None
    for i, ln in enumerate(lines[:800]):
        if pat_numeric.search(ln.strip()):
            found = i
            break
    if found is None:
        for i, ln in enumerate(lines[:800]):
            if pat_textual.search(ln.strip()):
                found = i
                break
    if found is not None:
        start_idx = found
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
_re_bare_domain = re.compile(
    r"(?<!\]\()(?:\bwww\.[^\s)]+|\b[A-Za-z0-9.-]*ucl\.ac\.uk[^\s)]*)",
    re.IGNORECASE,
)


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
        # Autolink common bare domains (no scheme). Prefer https.
        def _link_bare(m: re.Match[str]) -> str:
            u = m.group(0)
            # Skip if already inside a markdown link (handled by negative lookbehind), or contains scheme
            if u.lower().startswith("http://") or u.lower().startswith("https://"):
                return u
            # Normalize leading 'www.' case
            if u.lower().startswith('www.'):
                return f"[{'https://' + u}]({'https://' + u})"
            # Known domain family: ucl.ac.uk and subdomains
            if 'ucl.ac.uk' in u.lower():
                return f"[{u}](https://{u})"
            return u
        s = _re_bare_domain.sub(_link_bare, s)
        # Autolink emails
        s = _re_email.sub(lambda m: f"[{m.group(0)}](mailto:{m.group(0)})", s)
        out.append(s)
    return "\n".join(out).strip() + "\n"




# --- Table utilities and advanced cleanup ---

_re_table_block = re.compile(r"(^\|.*\|\n\|[\s:\-|]+\|[\s\S]*?(?=\n\n|\Z))", re.MULTILINE)


def count_markdown_tables(md_text: str) -> int:
    """Return the number of GitHub-flavored Markdown tables detected in the text."""
    return len(_re_table_block.findall(md_text))


def _normalize_table_block(table_block: str) -> str:
    """Normalize a single markdown table block: trim cells, ensure header delimiter, drop blank rows."""
    lines = [ln.rstrip() for ln in table_block.splitlines() if ln.strip()]
    if not lines:
        return table_block
    # Ensure at least header and delimiter rows exist
    if len(lines) == 1:
        # Single row -> synthesize delimiter based on columns
        cols = [c.strip() for c in lines[0].strip().strip('|').split('|')]
        delim = '| ' + ' | '.join(['---' for _ in cols]) + ' |'
        lines.insert(1, delim)
    # Split to cells and trim
    def split_row(row: str) -> list[str]:
        inner = row.strip().strip('|')
        return [c.strip() for c in inner.split('|')]

    rows = [split_row(ln) for ln in lines]
    # Compute max width from header
    width = len(rows[0]) if rows else 0
    # Ensure delimiter row present at index 1
    if len(rows) >= 2:
        if not all(set(c) <= {'-', ':', ' '} and len(c) >= 3 for c in rows[1]):
            rows.insert(1, ['---' for _ in range(width)])
    # Remove fully empty data rows
    def is_blank_row(cells: list[str]) -> bool:
        return all(not c for c in cells)

    header = rows[0]
    delim = rows[1] if len(rows) > 1 else ['---' for _ in range(width)]
    data = [r for r in rows[2:] if not is_blank_row(r)]
    # Rebuild with consistent spacing
    out_lines: list[str] = []
    out_lines.append('| ' + ' | '.join(header) + ' |')
    out_lines.append('| ' + ' | '.join(['---' if not d else d for d in delim]) + ' |')
    for r in data:
        # Pad/truncate row to header width
        cells = (r + [''] * width)[:width]
        out_lines.append('| ' + ' | '.join(cells) + ' |')
    return "\n".join(out_lines)


def normalize_tables(md: str) -> str:
    """Normalize all markdown tables found in the document."""
    def _repl(m: re.Match[str]) -> str:
        return _normalize_table_block(m.group(1))

    return _re_table_block.sub(_repl, md).strip() + "\n"


def deduplicate_tables(md: str) -> str:
    """Remove duplicate tables by normalized signature (first rows + width). Keeps first occurrence."""
    tables = list(_re_table_block.finditer(md))
    seen: set[str] = set()
    keep_mask = [True] * len(tables)

    def signature(block: str) -> str:
        norm = _normalize_table_block(block)
        # Build a compact signature using first 3 rows and number of columns
        rows = [ln.strip() for ln in norm.splitlines()]
        head = rows[:3]
        width = len(rows[0].strip('|').split('|')) if rows else 0
        return f"{width}|" + '\n'.join(head)

    for idx, m in enumerate(tables):
        sig = signature(m.group(1))
        if sig in seen:
            keep_mask[idx] = False
        else:
            seen.add(sig)

    # Rebuild document without duplicates
    out_parts: list[str] = []
    last_end = 0
    for (m, keep) in zip(tables, keep_mask):
        out_parts.append(md[last_end:m.start()])
        if keep:
            out_parts.append(m.group(1))
        last_end = m.end()
    out_parts.append(md[last_end:])
    return ''.join(out_parts).strip() + "\n"


def clean_symbols(md: str) -> str:
    """Remove extraction artifacts such as checkmarks/crosses and normalize dashes/quotes."""
    s = md
    # Remove common glyphs
    s = s.replace('✓', '').replace('✗', '')
    # Normalize en/em dashes to hyphen
    s = s.replace('—', '-').replace('–', '-')
    # Normalize fancy quotes
    s = s.replace('“', '"').replace('”', '"').replace('’', "'")
    return s


def deduplicate_headings(md: str) -> str:
    """Detect duplicate headings and suffix subsequent duplicates with (n)."""
    lines = md.splitlines()
    seen: dict[str, int] = {}
    out: list[str] = []
    for ln in lines:
        t = ln.strip()
        if t.startswith('#'):
            # Extract heading text without leading #'s and surrounding spaces
            m = re.match(r"^(#{1,6})\s*(.*)$", t)
            if m:
                hashes, title = m.groups()
                count = seen.get(title, 0) + 1
                seen[title] = count
                if count > 1:
                    title = f"{title} ({count})"
                out.append(f"{hashes} {title}")
                continue
        out.append(ln)
    return "\n".join(out).strip() + "\n"


def reflow_paragraphs(md: str) -> str:
    """Conservatively unwrap paragraphs: keep code blocks, tables, lists, headings intact."""
    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        stripped = ln.strip()
        # Toggle code block state
        if stripped.startswith('```'):
            in_code = not in_code
            out.append(ln)
            i += 1
            continue
        if in_code or stripped.startswith('|'):
            out.append(ln)
            i += 1
            continue
        # Block starts: headings, lists, blockquotes
        if stripped.startswith('#') or stripped.startswith(('-', '*', '+')) or re.match(r"^\d+\.\s", stripped) or stripped.startswith('>'):
            out.append(ln)
            i += 1
            continue
        # Gather paragraph lines until blank or next block
        if stripped:
            para: list[str] = [stripped]
            j = i + 1
            while j < n:
                nxt = lines[j].strip()
                if not nxt:
                    break
                if nxt.startswith('#') or nxt.startswith('|') or nxt.startswith('```') or nxt.startswith(('-', '*', '+')) or re.match(r"^\d+\.\s", nxt) or nxt.startswith('>'):
                    break
                para.append(nxt)
                j += 1
            out.append(' '.join(para))
            i = j
            continue
        # Preserve blank lines
        out.append(ln)
        i += 1
    return "\n".join(out).strip() + "\n"


# --- Navigation bloat removal and link quality improvements ---

_pat_nav_section_titles = re.compile(
    r"^#{2,}\s*(Quick Links|College resources|Support for extenuating circumstances)\s*$",
    re.IGNORECASE,
)


def remove_navigation_cruft_and_bloat(md: str) -> str:
    """Remove known navigation sections (Quick Links, College resources, Support...) anywhere in doc.
    This specifically targets high-level nav blocks that clutter the beginning.
    """
    lines = md.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)
    while i < n:
        ln = lines[i]
        if _pat_nav_section_titles.match(ln.strip()):
            # Skip until next heading or end
            i += 1
            while i < n and not lines[i].lstrip().startswith('#'):
                i += 1
            continue
        out.append(ln)
        i += 1
    return "\n".join(out).strip() + "\n"


_pat_double_link_trailer = re.compile(r"\]\((https?://[^)]+)\)\]\([^)]*\)")


def fix_malformed_double_links(md: str) -> str:
    """Fix common double-bracketed link artifacts like [text](url)](url](url))."""
    prev = None
    cur = md
    # Apply a few passes to stabilize
    for _ in range(3):
        prev = cur
        cur = _pat_double_link_trailer.sub(r"](\1)", prev)
        if cur == prev:
            break
    return cur


_pat_mdlink_with_url_label = re.compile(r"\[(https?://[^\]]+)\]\((https?://[^)]+)\)")


def _describe_url(url: str) -> str:
    try:
        from urllib.parse import urlparse
        u = urlparse(url)
        host = (u.netloc or '').lower()
        path = (u.path or '').strip('/').lower()
        if 'academic-manual' in host or 'academic-manual' in path:
            # Try to extract chapter/section
            m = re.search(r"chapter[-/](\d+).*section[-/]([0-9.]+)", path)
            if m:
                ch, sec = m.groups()
                return f"UCL Academic Manual Chapter {ch}, Section {sec}"
            return "UCL Academic Manual"
        if 'module-catalogue' in host or 'module-catalogue' in path:
            return "UCL Module Catalogue"
        if host.endswith('ucl.ac.uk'):
            return "UCL website"
        return host or url
    except Exception:
        return url


def improve_url_display_text(md: str) -> str:
    """Replace visible URL labels with descriptive text for known domains."""
    def _repl(m: re.Match[str]) -> str:
        label, href = m.group(1), m.group(2)
        if label == href:
            return f"[{_describe_url(href)}]({href})"
        return m.group(0)

    return _pat_mdlink_with_url_label.sub(_repl, md)


_pat_academic_manual_ref = re.compile(
    r"\bAcademic Manual\s*(?:Chapter|Ch\.)\s*(\d+)\s*,?\s*(?:Section|Sec\.)\s*([0-9]+(?:\.[0-9]+)*)",
    re.IGNORECASE,
)


def create_authentic_inline_links(md: str, annotations: list[str] | None = None) -> str:
    """Link real text references to canonical URLs. Skips code blocks and tables.
    Currently supports Academic Manual Chapter/Section references.
    If annotations contain academic-manual URLs, prefer those specific URLs.
    """
    annot_manual_urls: list[str] = []
    for u in (annotations or []):
        if 'academic-manual' in u:
            annot_manual_urls.append(u)

    def pick_specific_manual_url(ch: str, sec: str) -> str | None:
        # Try to find a matching annotation URL
        for u in annot_manual_urls:
            if f"chapter-{ch}" in u.lower() and f"section-{sec}" in u.lower():
                return u
        return None

    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    for ln in lines:
        s = ln
        t = s.strip()
        if t.startswith('```'):
            in_code = not in_code
            out.append(s)
            continue
        if in_code or s.lstrip().startswith('|'):
            out.append(s)
            continue
        # Replace textual references only if not already inside a link
        def _repl(m: re.Match[str]) -> str:
            ch, sec = m.group(1), m.group(2)
            url = pick_specific_manual_url(ch, sec) or f"https://www.ucl.ac.uk/academic-manual/chapter-{ch}/section-{sec}"
            text = f"Academic Manual Chapter {ch}, Section {sec}"
            return f"[{text}]({url})"

        s2 = _pat_academic_manual_ref.sub(_repl, s)
        out.append(s2)
    return "\n".join(out).strip() + "\n"


def inline_annotations_by_keyword(md: str, annotations: list[str] | None = None) -> str:
    """Inline links by matching known keywords to actual annotation URLs.
    Ensures links are authentic by only using URLs present in the PDF annotations.
    Currently supports: Academic Manual, Module Catalogue.
    """
    urls = annotations or []
    manu = next((u for u in urls if 'academic-manual' in u.lower()), None)
    module = next((u for u in urls if 'module-catalogue' in u.lower()), None)
    if not manu and not module:
        return md

    def already_linked(s: str, keyword: str) -> bool:
        # If keyword appears inside an existing markdown link label
        return f'[{keyword}](' in s

    lines = md.splitlines()
    out: list[str] = []
    in_code = False
    for ln in lines:
        s = ln
        t = s.strip()
        if t.startswith('```'):
            in_code = not in_code
            out.append(s)
            continue
        if in_code or s.lstrip().startswith('|'):
            out.append(s)
            continue
        if manu and 'Academic Manual' in s and not already_linked(s, 'Academic Manual'):
            s = s.replace('Academic Manual', f'[Academic Manual]({manu})', 1)
        if module and 'Module Catalogue' in s and not already_linked(s, 'Module Catalogue'):
            s = s.replace('Module Catalogue', f'[Module Catalogue]({module})', 1)
        out.append(s)
    return "\n".join(out).strip() + "\n"

