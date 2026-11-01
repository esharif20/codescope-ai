"""Tests for the app.analysis CLI (contract point 13).

All of these call `main()` in-process (per the contract, no subprocess is
needed here -- subprocessing is reserved for the isolation guard test in
test_python_symbols.py).
"""

from __future__ import annotations

import json

from app.analysis.cli import main


def test_valid_file_prints_parseable_json_and_exits_zero(write_source, capsys):
    path = write_source("def foo():\n    pass\n", name="module.py")

    exit_code = main([str(path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "ok"
    assert payload["file_path"] == str(path)
    assert len(payload["symbols"]) == 1
    assert payload["symbols"][0]["name"] == "foo"


def test_compact_flag_produces_single_line_json_and_exits_zero(write_source, capsys):
    path = write_source("def foo():\n    pass\n", name="module.py")

    exit_code = main([str(path), "--compact"])
    captured = capsys.readouterr()

    assert exit_code == 0
    stripped = captured.out.rstrip("\n")
    assert "\n" not in stripped

    payload = json.loads(captured.out)
    assert payload["status"] == "ok"


def test_broken_file_still_exits_zero_with_syntax_errors_status(write_source, capsys):
    lines = [
        "def good():",
        "    pass",
        "",
        "",
        "def broken(",
        "    pass",
    ]
    source = "\n".join(lines) + "\n"
    path = write_source(source, name="broken.py")

    exit_code = main([str(path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    payload = json.loads(captured.out)
    assert payload["status"] == "syntax_errors"
    assert len(payload["errors"]) >= 1


def test_broken_file_with_compact_flag_still_exits_zero(write_source, capsys):
    lines = [
        "def good():",
        "    pass",
        "",
        "",
        "def broken(",
        "    pass",
    ]
    source = "\n".join(lines) + "\n"
    path = write_source(source, name="broken.py")

    exit_code = main([str(path), "--compact"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "\n" not in captured.out.rstrip("\n")
    payload = json.loads(captured.out)
    assert payload["status"] == "syntax_errors"


def test_nonexistent_path_exits_one_with_nonempty_stderr(tmp_path, capsys):
    missing = tmp_path / "does_not_exist.py"

    exit_code = main([str(missing)])
    captured = capsys.readouterr()

    assert exit_code == 1
    assert captured.err.strip() != ""
