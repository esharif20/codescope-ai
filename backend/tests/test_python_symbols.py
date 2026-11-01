"""Tests for app.analysis symbol extraction behavior (contract points 4-12).

These tests are written purely against the pinned contract described in the
task brief -- they do not import or inspect any SA-2 implementation details
beyond the public surface of `app.analysis`.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from app.analysis import (
    ParseResult,
    ParseStatus,
    Symbol,
    SymbolKind,
    SyntaxIssue,
    SyntaxIssueKind,
    extract_symbols,
    extract_symbols_from_file,
)


def test_public_api_surface_is_importable_from_app_analysis():
    # The contract pins this exact import path -- never from submodules.
    # Merely getting here means all six names + both functions resolved.
    assert callable(extract_symbols)
    assert callable(extract_symbols_from_file)
    assert ParseResult is not None
    assert ParseStatus is not None
    assert Symbol is not None
    assert SymbolKind is not None
    assert SyntaxIssue is not None
    assert SyntaxIssueKind is not None


# ---------------------------------------------------------------------------
# Basic shapes: top-level function, class + methods, nesting combinations
# ---------------------------------------------------------------------------


def test_top_level_function():
    source = "def foo():\n    pass\n"
    result = extract_symbols(source, "module.py")

    assert isinstance(result, ParseResult)
    assert result.status == "ok"
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert isinstance(sym, Symbol)
    assert sym.name == "foo"
    assert sym.qualified_name == "foo"
    assert sym.kind == "function"
    assert sym.parent_qualified_name is None
    assert sym.decorator_start_line is None
    assert sym.is_async is False
    assert sym.start_line == 1
    assert sym.end_line == 2
    assert sym.file_path == "module.py"


def test_class_with_two_methods_exact_line_ranges():
    lines = [
        "class C:",  # 1
        "    def m1(self):",  # 2
        "        pass",  # 3
        "",  # 4
        "    def m2(self):",  # 5
        "        pass",  # 6
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    by_name = {s.qualified_name: s for s in result.symbols}
    assert set(by_name) == {"C", "C.m1", "C.m2"}

    cls = by_name["C"]
    assert cls.kind == "class"
    assert cls.parent_qualified_name is None
    assert cls.start_line == 1
    assert cls.end_line == 6

    m1 = by_name["C.m1"]
    assert m1.kind == "method"
    assert m1.name == "m1"
    assert m1.parent_qualified_name == "C"
    assert m1.start_line == 2
    assert m1.end_line == 3

    m2 = by_name["C.m2"]
    assert m2.kind == "method"
    assert m2.parent_qualified_name == "C"
    assert m2.start_line == 5
    assert m2.end_line == 6


def test_nested_function_inside_function_exact_line_ranges():
    lines = [
        "def outer():",  # 1
        "    def inner():",  # 2
        "        pass",  # 3
        "    return inner",  # 4
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    by_name = {s.qualified_name: s for s in result.symbols}
    assert set(by_name) == {"outer", "outer.<locals>.inner"}

    outer = by_name["outer"]
    assert outer.kind == "function"
    assert outer.parent_qualified_name is None
    assert outer.start_line == 1
    assert outer.end_line == 4

    inner = by_name["outer.<locals>.inner"]
    assert inner.kind == "nested_function"
    assert inner.name == "inner"
    assert inner.parent_qualified_name == "outer"
    assert inner.start_line == 2
    assert inner.end_line == 3


def test_nested_function_inside_method():
    lines = [
        "class C:",  # 1
        "    def m(self):",  # 2
        "        def helper():",  # 3
        "            pass",  # 4
        "        return helper",  # 5
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    by_name = {s.qualified_name: s for s in result.symbols}
    assert set(by_name) == {"C", "C.m", "C.m.<locals>.helper"}

    m = by_name["C.m"]
    assert m.kind == "method"
    assert m.parent_qualified_name == "C"

    helper = by_name["C.m.<locals>.helper"]
    assert helper.kind == "nested_function"
    assert helper.name == "helper"
    assert helper.parent_qualified_name == "C.m"
    assert helper.start_line == 3
    assert helper.end_line == 4


def test_class_nested_inside_class():
    lines = [
        "class Outer:",  # 1
        "    class Inner:",  # 2
        "        pass",  # 3
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    by_name = {s.qualified_name: s for s in result.symbols}
    assert set(by_name) == {"Outer", "Outer.Inner"}

    inner = by_name["Outer.Inner"]
    assert inner.kind == "class"
    assert inner.name == "Inner"
    assert inner.parent_qualified_name == "Outer"
    assert inner.start_line == 2
    assert inner.end_line == 3


def test_class_nested_inside_function():
    lines = [
        "def outer():",  # 1
        "    class Inner:",  # 2
        "        pass",  # 3
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    by_name = {s.qualified_name: s for s in result.symbols}
    assert set(by_name) == {"outer", "outer.<locals>.Inner"}

    inner = by_name["outer.<locals>.Inner"]
    assert inner.kind == "class"
    assert inner.name == "Inner"
    assert inner.parent_qualified_name == "outer"
    assert inner.start_line == 2
    assert inner.end_line == 3


# ---------------------------------------------------------------------------
# Decorators
# ---------------------------------------------------------------------------


def test_decorated_function_has_decorator_start_line():
    lines = [
        "@my_decorator",  # 1
        "def foo():",  # 2
        "    pass",  # 3
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    sym = result.symbols[0]
    assert sym.name == "foo"
    assert sym.decorator_start_line == 1
    assert sym.start_line == 2
    assert sym.end_line == 3


def test_decorated_method_single_decorator_property():
    lines = [
        "class C:",  # 1
        "    @property",  # 2
        "    def value(self):",  # 3
        "        return self._value",  # 4
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    by_name = {s.qualified_name: s for s in result.symbols}
    value = by_name["C.value"]
    assert value.kind == "method"
    assert value.decorator_start_line == 2
    assert value.start_line == 3
    assert value.end_line == 4


def test_decorated_method_multiple_decorators_uses_first_decorator_line():
    lines = [
        "class C:",  # 1
        "    @staticmethod",  # 2
        "    @another_decorator",  # 3
        "    def m():",  # 4
        "        pass",  # 5
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    by_name = {s.qualified_name: s for s in result.symbols}
    m = by_name["C.m"]
    assert m.kind == "method"
    # The FIRST decorator's line, not the last.
    assert m.decorator_start_line == 2
    assert m.start_line == 4
    assert m.end_line == 5


# ---------------------------------------------------------------------------
# async
# ---------------------------------------------------------------------------


def test_async_function_and_async_method():
    lines = [
        "async def foo():",  # 1
        "    pass",  # 2
        "",  # 3
        "class C:",  # 4
        "    async def m(self):",  # 5
        "        pass",  # 6
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    by_name = {s.qualified_name: s for s in result.symbols}
    foo = by_name["foo"]
    assert foo.kind == "function"
    assert foo.is_async is True
    assert foo.start_line == 1
    assert foo.end_line == 2

    m = by_name["C.m"]
    assert m.kind == "method"
    assert m.is_async is True
    assert m.start_line == 5
    assert m.end_line == 6

    cls = by_name["C"]
    assert cls.is_async is False


# ---------------------------------------------------------------------------
# Non-scoping blocks (if/try/with/for) at module level
# ---------------------------------------------------------------------------


def test_function_conditionally_defined_inside_if_is_still_function():
    lines = [
        "if True:",  # 1
        "    def foo():",  # 2
        "        pass",  # 3
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert sym.kind == "function"
    assert sym.qualified_name == "foo"
    assert sym.parent_qualified_name is None
    assert sym.start_line == 2
    assert sym.end_line == 3


def test_function_deeply_nested_in_non_scope_blocks_still_top_level_function():
    lines = [
        "for _ in range(1):",  # 1
        "    try:",  # 2
        "        with open('x') as f:",  # 3
        "            def foo():",  # 4
        "                pass",  # 5
        "    except Exception:",  # 6
        "        pass",  # 7
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert sym.kind == "function"
    assert sym.qualified_name == "foo"
    assert sym.parent_qualified_name is None
    assert sym.start_line == 4
    assert sym.end_line == 5


# ---------------------------------------------------------------------------
# Source order determinism
# ---------------------------------------------------------------------------


def test_source_order_determinism_b_defined_before_a():
    lines = [
        "def b():",  # 1
        "    pass",  # 2
        "",  # 3
        "def a():",  # 4
        "    pass",  # 5
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert [s.name for s in result.symbols] == ["b", "a"]


# ---------------------------------------------------------------------------
# Negative cases: these must never produce symbols
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        pytest.param("import os\nfrom sys import path\n", id="imports_only"),
        pytest.param("f = lambda x: x + 1\n", id="lambda_assignment"),
        pytest.param("X = 42\n", id="module_constant"),
        pytest.param("from typing import TypeVar\nT = TypeVar('T')\n", id="typevar"),
        pytest.param("squares = [x * x for x in range(10)]\n", id="comprehension"),
        pytest.param("# just a comment\n# another comment\n", id="comments_only"),
    ],
)
def test_negative_cases_produce_ok_with_no_symbols(source):
    result = extract_symbols(source, "module.py")
    assert result.status == "ok"
    assert result.symbols == []
    assert result.errors == []


# ---------------------------------------------------------------------------
# str vs bytes input equivalence
# ---------------------------------------------------------------------------


def test_str_and_bytes_input_produce_equivalent_results():
    source_str = "def foo():\n    pass\n"
    source_bytes = source_str.encode("utf-8")

    result_str = extract_symbols(source_str, "module.py")
    result_bytes = extract_symbols(source_bytes, "module.py")

    assert result_str.status == result_bytes.status == "ok"
    assert result_str.file_path == result_bytes.file_path == "module.py"
    assert len(result_str.symbols) == len(result_bytes.symbols) == 1

    for a, b in zip(result_str.symbols, result_bytes.symbols):
        assert a.name == b.name
        assert a.qualified_name == b.qualified_name
        assert a.kind == b.kind
        assert a.start_line == b.start_line
        assert a.end_line == b.end_line
        assert a.is_async == b.is_async


# ---------------------------------------------------------------------------
# Deep nesting must not blow the recursion limit
# ---------------------------------------------------------------------------


def test_deeply_nested_source_does_not_raise_recursion_error():
    depth = 150
    lines = []
    for i in range(depth):
        lines.append("    " * i + f"def f{i}():")
    lines.append("    " * depth + "pass")
    source = "\n".join(lines) + "\n"

    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    assert len(result.symbols) == depth
    assert result.symbols[0].kind == "function"
    assert all(s.kind == "nested_function" for s in result.symbols[1:])

    # The qualified-name / parent-qualified-name chain must be internally
    # consistent all the way down, without us having to hand-write the full
    # 150-level literal string.
    assert result.symbols[0].qualified_name == "f0"
    assert result.symbols[0].parent_qualified_name is None
    for i in range(1, depth):
        assert result.symbols[i].parent_qualified_name == result.symbols[i - 1].qualified_name
        assert result.symbols[i].qualified_name == (
            result.symbols[i - 1].qualified_name + f".<locals>.f{i}"
        )


# ---------------------------------------------------------------------------
# Same-name redefinition
# ---------------------------------------------------------------------------


def test_same_name_redefinition_produces_two_distinguishable_symbols():
    lines = [
        "def foo():",  # 1
        "    pass",  # 2
        "",  # 3
        "",  # 4
        "def foo():",  # 5
        "    return 1",  # 6
    ]
    source = "\n".join(lines) + "\n"
    result = extract_symbols(source, "module.py")

    assert result.status == "ok"
    assert len(result.symbols) == 2
    first, second = result.symbols

    assert first.name == first.qualified_name == "foo"
    assert second.name == second.qualified_name == "foo"

    assert (first.start_line, first.end_line) != (second.start_line, second.end_line)
    assert first.start_line == 1
    assert first.end_line == 2
    assert second.start_line == 5
    assert second.end_line == 6


# ---------------------------------------------------------------------------
# CRLF line endings
# ---------------------------------------------------------------------------


def test_crlf_line_endings_produce_correct_line_numbers(write_source):
    content = b"def foo():\r\n    pass\r\n"
    path = write_source(content, name="crlf_module.py")

    result = extract_symbols_from_file(path)

    assert result.status == "ok"
    assert len(result.symbols) == 1
    sym = result.symbols[0]
    assert sym.name == "foo"
    assert sym.start_line == 1
    assert sym.end_line == 2
    assert result.file_path == str(path)


# ---------------------------------------------------------------------------
# extract_symbols_from_file smoke test
# ---------------------------------------------------------------------------


def test_extract_symbols_from_file_smoke(write_source):
    path = write_source("def foo():\n    pass\n", name="smoke.py")
    result = extract_symbols_from_file(path)

    assert result.status == "ok"
    assert result.file_path == str(path)
    assert len(result.symbols) == 1
    assert result.symbols[0].file_path == str(path)


def test_extract_symbols_from_file_accepts_pathlike_and_str(write_source):
    path = write_source("def foo():\n    pass\n", name="pathlike.py")

    result_from_path = extract_symbols_from_file(path)
    result_from_str = extract_symbols_from_file(str(path))

    assert result_from_path.file_path == result_from_str.file_path == str(path)
    assert len(result_from_path.symbols) == len(result_from_str.symbols) == 1


# ---------------------------------------------------------------------------
# Isolation guard (contract point 14).
#
# This is the ONE test in the suite that must use a real subprocess rather
# than in-process calls: the whole point is to verify that nothing in THIS
# test process has ever imported fastapi merely as a side effect of
# `import app.analysis`. Checking `sys.modules` in-process would only prove
# that *this* interpreter (which may have imported fastapi for unrelated
# reasons, e.g. a future app.main import elsewhere in the suite) is clean,
# not that app.analysis itself is side-effect free.
# ---------------------------------------------------------------------------


def test_isolation_app_analysis_never_imports_fastapi():
    backend_dir = Path(__file__).resolve().parent.parent
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            "import app.analysis, sys; assert 'fastapi' not in sys.modules; print('ok')",
        ],
        cwd=str(backend_dir),
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert completed.returncode == 0, completed.stderr
    assert "ok" in completed.stdout
