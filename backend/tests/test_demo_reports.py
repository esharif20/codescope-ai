"""Frozen demo artifacts preserve controlled evidence and exact serialization."""

import hashlib
import json
import shutil
import socket
import subprocess
import sys

import pytest

from app.ingestion.models import IngestionError
from app.reporting import demos
from app.reporting.builder import canonical_json_bytes


def test_frozen_reports_and_catalog():
    entries = demos.list_demos()
    assert [entry["id"] for entry in entries] == ["auth-positive", "unrelated-negative"]
    catalog = json.loads((demos._DEMO_ROOT / "catalog.json").read_bytes())
    for entry in catalog["entries"]:
        report = demos.get_demo_report(entry["id"])
        raw = (demos._DEMO_ROOT / demos._DEMO_FILES[entry["id"]]).read_bytes()
        assert raw == canonical_json_bytes(report)
        assert hashlib.sha256(raw).hexdigest() == entry["report_sha256"]
        assert report.provenance.kind == "controlled"
        assert "not real GitHub PR analyses" in report.provenance.description
        assert report.report_id == entry["id"]
        for revision in report.revisions:
            paths = {finding.route.path for finding in revision.findings}
            assert paths == (
                {"/users/me", "/users/{user_id}"} if entry["id"] == "auth-positive" else set()
            )
        if entry["id"] == "unrelated-negative":
            assert report.provenance.fixture_id == "unrelated-callers"
            assert report.changes[0].symbol_id == "callers:call_twice"


def test_check_is_read_only_and_byte_identical():
    before = {path.name: path.read_bytes() for path in demos._DEMO_ROOT.iterdir()}
    result = subprocess.run(
        [sys.executable, "-m", "app.reporting.demos", "--check"], capture_output=True
    )
    assert result.returncode == 0, result.stderr
    assert before == {path.name: path.read_bytes() for path in demos._DEMO_ROOT.iterdir()}


@pytest.fixture
def artifacts(tmp_path, monkeypatch):
    root = tmp_path / "demos"
    shutil.copytree(demos._DEMO_ROOT, root)
    monkeypatch.setattr(demos, "_DEMO_ROOT", root)
    return root


@pytest.mark.parametrize(
    "demo_id",
    [
        "../auth-positive",
        ".",
        "..",
        "%2fauth-positive",
        "auth-positive.json",
        "auth-positive/",
        "auth-positive\\x",
        "AUTH-POSITIVE",
        "",
    ],
)
def test_unknown_ids_never_touch_files(monkeypatch, demo_id):
    def forbidden(*args, **kwargs):
        raise AssertionError("unknown ID accessed files")

    monkeypatch.setattr(demos, "_read", forbidden)
    with pytest.raises(IngestionError) as caught:
        demos.get_demo_report(demo_id)
    assert caught.value.code == "demo_not_found"
    assert caught.value.http_status == 404


@pytest.mark.parametrize(
    "damage",
    [
        "missing",
        "hash",
        "schema",
        "provenance",
        "id",
        "noncanonical",
        "too_large",
        "catalog_ids",
        "catalog_schema",
        "catalog_extra",
        "catalog_title",
        "symlink",
    ],
)
def test_corruption_fails_closed(artifacts, damage):
    path = artifacts / "auth-positive.json"
    report = json.loads(path.read_bytes())
    catalog_path = artifacts / "catalog.json"
    catalog = json.loads(catalog_path.read_bytes())
    if damage == "missing":
        path.unlink()
    elif damage == "hash":
        catalog["entries"][0]["report_sha256"] = "0" * 64
    elif damage == "noncanonical":
        path.write_bytes(path.read_bytes() + b"\n")
    elif damage == "too_large":
        path.write_bytes(b" " * (2097152 + 1))
    elif damage.startswith("catalog_"):
        if damage == "catalog_ids":
            catalog["entries"][0]["id"] = "../auth-positive"
        elif damage == "catalog_schema":
            catalog["schema_version"] = "2"
        elif damage == "catalog_title":
            catalog["entries"][0]["title"] = "Unreviewed mutable metadata"
        else:
            catalog["unexpected"] = True
    elif damage == "symlink":
        target = artifacts / "target.json"
        path.rename(target)
        path.symlink_to(target)
    else:
        if damage == "schema":
            report["schema_version"] = "2"
        elif damage == "provenance":
            report["provenance"]["fixture_id"] = "unsupported-audit"
        else:
            report["report_id"] = "unrelated-negative"
        path.write_bytes(canonical_json_bytes(report))
        catalog["entries"][0]["report_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    catalog_path.write_bytes(canonical_json_bytes(catalog))
    for operation in (demos.list_demos, lambda: demos.get_demo_report("auth-positive")):
        with pytest.raises(IngestionError) as caught:
            operation()
        assert caught.value.code == "demo_unavailable"
        assert caught.value.http_status == 503
        assert str(artifacts) not in str(caught.value)


def test_runtime_uses_no_compute_or_network_and_returns_defensive_instances(monkeypatch):
    from app.analysis import project_routes
    from app.reporting import builder, evaluation

    def forbidden(*args, **kwargs):
        raise AssertionError("runtime attempted computation or network")

    for module, name in (
        (demos, "_regenerated_bytes"),
        (builder, "build_report"),
        (evaluation, "build_case_report"),
        (evaluation, "analyze_route_impacts"),
        (project_routes, "analyze_route_impacts"),
        (socket, "socket"),
    ):
        monkeypatch.setattr(module, name, forbidden)
    before = {path.name: path.read_bytes() for path in demos._DEMO_ROOT.iterdir()}
    report = demos.get_demo_report("auth-positive")
    report.revisions[0].findings.clear()
    entries = demos.list_demos()
    entries[0]["title"] = "mutated"
    assert demos.get_demo_report("auth-positive").revisions[0].findings
    assert demos.list_demos()[0]["title"] != "mutated"
    assert before == {path.name: path.read_bytes() for path in demos._DEMO_ROOT.iterdir()}


def test_relocated_sources_and_stale_inputs(artifacts, tmp_path, monkeypatch, capsys):
    from app.reporting import evaluation

    repository = tmp_path / "relocated"
    shutil.copytree(evaluation.REPOSITORY_ROOT / "fixtures", repository / "fixtures")
    monkeypatch.setattr(evaluation, "REPOSITORY_ROOT", repository)
    monkeypatch.setattr(demos, "_REPOSITORY_ROOT", repository)
    assert demos.main(["--check"]) == 0
    before = {path.name: path.read_bytes() for path in artifacts.iterdir()}
    source = repository / "fixtures/sample_fastapi_repo/services/auth.py"
    source.write_bytes(source.read_bytes() + b"\n# changed fixture bytes\n")
    assert demos.main(["--check"]) == 1
    # Restore source, then change a seed without altering frozen artifacts.
    source.write_bytes(source.read_bytes().removesuffix(b"\n# changed fixture bytes\n"))
    labels_path = repository / "fixtures/report_evaluation/labels.json"
    labels = json.loads(labels_path.read_bytes())
    labels["cases"][0]["seed_changes"][0]["old"]["start_line"] = 14
    labels_path.write_bytes(canonical_json_bytes(labels))
    assert demos.main(["--check"]) == 1
    assert before == {path.name: path.read_bytes() for path in artifacts.iterdir()}
    assert "Demo artifact verification failed." in capsys.readouterr().err
