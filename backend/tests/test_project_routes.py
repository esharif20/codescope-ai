"""Public project route analysis remains bounded, diagnostic and parse-only."""

import subprocess
import sys
from pathlib import Path

import pytest

from app.analysis import ProjectImpactAnalysis, analyze_route_impacts


@pytest.fixture
def source_tree(tmp_path: Path) -> Path:
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\nfrom endpoints import router\n"
        "app = FastAPI()\napp.include_router(router, prefix='/api')\n"
    )
    (tmp_path / "endpoints.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/users')\n"
        "def helper():\n    return 1\n"
        "@router.get('/me')\ndef handler():\n    return helper()\n"
    )
    return tmp_path


def test_imported_router_and_call_evidence(source_tree: Path) -> None:
    result = analyze_route_impacts(str(source_tree), ["endpoints:helper"])
    assert isinstance(result, ProjectImpactAnalysis)
    assert not result.partial
    [path] = result.impact.impacts
    assert (path.route.app_id, path.route.method, path.route.path) == (
        "main:app", "GET", "/api/users/me"
    )
    assert path.symbols == ["endpoints:handler", "endpoints:helper"]
    assert path.edges[0].lines == [7]
    assert path.route.declaration.line == 5
    assert [fact.line for fact in path.route.registration_evidence] == [3, 4, 2]
    assert result.routes.file_statuses == result.project_graph.file_statuses


def test_nested_mount_and_package_relative_import(tmp_path: Path) -> None:
    package = tmp_path / "pkg"
    package.mkdir()
    (tmp_path / "main.py").write_text(
        "from fastapi import FastAPI\nfrom pkg import router\n"
        "app = FastAPI()\napp.include_router(router, prefix='/v1')\n"
    )
    (package / "__init__.py").write_text(
        "from fastapi import APIRouter\nfrom .child import router as child\n"
        "router = APIRouter(prefix='/outer')\nrouter.include_router(child, prefix='/inner')\n"
    )
    (package / "child.py").write_text(
        "from fastapi import APIRouter\nrouter = APIRouter(prefix='/leaf')\n"
        "@router.get('/')\ndef endpoint():\n    return 1\n"
    )
    result = analyze_route_impacts(str(tmp_path), ["pkg.child:endpoint"])
    assert result.impact.impacts[0].route.path == "/v1/outer/inner/leaf/"
    assert not result.partial


@pytest.mark.parametrize("status", ["decode_error", "syntax_errors", "unreadable"])
def test_incomplete_files_are_visible(source_tree: Path, monkeypatch, status: str) -> None:
    import app.analysis.project_graph as graph_module

    broken = source_tree / "broken.py"
    broken.write_bytes(b"\xff" if status == "decode_error" else b"def broken(:\n")
    if status == "unreadable":
        real_extract = graph_module.extract_symbols_from_file

        def extract(path):
            if Path(path) == broken:
                raise OSError("unreadable")
            return real_extract(path)

        monkeypatch.setattr(graph_module, "extract_symbols_from_file", extract)
    result = analyze_route_impacts(str(source_tree), ["endpoints:helper"])
    assert result.partial
    assert result.routes.file_statuses[str(broken)] == status
    assert len(result.impact.impacts) == 1


def test_file_cap_does_not_read_omitted_sources(source_tree: Path, monkeypatch) -> None:
    import app.analysis.project_graph as graph_module

    monkeypatch.setattr(graph_module, "_MAX_FILES", 1)
    result = analyze_route_impacts(str(source_tree), ["endpoints:helper"])
    assert result.partial
    assert result.routes.file_statuses[str(source_tree / "main.py")] == "skipped_file_cap"
    assert not result.routes.registrations


@pytest.mark.parametrize("failure", ["unreadable", "decode_error"])
def test_late_source_failure_is_a_route_diagnostic(source_tree: Path, monkeypatch, failure) -> None:
    import app.analysis.project_routes as route_module

    real_build = route_module.build_project_graph

    def build(root):
        graph = real_build(root)
        target = source_tree / "endpoints.py"
        if failure == "unreadable":
            target.unlink()
        else:
            target.write_bytes(b"\xff")
        return graph

    monkeypatch.setattr(route_module, "build_project_graph", build)
    result = analyze_route_impacts(str(source_tree), ["endpoints:helper"])
    assert result.partial
    assert result.project_graph.file_statuses[str(source_tree / "endpoints.py")] == "ok"
    assert result.routes.file_statuses[str(source_tree / "endpoints.py")] == failure
    assert any(d.reason == failure for d in result.routes.diagnostics)
    assert result.impact.impacts == []


@pytest.mark.parametrize("cap", ["unresolved", "routes", "impact"])
def test_underlying_truncation_propagates(source_tree: Path, monkeypatch, cap: str) -> None:
    import app.analysis.impact as impact_module
    import app.analysis.project_graph as graph_module
    import app.analysis.route_resolver as resolver_module

    if cap == "unresolved":
        (source_tree / "unknown.py").write_text("def f():\n    unknown()\n")
        monkeypatch.setattr(graph_module, "_MAX_UNRESOLVED_ENTRIES", 0)
    elif cap == "routes":
        monkeypatch.setattr(resolver_module, "_MAX_REGISTRATIONS", 0)
    else:
        monkeypatch.setattr(impact_module, "_MAX_VISITED_NODES", 0)
    result = analyze_route_impacts(str(source_tree), ["endpoints:helper"])
    assert result.partial
    assert (result.project_graph.unresolved_truncated or result.routes.truncated
            or result.impact.truncated)


def test_unsupported_route_syntax_is_partial(source_tree: Path) -> None:
    (source_tree / "dynamic.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "@app.get(PATH)\ndef dynamic():\n    return 1\n"
    )
    result = analyze_route_impacts(str(source_tree), [])
    assert result.partial
    assert result.routes.diagnostics


def test_unresolved_calls_alone_do_not_mark_partial(source_tree: Path) -> None:
    (source_tree / "unknown.py").write_text("def f():\n    unknown()\n")
    result = analyze_route_impacts(str(source_tree), [])
    assert result.project_graph.call_graph.unresolved
    assert not result.partial


def test_sources_and_fastapi_are_never_imported(source_tree: Path) -> None:
    (source_tree / "trap.py").write_text("raise RuntimeError('must not execute')\n")
    code = (
        "import sys; from app.analysis import analyze_route_impacts; "
        f"analyze_route_impacts({str(source_tree)!r}, []); "
        "assert 'fastapi' not in sys.modules; assert 'trap' not in sys.modules"
    )
    subprocess.run([sys.executable, "-c", code], check=True)
