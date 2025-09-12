#!/usr/bin/env python3
"""
Mirror the installed `ragas` package source into `vendor/ragas` so Cursor can index it.

Usage:
  python scripts/vendor_ragas.py [--dest vendor/ragas] [--source <path>] [--include-tests] [--verbose]

Notes:
  - By default, finds the installed `ragas` package via importlib and copies its source tree.
  - The vendor copy is for code reading by the Agent; project imports should still use `import ragas`.
"""

from __future__ import annotations

import argparse
import importlib.util
import os
import shutil
import sys
from pathlib import Path


def find_ragas_source(provided_source: str | None = None) -> Path:
    if provided_source:
        src = Path(provided_source).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"Provided ragas source path does not exist: {src}")
        return src

    spec = importlib.util.find_spec("ragas")
    if spec is None or not spec.submodule_search_locations:
        raise ModuleNotFoundError(
            "Could not locate installed 'ragas'. Ensure it is installed in the current environment."
        )
    # The first location should be the package directory
    return Path(list(spec.submodule_search_locations)[0]).resolve()


def copy_ragas_source(src: Path, dest: Path, include_tests: bool, verbose: bool) -> None:
    if dest.exists():
        if verbose:
            print(f"Removing existing destination: {dest}")
        shutil.rmtree(dest)

    ignore_patterns = [
        "__pycache__",
        "*.pyc",
        "*.pyo",
        "*.so",
        "*.dylib",
        "*.ipynb_checkpoints",
        "node_modules",
        "dist",
        "build",
        "*.egg-info",
        "site-packages",
        "tests" if not include_tests else "",
        "test" if not include_tests else "",
        "benchmarks",
        "docs",
        "assets",
        "examples",
    ]
    ignore_patterns = [p for p in ignore_patterns if p]

    if verbose:
        print(f"Copying from {src} -> {dest}")
        print(f"Ignoring patterns: {ignore_patterns}")

    shutil.copytree(src, dest, ignore=shutil.ignore_patterns(*ignore_patterns))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Vendor the installed ragas package into vendor/ragas")
    parser.add_argument("--source", type=str, default=None, help="Optional path to ragas source directory")
    parser.add_argument(
        "--dest",
        type=str,
        default=str(Path("vendor/ragas")),
        help="Destination directory for vendor mirror (default: vendor/ragas)",
    )
    parser.add_argument("--include-tests", action="store_true", help="Include tests in the vendor mirror")
    parser.add_argument("--verbose", action="store_true", help="Verbose logging")

    args = parser.parse_args(argv)

    try:
        src = find_ragas_source(args.source)
        dest = Path(args.dest).expanduser().resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        copy_ragas_source(src, dest, include_tests=args.include_tests, verbose=args.verbose)
        if args.verbose:
            print("Vendor mirror updated successfully.")
        return 0
    except Exception as exc:  # noqa: BLE001 - allow broad to print helpful message
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
