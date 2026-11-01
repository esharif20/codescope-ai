"""Source-only report assembly and canonical manifest regression checks."""

import hashlib
import json

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
    inputs = ReportInput(
        report_id="case",
        provenance=ControlledProvenance(
            fixture_id="case",
            description="controlled",
            **{f"{rev}_digest": snapshot_digest(root, ["main.py"]) for rev, root in roots.items()},
        ),
    )
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
    expected = hashlib.sha256(
        (4).to_bytes(8, "big") + b"x.py" + (4).to_bytes(8, "big") + b"abc\n"
    ).hexdigest()
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


def test_github_fork_and_removed_change(tmp_path):
    from app.ingestion.models import PinnedPullRequest, PullRequestRef
    from app.ingestion.source_links import source_reference
    from app.reporting.models import GitHubProvenance, GitHubReference, ReportChange

    data = setup(tmp_path)
    metadata = PinnedPullRequest(
        ref=PullRequestRef(owner="owner", repo="repo", number=1),
        title="change",
        base_repository="owner/repo",
        head_repository="fork/repo",
        target_base_sha="a" * 40,
        analysis_base_sha="b" * 40,
        head_sha="c" * 40,
        changed_files=1,
    )
    data[0].provenance = GitHubProvenance(pull_request=metadata)
    data[0].changes = [
        ReportChange(
            status="removed",
            symbol_id="main:helper",
            kind="function",
            old=GitHubReference(source=source_reference(metadata, "base", "main.py", 3, 4)),
        )
    ]
    result = build(data)
    assert result.changes[0].old.source.commit_sha == "b" * 40
    for revision, repository, sha in zip(
        result.revisions, ["owner/repo", "fork/repo"], ["b" * 40, "c" * 40], strict=True
    ):
        for node in revision.nodes:
            assert node.source.source.repository == repository
            assert node.source.source.commit_sha == sha
            assert node.source.source.url.startswith(f"https://github.com/{repository}/blob/{sha}/")


def test_unverified_candidates_and_bad_diagnostic_stay_outside_graph(tmp_path):
    from app.analysis.models import ResolutionStatus, UnresolvedCall
    from app.analysis.route_models import RouteDiagnostic

    data = setup(tmp_path)
    analysis = data[2]["base"]
    analysis.project_graph.call_graph.unresolved["main:helper"] = [
        UnresolvedCall(
            enclosing_symbol="main:helper",
            file_path=str(data[1]["base"] / "main.py"),
            line=4,
            expression="private expression",
            status=ResolutionStatus.UNCERTAIN,
            candidates=["main:unresolved", "main:handler", "main:handler"],
        )
    ]
    analysis.routes.diagnostics = [
        RouteDiagnostic(
            file_path="/private/missing.py",
            line=1,
            expression="do not disclose",
            reason="private reason /secret",
        )
    ]
    report = build(data)
    [candidate] = [u for u in report.uncertainties if u.category == "uncertain_call"]
    assert candidate.candidates == ["main:handler", "main:unresolved"]
    assert len(report.revisions[0].edges) == 1
    assert report.partial
    serialized = canonical_json_bytes(report)
    for private in (b"/private", b"/secret", b"do not disclose", b"private expression"):
        assert private not in serialized
    assert any(u.category == "invalid_evidence" for u in report.uncertainties)


def test_registration_evidence_is_preserved(tmp_path):
    roots = {rev: tmp_path / rev for rev in ("base", "head")}
    analyses = {}
    digests = {}
    for revision, root in roots.items():
        root.mkdir()
        (root / "main.py").write_text(
            "from fastapi import FastAPI\n"
            "from endpoints import router\napp = FastAPI()\n"
            "app.include_router(router, prefix='/api')\n"
        )
        (root / "endpoints.py").write_text(
            "from fastapi import APIRouter\n"
            "router = APIRouter()\n@router.get('/')\ndef handler():\n    return 1\n"
        )
        analyses[revision] = analyze_route_impacts(str(root), ["endpoints:handler"])
        digests[f"{revision}_digest"] = snapshot_digest(root, ["endpoints.py", "main.py"])
    inputs = ReportInput(
        report_id="registration",
        provenance=ControlledProvenance(
            fixture_id="registration", description="registration", **digests
        ),
    )
    report = build_report(inputs, roots=roots, **analyses)
    for revision in report.revisions:
        [finding] = revision.findings
        assert finding.route.path == "/api/"
        assert {(r.file_path, r.start_line) for r in finding.route.registration_evidence} == {
            ("main.py", 3),
            ("main.py", 4),
            ("endpoints.py", 2),
        }


def test_inventory_digest_includes_empty_and_skipped_sources(tmp_path):
    data = setup(tmp_path)
    root = data[1]["base"]
    (root / "empty.py").write_bytes(b"")
    (root / "skipped.py").write_bytes(b"raise RuntimeError('source only')\n")
    data[2]["base"].project_graph.file_statuses.update(
        {str(root / "empty.py"): "empty", str(root / "skipped.py"): "skipped_file_cap"}
    )
    data[0].provenance.base_digest = snapshot_digest(root, ["main.py", "empty.py", "skipped.py"])
    report = build(data)
    assert report.revisions[0].partial
    assert any(
        u.category == "file_status" and u.reason == "skipped_file_cap" for u in report.uncertainties
    )


def test_source_payload_never_executes(tmp_path):
    data = setup(tmp_path)
    marker = tmp_path / "execution-marker"
    for revision, root in data[1].items():
        payload = root / "trap.py"
        payload.write_text(
            f"from pathlib import Path\nPath({str(marker)!r}).touch()\n"
            "raise RuntimeError('must only parse this source')\n"
        )
        data[2][revision] = analyze_route_impacts(str(root), ["main:helper"])
        setattr(
            data[0].provenance, f"{revision}_digest", snapshot_digest(root, ["main.py", "trap.py"])
        )
    assert build(data)
    assert not marker.exists()


def test_trusted_ancestor_alias_preserves_report_bytes(tmp_path):
    data = setup(tmp_path / "real")
    expected = canonical_json_bytes(build(data))
    alias = tmp_path / "alias"
    alias.symlink_to(tmp_path / "real", target_is_directory=True)
    aliased_roots = {revision: alias / revision for revision in ("base", "head")}
    aliased_analyses = {
        revision: analyze_route_impacts(str(root), ["main:helper", "main:handler"])
        for revision, root in aliased_roots.items()
    }
    assert (
        canonical_json_bytes(build_report(data[0], roots=aliased_roots, **aliased_analyses))
        == expected
    )


@pytest.mark.parametrize("mutation", ["range", "identity", "file"])
def test_contradictory_handler_evidence_fails_closed(tmp_path, mutation):
    data = setup(tmp_path)
    declaration = data[2]["head"].impact.impacts[0].route.declaration
    if mutation == "range":
        declaration.handler_line = declaration.handler_end_line = 1
    elif mutation == "identity":
        declaration.handler_id = "main:helper"
    else:
        other = data[1]["head"] / "other.py"
        other.write_bytes((data[1]["head"] / "main.py").read_bytes())
        declaration.file_path = str(other)
    with pytest.raises(IngestionError) as error:
        build(data)
    assert error.value.code == "report_evidence_invalid"
