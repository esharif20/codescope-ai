"""Tests for `app.analysis.module_paths.module_path_for` (D-08)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.analysis.module_paths import module_path_for


def test_plain_file_one_level_deep(tmp_path: Path) -> None:
    root = tmp_path
    file_path = root / "app" / "main.py"
    assert module_path_for(str(file_path), str(root)) == "app.main"


def test_nested_file(tmp_path: Path) -> None:
    root = tmp_path
    file_path = root / "app" / "services" / "auth.py"
    assert module_path_for(str(file_path), str(root)) == "app.services.auth"


def test_package_init_maps_to_containing_directory(tmp_path: Path) -> None:
    root = tmp_path
    file_path = root / "app" / "services" / "__init__.py"
    assert module_path_for(str(file_path), str(root)) == "app.services"


def test_repo_root_init_maps_to_empty_string(tmp_path: Path) -> None:
    root = tmp_path
    file_path = root / "__init__.py"
    assert module_path_for(str(file_path), str(root)) == ""


def test_path_outside_root_raises_value_error(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    outside = tmp_path / "other" / "file.py"
    with pytest.raises(ValueError):
        module_path_for(str(outside), str(root))


def test_root_trailing_slash_is_normalized(tmp_path: Path) -> None:
    root = tmp_path
    file_path = root / "app" / "main.py"
    with_slash = module_path_for(str(file_path), str(root) + "/")
    without_slash = module_path_for(str(file_path), str(root))
    assert with_slash == without_slash == "app.main"
