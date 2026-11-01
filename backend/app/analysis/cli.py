"""JSON command-line interface for the Python symbol extractor.

Runnable as either the installed console script (``codescope-parse FILE``)
or as a module (``python -m app.analysis.cli FILE``).
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import networkx as nx

from app.analysis.project_graph import build_project_graph
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


def graph_main(argv: list[str] | None = None) -> int:
    """Build a call graph for a source directory and print JSON evidence."""
    parser = argparse.ArgumentParser(
        prog="codescope-graph",
        description=(
            "Build a NetworkX call graph for a directory of Python source files "
            "and print it as JSON."
        ),
    )
    parser.add_argument("root", help="Directory of Python source files to analyse.")
    parser.add_argument(
        "--compact",
        action="store_true",
        help="Print single-line JSON instead of pretty-printed JSON.",
    )
    args = parser.parse_args(argv)

    if not Path(args.root).is_dir():
        print(f"error: {args.root} is not a directory", file=sys.stderr)
        return 1

    result = build_project_graph(args.root)
    payload = {
        "graph": nx.node_link_data(result.call_graph.graph),
        "unresolved": {
            symbol_id: [entry.model_dump() for entry in entries]
            for symbol_id, entries in result.call_graph.unresolved.items()
        },
        "file_statuses": result.file_statuses,
        "unresolved_truncated": result.unresolved_truncated,
    }
    if args.compact:
        print(json.dumps(payload, separators=(",", ":")))
    else:
        print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
