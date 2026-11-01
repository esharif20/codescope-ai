"""Tests for the additive ``codescope-graph`` command."""

from __future__ import annotations

import json

from app.analysis.cli import graph_main


def test_graph_main_prints_compact_inspectable_graph(tmp_path, capsys) -> None:
    (tmp_path / "module.py").write_text("def helper():\n    return 1\n")

    exit_code = graph_main([str(tmp_path), "--compact"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "\n" not in captured.out.rstrip("\n")
    payload = json.loads(captured.out)
    assert set(payload) == {"graph", "unresolved", "file_statuses", "unresolved_truncated"}
    assert payload["graph"]["nodes"]


def test_graph_main_rejects_missing_or_non_directory_path(tmp_path, capsys) -> None:
    file_path = tmp_path / "module.py"
    file_path.write_text("def helper():\n    return 1\n")

    exit_code = graph_main([str(file_path)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.err.strip()
