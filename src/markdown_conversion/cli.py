import argparse
import json
from .pipeline import run as pipeline_run
from .validate import validate_tables


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


if __name__ == "__main__":
    main()


