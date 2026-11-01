"""Tests for whole-project static analysis orchestration."""

from __future__ import annotations

from pathlib import Path

from app.analysis.models import ResolutionStatus
from app.analysis.project_graph import _build_symbols_and_bindings


def test_build_symbols_and_bindings_resolves_cross_file_import(tmp_path: Path) -> None:
    (tmp_path / "source.py").write_text("def helper():\n    return 1\n")
    consumer = tmp_path / "consumer.py"
    consumer.write_text("from source import helper\n\ndef use():\n    return helper()\n")

    _, bindings, statuses, _ = _build_symbols_and_bindings(str(tmp_path))

    assert statuses[str(tmp_path / "source.py")] == "ok"
    assert statuses[str(consumer)] == "ok"
    assert bindings["consumer"][0].status == ResolutionStatus.RESOLVED
    assert bindings["consumer"][0].source_module == "source"
    assert bindings["consumer"][0].source_name == "helper"


def test_build_symbols_and_bindings_records_decode_error_and_continues(tmp_path: Path) -> None:
    valid = tmp_path / "valid.py"
    invalid = tmp_path / "invalid.py"
    valid.write_text("def valid():\n    return 1\n")
    invalid.write_bytes(b"\xff\xfe")

    symbols, _, statuses, _ = _build_symbols_and_bindings(str(tmp_path))

    assert statuses[str(invalid)] == "decode_error"
    assert statuses[str(valid)] == "ok"
    assert [symbol.qualified_name for symbol in symbols["valid"]] == ["valid"]
    assert "invalid" not in symbols


def test_build_symbols_and_bindings_records_unreadable_and_continues(
    tmp_path: Path, monkeypatch: object
) -> None:
    import app.analysis.project_graph as project_graph

    good = tmp_path / "good.py"
    missing = tmp_path / "missing.py"
    good.write_text("def good():\n    return 1\n")
    missing.write_text("def missing():\n    return 1\n")
    real_extract = project_graph.extract_symbols_from_file

    def raise_for_missing(path: str | Path):
        if Path(path) == missing:
            raise OSError("simulated unreadable file")
        return real_extract(path)

    monkeypatch.setattr(project_graph, "extract_symbols_from_file", raise_for_missing)

    symbols, _, statuses, _ = _build_symbols_and_bindings(str(tmp_path))

    assert statuses[str(missing)] == "unreadable"
    assert statuses[str(good)] == "ok"
    assert [symbol.qualified_name for symbol in symbols["good"]] == ["good"]


def test_build_symbols_and_bindings_applies_file_cap_deterministically(
    tmp_path: Path, monkeypatch: object
) -> None:
    import app.analysis.project_graph as project_graph

    first = tmp_path / "a.py"
    second = tmp_path / "b.py"
    third = tmp_path / "c.py"
    for path in (first, second, third):
        path.write_text(f"def {path.stem}():\n    return 1\n")
    monkeypatch.setattr(project_graph, "_MAX_FILES", 2)

    symbols, _, statuses, _ = _build_symbols_and_bindings(str(tmp_path))

    assert set(symbols) == {"a", "b"}
    assert statuses[str(first)] == "ok"
    assert statuses[str(second)] == "ok"
    assert statuses[str(third)] == "skipped_file_cap"
