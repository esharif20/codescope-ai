"""Source-only report assembly and canonical manifest regression checks."""

import hashlib
import json
from pathlib import Path

import pytest

from app.analysis.project_routes import analyze_route_impacts
from app.ingestion.models import IngestionError
from app.reporting.builder import build_report, canonical_json_bytes, snapshot_digest
from app.reporting.models import ControlledProvenance, ReportInput


def case(root):
    root.mkdir(parents=True)
    (root / "main.py").write_text(
        "from fastapi import FastAPI\napp = FastAPI()\n"
        "def helper():\n    return 1\n@app.get('/')\ndef handler():\n"
        "    helper()\n    return helper()\n"
        "def unresolved():\n    unknown('private expression')\n"
        "raise RuntimeError('never execute source')\n"
    )
    return analyze_route_impacts(str(root), ["main:helper", "main:handler"])


def setup(tmp_path):
    roots = {rev: tmp_path / rev for rev in ("base", "head")}
    analyses = {rev: case(root) for rev, root in roots.items()}
    inputs = ReportInput(report_id="case", provenance=ControlledProvenance(
        fixture_id="case", description="controlled", **{
            f"{rev}_digest": snapshot_digest(root, ["main.py"]) for rev, root in roots.items()
        }))
    return inputs, roots, analyses


def build(data, **kwargs):
    inputs, roots, analyses = data
    return build_report(inputs, roots=roots, **analyses, **kwargs)


def test_canonical_bytes():
    assert canonical_json_bytes({"z": "é", "a": 1}) == b'{"a":1,"z":"\xc3\xa9"}\n'
    assert canonical_json_bytes({"a": 1, "z": "é"}) == canonical_json_bytes({"z": "é", "a": 1})
    with pytest.raises(ValueError):
        canonical_json_bytes([float("nan")])


def test_manifest_exact_bytes_and_safe_paths(tmp_path):
    (tmp_path / "x.py").write_bytes(b"abc\n")
    expected = hashlib.sha256((4).to_bytes(8, "big") + b"x.py" +
                              (4).to_bytes(8, "big") + b"abc\n").hexdigest()
    assert snapshot_digest(tmp_path, ["x.py", "x.py"]) == expected
    (tmp_path / "link.py").symlink_to(tmp_path / "x.py")
    for path in ("link.py", "../outside.py", "/absolute.py"):
        with pytest.raises((ValueError, IngestionError)):
            snapshot_digest(tmp_path, [path])


def test_evidence_and_determinism(tmp_path):
    report = build(setup(tmp_path / "first"))
    assert canonical_json_bytes(report) == canonical_json_bytes(build(setup(tmp_path / "second")))
    assert [r.revision for r in report.revisions] == ["base", "head"]
    for revision in report.revisions:
        assert len(revision.findings) == 2
        [edge] = revision.edges
        assert [ref.start_line for ref in edge.evidence] == [7, 8]
        assert any(not finding.edges for finding in revision.findings)
    assert not report.partial
    assert any(u.category == "unresolved_call" for u in report.uncertainties)
    assert b"private expression" not in canonical_json_bytes(report)
    assert b"https://github.com" not in canonical_json_bytes(report)


def test_byte_limit_includes_newline(tmp_path):
    data = setup(tmp_path)
    size = len(canonical_json_bytes(build(data)))
    assert build(data, max_report_bytes=size)
    with pytest.raises(IngestionError) as error:
        build(data, max_report_bytes=size - 1)
    assert error.value.code == "result_limit_exceeded"


def test_missing_verified_evidence_fails_closed(tmp_path):
    data = setup(tmp_path)
    data[2]["head"].project_graph.call_graph.graph.nodes["main:helper"]["file_path"] = "/secret"
    with pytest.raises(IngestionError) as error:
        build(data)
    assert error.value.code == "report_evidence_invalid"
    assert "secret" not in str(error.value)


def test_changed_snapshot_rejected_and_budget_called(tmp_path):
    data = setup(tmp_path)
    count = []
    build(data, check_budget=lambda: count.append(1))
    assert len(count) > 10
    (data[1]["head"] / "main.py").write_text("changed\n")
    with pytest.raises(IngestionError):
        build(data)


def test_diagnostics_and_truncation(tmp_path):
    data = setup(tmp_path)
    data[2]["base"].impact.truncated = True
    data[2]["base"].impact.unknown_symbols = ["main:missing"]
    data[0].mapping_diagnostics = ["/secret/raw payload"]
    report = build(data)
    assert report.partial
    assert {u.category for u in report.uncertainties} >= {"mapping", "truncation", "unknown_symbol"}
    assert "/secret" not in json.dumps(report.model_dump(mode="json"))
