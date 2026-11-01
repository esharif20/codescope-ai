"""Compute Phase 2's module-path addressing scheme for a file (D-08).

This module has a single pure function, ``module_path_for``, and zero
dependency on FastAPI or any web framework (see ``AGENTS.md``).
"""

from __future__ import annotations

from pathlib import Path


def module_path_for(file_path: str, root: str) -> str:
    """Compute the Phase 2 module path for `file_path`, relative to `root` (D-08).

    Rules (no auto-detection; `root` is always explicit):
    - `file_path` must be inside `root` (or raise ValueError -- never silently guess).
    - Path separators relative to root become `.`.
    - A trailing `.py` suffix is stripped.
    - A file named `__init__.py` maps to its OWN containing directory's dotted path
      (the package name itself), not `<package>.__init__`.
    - The repo-root `__init__.py` (directly inside `root`) maps to `""` (the empty string),
      representing the top-level implicit package.
    """
    root_path = Path(root).resolve()
    resolved_file_path = Path(file_path).resolve()

    try:
        relative = resolved_file_path.relative_to(root_path)
    except ValueError as exc:
        raise ValueError(
            f"file_path {file_path!r} is not inside root {root!r}"
        ) from exc

    parts = list(relative.parts)

    if parts and parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts:
        last = parts[-1]
        if last.endswith(".py"):
            last = last[: -len(".py")]
        parts[-1] = last

    return ".".join(parts)
