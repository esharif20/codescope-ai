"""Shared pytest fixtures for the app.analysis test suite."""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.fixture
def write_source(tmp_path: Path):
    """Return a helper that writes source content to a real temp file.

    Writing to a real file (rather than inlining a `.py` fixture file in the
    repo) keeps pytest from ever trying to collect/import a deliberately
    broken sample module.
    """

    def _write(content: str | bytes, name: str = "module.py") -> Path:
        path = tmp_path / name
        if isinstance(content, bytes):
            path.write_bytes(content)
        else:
            path.write_text(content, encoding="utf-8")
        return path

    return _write
