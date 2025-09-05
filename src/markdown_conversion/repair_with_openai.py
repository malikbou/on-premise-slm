import argparse
import csv
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import tiktoken  # optional
except Exception:
    tiktoken = None  # type: ignore

from dotenv import load_dotenv
from openai import OpenAI, BadRequestError

from .prompt_templates import SYSTEM_PROMPT, USER_PROMPT_TEMPLATE, SIMPLE_SYSTEM_PROMPT


# --------- Utilities ---------
BAD_LINK_PATTERNS: List[Tuple[re.Pattern[str], str]] = [
    (re.compile(r"https://\[https"), "https://"),
    (re.compile(r"\]\]\("), "]("),
    (re.compile(r"\)\)\]"), ")"),
]


def read_file(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="ignore")


def write_file(p: Path, s: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")


def load_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        r = csv.DictReader(f)
        for row in r:
            rows.append(row)
    return rows


def filter_csv_by_page(rows: List[Dict[str, str]], start: int, end: int) -> List[Dict[str, str]]:
    def _safe_int(x: Any, default: int = 0) -> int:
        try:
            return int(x)
        except Exception:
            return default
    return [r for r in rows if start <= _safe_int(r.get("page", 0)) <= end]


def csv_to_string(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return ""
    cols = ["page", "x0", "y0", "x1", "y1", "uri", "text"]
    out = [",".join(cols)]
    for r in rows:
        vals = [str(r.get(c, "")) for c in cols]
        vals = [v.replace("\n", " ").replace("\r", " ").replace(",", " ") for v in vals]
        out.append(",".join(vals))
    return "\n".join(out)


HEADING_SPLIT_H12 = re.compile(r"(?m)^(?=#{1,2}\s)")
HEADING_SPLIT_H3 = re.compile(r"(?m)^(?=###\s)")
HEADING_SPLIT_H4 = re.compile(r"(?m)^(?=####\s)")


def _split_keep_heads(text: str, pattern: re.Pattern[str]) -> List[str]:
    return [p for p in pattern.split(text) if p.strip()]


def _chunk_by_chars(text: str, max_chars: int) -> List[str]:
    if len(text) <= max_chars:
        return [text]
    out: List[str] = []
    i = 0
    n = len(text)
    while i < n:
        j = min(n, i + max_chars)
        out.append(text[i:j])
        i = j
    return out


def chunk_markdown(md: str, max_slice_tokens: int) -> List[str]:
    # First, split on # / ##
    coarse = _split_keep_heads(md, HEADING_SPLIT_H12)
    slices: List[str] = []
    for block in coarse:
        if approx_token_count(block) <= max_slice_tokens:
            slices.append(block)
            continue
        # Try splitting on ###
        parts3 = _split_keep_heads(block, HEADING_SPLIT_H3)
        if len(parts3) > 1:
            for p3 in parts3:
                if approx_token_count(p3) <= max_slice_tokens:
                    slices.append(p3)
                else:
                    # Try splitting on ####
                    parts4 = _split_keep_heads(p3, HEADING_SPLIT_H4)
                    if len(parts4) > 1:
                        for p4 in parts4:
                            if approx_token_count(p4) <= max_slice_tokens:
                                slices.append(p4)
                            else:
                                # Fallback: paragraph/char-based
                                target_chars = max(1000, max_slice_tokens * 4)
                                slices.extend(_chunk_by_chars(p4, target_chars))
                    else:
                        target_chars = max(1000, max_slice_tokens * 4)
                        slices.extend(_chunk_by_chars(p3, target_chars))
        else:
            target_chars = max(1000, max_slice_tokens * 4)
            slices.extend(_chunk_by_chars(block, target_chars))
    return slices


def approx_token_count(s: str) -> int:
    if tiktoken is not None:  # type: ignore
        try:
            enc = tiktoken.get_encoding("cl100k_base")  # type: ignore
            return len(enc.encode(s))
        except Exception:
            pass
    return max(1, len(s.split()))


def apply_simple_sanity_fixes(s: str) -> str:
    for pat, repl in BAD_LINK_PATTERNS:
        s = pat.sub(repl, s)
    return s


# --------- OpenAI Call ---------
def call_openai(client: OpenAI, model: str, system_prompt: str, user_prompt: str, *, max_tokens: int = 2000, temperature: float = 0.0, reasoning_effort: str | None = None, verbosity: str | None = None) -> str:
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]

    def _clean(d: Dict[str, Any]) -> Dict[str, Any]:
        return {k: v for k, v in d.items() if v is not None}

    attempts: List[Dict[str, Any]] = []
    # Normalize max tokens: treat 0/None as unset
    max_tok = max_tokens if (isinstance(max_tokens, int) and max_tokens and max_tokens > 0) else None
    # 1) With max_tokens + temperature
    attempts.append(_clean({"model": model, "messages": messages, "temperature": temperature, "max_tokens": max_tok}))
    # 2) With temperature only
    attempts.append(_clean({"model": model, "messages": messages, "temperature": temperature}))
    # 3) With max_completion_tokens + temperature
    attempts.append(_clean({"model": model, "messages": messages, "temperature": temperature, "max_completion_tokens": max_tok}))
    # 4) With neither (defaults)
    attempts.append(_clean({"model": model, "messages": messages}))
    # 5) With max_completion_tokens only
    attempts.append(_clean({"model": model, "messages": messages, "max_completion_tokens": max_tok}))

    # GPT-5 Responses API style parameters (some SDKs support passing on chat.create transparently)
    if reasoning_effort or verbosity:
        attempts.insert(0, _clean({
            "model": model,
            "messages": messages,
            "reasoning": {"effort": reasoning_effort} if reasoning_effort else None,
            "text": {"verbosity": verbosity} if verbosity else None,
        }))

    last_err: Exception | None = None
    for kwargs in attempts:
        try:
            resp = client.chat.completions.create(**kwargs)
            return resp.choices[0].message.content or ""
        except BadRequestError as e:
            msg = str(e).lower()
            # If temperature unsupported, drop it and continue to next
            if "temperature" in msg:
                # remove temperature in-place for subsequent attempts
                for k in ("temperature",):
                    if k in kwargs:
                        kwargs.pop(k, None)
                try:
                    resp = client.chat.completions.create(**kwargs)
                    return resp.choices[0].message.content or ""
                except BadRequestError as e2:
                    last_err = e2
                    continue
            last_err = e
            continue
        except Exception as e:
            last_err = e
            continue
    if last_err:
        raise last_err
    raise RuntimeError("OpenAI call failed with unknown error.")


# --------- Main Flow ---------
def run(
    pdf_links_csv: Path,
    in_md: Path,
    out_md: Path,
    model: str,
    page_ranges: List[Tuple[int, int]],
    max_tokens: int,
    delay_s: float,
    dry_run: bool,
    token_budget: int = 12000,
    max_slice_tokens: int = 3000,
    concurrency: int = 4,
    timeout_s: float = 60.0,
    no_csv: bool = False,
) -> None:
    # Load environment variables (e.g., OPENAI_API_KEY) like generate_testset.py
    load_dotenv()

    client: OpenAI | None = None
    if not dry_run:
        client = OpenAI(timeout=timeout_s)
    base_md = read_file(in_md)
    rows = load_csv(pdf_links_csv)

    slices = chunk_markdown(base_md, max_slice_tokens)
    repaired_slices: List[str] = []

    if rows:
        min_page = min(int(r.get("page", 1)) for r in rows if str(r.get("page", "")).isdigit())
        max_page = max(int(r.get("page", 1)) for r in rows if str(r.get("page", "")).isdigit())
    else:
        min_page, max_page = 1, 9999

    ranges = page_ranges if page_ranges else [(min_page, max_page)]

    total = len(slices)
    print(f"Total slices: {total}; concurrency={concurrency}; token_budget={token_budget}; max_slice_tokens={max_slice_tokens}")

    def _process_one(idx: int, sl: str) -> Tuple[int, str]:
        t0 = time.time()
        rng = ranges[min(idx - 1, len(ranges) - 1)]
        csv_subset = [] if no_csv else filter_csv_by_page(rows, rng[0], rng[1])
        user_prompt = USER_PROMPT_TEMPLATE.format(
            markdown_slice=sl.strip(),
            csv_subset=csv_to_string(csv_subset),
        )
        # If GPT-5-mini specified, optionally switch to simpler system prompt for speed
        system_prompt = SIMPLE_SYSTEM_PROMPT if ("gpt-5" in model and "mini" in model) else SYSTEM_PROMPT
        # Token budget guard: reduce CSV if too large
        while approx_token_count(user_prompt) > token_budget and len(csv_subset) > 0:
            csv_subset = csv_subset[: max(1, len(csv_subset) // 2)]
            user_prompt = USER_PROMPT_TEMPLATE.format(
                markdown_slice=sl.strip(),
                csv_subset=csv_to_string(csv_subset),
            )
        print(f"[{idx}/{total}] tokens~{approx_token_count(user_prompt)} csv_rows={len(csv_subset)} pages={rng[0]}-{rng[1]}")

        if dry_run:
            cleaned = apply_simple_sanity_fixes(sl)
            dt = time.time() - t0
            print(f"[{idx}/{total}] dry-run done in {dt:.2f}s")
            return idx, cleaned

        backoff = 1.0
        out_text = ""
        for attempt in range(5):
            try:
                assert client is not None
                out_text = call_openai(client, model, system_prompt, user_prompt, max_tokens=max_tokens, temperature=0.0, reasoning_effort="minimal", verbosity="low")
                break
            except Exception as e:
                if attempt == 4:
                    raise
                time.sleep(backoff)
                backoff *= 2
        in_tok = approx_token_count(sl)
        out_tok = approx_token_count(out_text)
        if out_tok < max(200, int(0.6 * in_tok)):
            cleaned = apply_simple_sanity_fixes(sl)
            note = "(fallback original)"
        else:
            cleaned = apply_simple_sanity_fixes(out_text)
            note = ""
        dt = time.time() - t0
        print(f"[{idx}/{total}] done in {dt:.2f}s out_tokens~{out_tok} {note}")
        if delay_s > 0:
            time.sleep(delay_s)
        return idx, cleaned

    # Process slices (parallel for real run)
    results: List[Tuple[int, str]] = []
    if dry_run or concurrency <= 1:
        for i, sl in enumerate(slices, 1):
            results.append(_process_one(i, sl))
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as ex:
            futures = {ex.submit(_process_one, i, sl): i for i, sl in enumerate(slices, 1)}
            for fut in as_completed(futures):
                results.append(fut.result())
        # Sort by original index
        results.sort(key=lambda x: x[0])

    repaired_slices = [text for _, text in results]

    final_md = "\n\n".join(repaired_slices).strip()
    write_file(out_md, final_md)
    print(f"Wrote repaired Markdown -> {out_md}")


def parse_pages(values: List[str]) -> List[Tuple[int, int]]:
    out: List[Tuple[int, int]] = []
    for v in values:
        if "-" in v:
            a, b = v.split("-", 1)
            out.append((int(a), int(b)))
        else:
            p = int(v)
            out.append((p, p))
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Repair Markdown using OpenAI + PDF link dump.")
    ap.add_argument("--links", required=True, type=Path, help="Path to pdf_links.csv (from dump_pdf_links.py).")
    ap.add_argument("--in-md", required=True, type=Path, help="Path to input Markdown to repair.")
    ap.add_argument("--out-md", required=True, type=Path, help="Path to write the repaired Markdown.")
    ap.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name.")
    ap.add_argument("--pages", action="append", help="Optional page ranges to pass with each slice (e.g., 12-25). Repeatable.")
    ap.add_argument("--max-tokens", type=int, default=2000)
    ap.add_argument("--delay-s", type=float, default=0.0, help="Sleep between API calls to smooth rate limits.")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    page_ranges = parse_pages(args.pages) if args.pages else []
    run(args.links, args.in_md, args.out_md, args.model, page_ranges, args.max_tokens, args.delay_s, args.dry_run)


if __name__ == "__main__":
    main()
