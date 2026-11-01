"""JSON command-line interface for the Python symbol extractor.

Runnable as either the installed console script (``codescope-parse FILE``)
or as a module (``python -m app.analysis.cli FILE``).
"""

from __future__ import annotations

import argparse
import sys

from app.analysis.python_symbols import extract_symbols_from_file


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="codescope-parse",
        description=(
            "Extract Python symbols (functions, classes, methods) from a "
            "source file and print the result as JSON."
        ),
    )
    parser.add_argument("path", help="Path to a Python source file.")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print single-line JSON instead of pretty-printed JSON.",
    )
    args = parser.parse_args(argv)

    try:
        result = extract_symbols_from_file(args.path)
    except OSError as exc:
        print(f"error: cannot read {args.path}: {exc}", file=sys.stderr)
        return 1

    if args.compact:
        print(result.model_dump_json())
    else:
        print(result.model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
