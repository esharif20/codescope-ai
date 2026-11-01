"""Tests for `app.analysis.imports.extract_raw_imports` (CS-021, import half).

Extraction only -- no resolution, no filesystem lookups. See
`.planning/phases/02-imports-resolution-call-graph/02-03-PLAN.md` for the
confirmed Tree-sitter grammar shapes these tests assert against.
"""

from __future__ import annotations

from app.analysis.imports import RawImport, extract_raw_imports


def test_import_plain() -> None:
    result = extract_raw_imports("import os", "mod.py")

    assert result == [
        RawImport(
            kind="import",
            module="os",
            relative_level=0,
            names=[("os", None)],
            is_star=False,
            line=1,
            file_path="mod.py",
        )
    ]


def test_import_multi_name() -> None:
    result = extract_raw_imports("import os, sys", "mod.py")

    assert result == [
        RawImport(
            kind="import",
            module="os",
            relative_level=0,
            names=[("os", None)],
            is_star=False,
            line=1,
            file_path="mod.py",
        ),
        RawImport(
            kind="import",
            module="sys",
            relative_level=0,
            names=[("sys", None)],
            is_star=False,
            line=1,
            file_path="mod.py",
        ),
    ]


def test_import_aliased() -> None:
    result = extract_raw_imports("import os.path as p", "mod.py")

    assert result == [
        RawImport(
            kind="import",
            module="os.path",
            relative_level=0,
            names=[("os.path", "p")],
            is_star=False,
            line=1,
            file_path="mod.py",
        )
    ]
