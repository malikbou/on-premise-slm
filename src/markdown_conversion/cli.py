import argparse
import json
from pathlib import Path
from .pipeline import run as pipeline_run
from .validate import validate_tables
from .repair_with_openai import run as repair_run
from .repair_one_shot import run as one_shot_run
from .repair_from_pdf import main as pdf_one_shot_main


def main():
    parser = argparse.ArgumentParser(description="Markdown Conversion CLI")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_convert = sub.add_parser("convert", help="Convert PDF to Markdown")
    p_convert.add_argument("--input", required=True, help="Path to input PDF")
    p_convert.add_argument("--output", required=True, help="Path to output Markdown")
    p_convert.add_argument("--save-metrics", action="store_true", help="Save metrics JSON next to output")

    p_validate = sub.add_parser("validate", help="Validate table/link/heading metrics between two markdown files")
    p_validate.add_argument("--old", required=True, help="Path to old baseline markdown")
    p_validate.add_argument("--new", required=True, help="Path to new markdown")
    p_validate.add_argument("--out", required=False, help="Path to save validation JSON summary")

    p_repair = sub.add_parser("repair", help="Repair Markdown using OpenAI and pdf_links.csv")
    p_repair.add_argument("--links", required=True, help="Path to pdf_links.csv (from dump_pdf_links.py)")
    p_repair.add_argument("--in-md", required=True, help="Path to input Markdown to repair")
    p_repair.add_argument("--out-md", required=True, help="Path to write the repaired Markdown")
    p_repair.add_argument("--model", default="gpt-4o-mini", help="OpenAI model name")
    p_repair.add_argument("--pages", action="append", help="Optional page ranges (e.g., 12-25). Repeatable.")
    p_repair.add_argument("--max-tokens", type=int, default=2000)
    p_repair.add_argument("--delay-s", type=float, default=0.0)
    p_repair.add_argument("--dry-run", action="store_true")
    p_repair.add_argument("--max-slice-tokens", type=int, default=3000, help="Approximate token budget per markdown slice before calling the model")
    p_repair.add_argument("--concurrency", type=int, default=4, help="Number of slices to process in parallel")
    p_repair.add_argument("--timeout-s", type=float, default=60.0, help="Per-request client timeout in seconds")
    p_repair.add_argument("--simple", action="store_true", help="Use a simpler system prompt for GPT-5-mini with minimal reasoning, low verbosity")
    p_repair.add_argument("--no-csv", action="store_true", help="Do not include PDF link CSV; let the model infer links")

    p_one = sub.add_parser("repair-one-shot", help="One-shot repair (no chunking) with Responses API")
    p_pdf = sub.add_parser("repair-from-pdf", help="Vision one-shot: PDF → Markdown with Responses API")
    p_pdf.add_argument("--pdf", required=True, help="Path to input PDF")
    p_pdf.add_argument("--out", required=True, help="Path to write the repaired Markdown")
    p_pdf.add_argument("--model", default="gpt-4o-mini", help="Vision-capable model")
    p_pdf.add_argument("--in-md", default="", help="Optional Docling Markdown context for the same document")
    p_pdf.add_argument("--max-tokens", type=int, default=0, help="Max completion tokens; 0 omits the limit")
    p_one.add_argument("--in-md", required=True, help="Path to input Markdown to repair")
    p_one.add_argument("--csv", required=False, default="", help="Optional pdf_links.csv to include as context")
    p_one.add_argument("--out", required=True, help="Path to write the repaired Markdown")
    p_one.add_argument("--model", default="gpt-5-mini", help="OpenAI model name")
    p_one.add_argument("--max-tokens", type=int, default=0, help="Max completion tokens; 0 omits the limit")
    p_one.add_argument("--fail-on-missing", action="store_true", help="Exit non-zero if table cells likely missing links")

    args = parser.parse_args()

    if args.cmd == "convert":
        res = pipeline_run(args.input, args.output)
        print(json.dumps(res, indent=2))
        if args.save_metrics:
            metrics_path = args.output.rsplit(".", 1)[0] + "__metrics.json"
            with open(metrics_path, "w") as f:
                json.dump(res, f, indent=2)
            print(f"Saved metrics to {metrics_path}")
    elif args.cmd == "validate":
        result = validate_tables(args.old, args.new, args.out)
        print(json.dumps(result, indent=2))
    elif args.cmd == "repair":
        page_ranges = []
        if args.pages:
            def _parse_pages(values):
                out = []
                for v in values:
                    if "-" in v:
                        a, b = v.split("-", 1)
                        out.append((int(a), int(b)))
                    else:
                        p = int(v)
                        out.append((p, p))
                return out
            page_ranges = _parse_pages(args.pages)
        # The 'simple' flag is interpreted inside repair_with_openai via prompt choice; pass no_csv explicitly
        repair_run(
            Path(args.links), Path(args.in_md), Path(args.out_md), args.model,
            page_ranges, args.max_tokens, args.delay_s, args.dry_run,
            max_slice_tokens=args.max_slice_tokens, concurrency=args.concurrency,
            timeout_s=args.timeout_s, no_csv=args.no_csv
        )
    elif args.cmd == "repair-one-shot":
        one_shot_run(
            str(Path(args.in_md)),
            str(Path(args.out)),
            args.model,
            str(Path(args.csv)) if args.csv else "",
            args.max_tokens,
            args.fail_on_missing,
        )
    elif args.cmd == "repair-from-pdf":
        # Reuse the module's main to keep arg handling consistent
        pdf_one_shot_main()


if __name__ == "__main__":
    main()
