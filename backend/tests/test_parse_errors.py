"""Tests for app.analysis error/edge-case handling (contract points 1-3, 8).

Broken-snippet shapes used below were verified directly against the
installed tree-sitter-python 0.25.0 grammar (not guessed) -- see the
"genuinely broken snippet" and "missing token" tests for the exact node
shapes this relies on.
"""

from __future__ import annotations

from app.analysis import extract_symbols, extract_symbols_from_file

# ---------------------------------------------------------------------------
# file_path passthrough exactness (contract point 1)
# ---------------------------------------------------------------------------


def test_file_path_passthrough_exact_for_extract_symbols():
    weird_path = "some/weird path.py"
    result = extract_symbols("def foo():\n    pass\n", weird_path)

    assert result.file_path == weird_path
    assert len(result.symbols) == 1
    assert result.symbols[0].file_path == weird_path


def test_file_path_passthrough_is_never_resolved_or_normalized():
    # A relative-looking, non-normalized path should round-trip byte-for-byte,
    # not get resolved to an absolute path or have ./ segments collapsed.
    weird_path = "./a/../weird//path.py"
    result = extract_symbols("x = 1\n", weird_path)
    assert result.file_path == weird_path


def test_file_path_passthrough_for_extract_symbols_from_file(write_source):
    path = write_source("def foo():\n    pass\n", name="weird name.py")
    result = extract_symbols_from_file(path)

    assert result.file_path == str(path)
    assert result.symbols[0].file_path == str(path)


def test_file_path_passthrough_for_extract_symbols_from_file_str_argument(write_source):
    path = write_source("def foo():\n    pass\n", name="module.py")
    result = extract_symbols_from_file(str(path))

    assert result.file_path == str(path)


# ---------------------------------------------------------------------------
# Empty / whitespace-only source (contract point 2)
# ---------------------------------------------------------------------------


def test_empty_string_source_is_status_empty():
    result = extract_symbols("", "module.py")
    assert result.status == "empty"
    assert result.symbols == []
    assert result.errors == []


def test_whitespace_only_string_source_is_status_empty():
    result = extract_symbols("   \n\t\n   \n", "module.py")
    assert result.status == "empty"
    assert result.symbols == []
    assert result.errors == []


def test_whitespace_only_bytes_source_is_status_empty():
    result = extract_symbols(b"   \n  \n", "module.py")
    assert result.status == "empty"
    assert result.symbols == []
    assert result.errors == []


def test_zero_byte_file_is_status_empty(write_source):
    path = write_source(b"", name="empty.py")
    result = extract_symbols_from_file(path)

    assert result.status == "empty"
    assert result.symbols == []
    assert result.errors == []
    assert result.file_path == str(path)


# ---------------------------------------------------------------------------
# str input can never produce decode_error (contract point 3)
# ---------------------------------------------------------------------------


def test_str_input_never_produces_decode_error_even_with_unicode():
    source = "def f():  # emoji \U0001F389\n    pass\n"
    result = extract_symbols(source, "module.py")
    assert result.status != "decode_error"
    assert result.status == "ok"
    assert result.symbols[0].name == "f"


# ---------------------------------------------------------------------------
# bytes input that fails strict UTF-8 decoding -> decode_error
# ---------------------------------------------------------------------------


def test_bytes_invalid_utf8_produces_decode_error():
    # 0xFF is never valid in UTF-8 (not a valid lead byte or continuation
    # byte), so strict decoding must fail.
    bad_bytes = b"x = 1\n\xff\n"
    result = extract_symbols(bad_bytes, "module.py")

    assert result.status == "decode_error"
    assert result.symbols == []
    assert len(result.errors) == 1

    issue = result.errors[0]
    assert issue.kind == "error"
    assert issue.start_line == 1
    assert issue.end_line == 1
    assert isinstance(issue.message, str)
    assert len(issue.message) > 0
    # The message must be a description, not literally the raw bytes dumped.
    assert issue.message != repr(bad_bytes)
    assert issue.message != str(bad_bytes)


def test_bytes_invalid_utf8_decode_error_via_file(write_source):
    bad_bytes = b"x = 1\n\xff\n"
    path = write_source(bad_bytes, name="bad_encoding.py")
    result = extract_symbols_from_file(path)

    assert result.status == "decode_error"
    assert result.symbols == []
    assert result.file_path == str(path)


# ---------------------------------------------------------------------------
# Syntax errors with partial recovery (contract point 8)
# ---------------------------------------------------------------------------


def test_broken_snippet_syntax_errors_with_partial_recovery_two_sided_check():
    # Verified against the real grammar: an unclosed "(" on `def broken(`
    # yields a single-line top-level ERROR node covering ONLY that line,
    # while the surrounding `good`/`also_good` function_definition nodes
    # are recovered untouched. "broken" never becomes a function_definition
    # node at all, so it must be absent from symbols.
    lines = [
        "def good():",  # 1
        "    pass",  # 2
        "",  # 3
        "",  # 4
        "def broken(",  # 5
        "    pass",  # 6
        "",  # 7
        "",  # 8
        "def also_good():",  # 9
        "    pass",  # 10
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "syntax_errors"

    names = {s.name for s in result.symbols}
    assert "good" in names
    assert "also_good" in names
    assert "broken" not in names  # absent: its tokens sit inside the ERROR node

    good = next(s for s in result.symbols if s.name == "good")
    also_good = next(s for s in result.symbols if s.name == "also_good")
    assert good.start_line == 1 and good.end_line == 2
    assert also_good.start_line == 9 and also_good.end_line == 10

    # At least one error entry whose range covers the broken region (line 5).
    assert len(result.errors) >= 1
    assert any(
        issue.kind == "error" and issue.start_line <= 5 <= issue.end_line
        for issue in result.errors
    )


def test_broken_snippet_missing_token():
    # Verified against the real grammar: `def f(:` causes the parser to
    # insert a zero-width MISSING ")" node immediately before the literal
    # ":" in the source, inside f's parameters list.
    lines = [
        "def good():",  # 1
        "    pass",  # 2
        "",  # 3
        "",  # 4
        "def f(:",  # 5
        "    pass",  # 6
        "",  # 7
        "",  # 8
        "def also_good():",  # 9
        "    pass",  # 10
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "syntax_errors"

    # Unambiguous: these two are untouched by the missing-token recovery.
    names = {s.name for s in result.symbols}
    assert "good" in names
    assert "also_good" in names

    # Resolved (not left ambiguous): `f` IS extracted too. The symbol walk's
    # dispatch for function_definition only ever pushes the `body` field, not
    # `parameters` -- so the MISSING ")" living inside `parameters` is never
    # visited by the symbol walk at all, and `f` itself is neither is_error
    # nor is_missing. It's still reported separately via `errors` below.
    assert "f" in names

    missing_issues = [e for e in result.errors if e.kind == "missing"]
    assert len(missing_issues) == 1
    assert missing_issues[0].start_line == 5

    # There must be a "missing" issue pinned at line 5 (the MISSING ")" is a
    # zero-width point immediately before the ":" on that line).
    missing_issues = [issue for issue in result.errors if issue.kind == "missing"]
    assert len(missing_issues) >= 1
    assert any(issue.start_line == 5 and issue.end_line == 5 for issue in missing_issues)

    # NOTE: whether `f` itself is also surfaced as a Symbol is intentionally
    # NOT asserted here -- see the report back to the orchestrator for why
    # this is genuinely ambiguous under the pinned contract wording.


def test_definition_inside_error_region_absent_while_lines_covered_by_errors():
    # Same shape as the partial-recovery test above, but additionally pins
    # the "one entry per top-most error/missing node" counting rule: since
    # there is exactly one ERROR node in this tree (not one per descendant
    # token inside it), there must be exactly one reported issue, not one
    # per token swallowed by the error (def/identifier/`(`).
    lines = [
        "def good():",  # 1
        "    pass",  # 2
        "",  # 3
        "",  # 4
        "def broken(",  # 5
        "    pass",  # 6
        "",  # 7
        "",  # 8
        "def also_good():",  # 9
        "    pass",  # 10
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "syntax_errors"
    assert not any(s.name == "broken" for s in result.symbols)
    assert len(result.errors) == 1
    issue = result.errors[0]
    assert issue.kind == "error"
    assert issue.start_line <= 5 <= issue.end_line
