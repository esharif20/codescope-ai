import shutil
from contextlib import contextmanager
from threading import Event, Thread
from uuid import uuid4

import pytest

from app.ingestion import pipeline
from app.ingestion.models import (
    AnalysisRequest,
    ChangedFile,
    IngestionError,
    PinnedPullRequest,
    PullRequestRef,
    SnapshotPair,
)
from app.ingestion.runtime import AnalysisRegistry
from app.ingestion.settings import Limits, Settings


@pytest.fixture
def setup_pipeline(tmp_path, monkeypatch):
    settings = Settings(allowed_repositories={"a/b"}, live_access_token="access")
    registry = AnalysisRegistry(settings)
    metadata = PinnedPullRequest(
        ref=PullRequestRef(owner="a", repo="b", number=1),
        title="test",
        base_repository="a/b",
        head_repository="a/b",
        target_base_sha="a" * 40,
        analysis_base_sha="b" * 40,
        head_sha="c" * 40,
        changed_files=1,
    )
    roots = [tmp_path / "base", tmp_path / "head"]
    for root in roots:
        root.mkdir()
        (root / "main.py").write_text(
            "from fastapi import FastAPI\napp = FastAPI()\n"
            '@app.get("/x")\ndef route():\n    return helper()\n'
            "def helper():\n    return 1\n"
        )
    (roots[1] / "main.py").write_text(
        (roots[1] / "main.py").read_text().replace("return 1", "return 2")
    )
    cleaned = []

    @contextmanager
    def snapshots(ref, client, config, *, check_budget, on_stage):
        on_stage("metadata")
        check_budget()
        on_stage("sources")
        try:
            yield SnapshotPair(
                metadata,
                *roots,
                [ChangedFile(old_path="main.py", new_path="main.py", status="modified")],
                [],
            )
        finally:
            # Admission must remain owned throughout cleanup, even after failure.
            with pytest.raises(IngestionError) as caught:
                registry.reserve(AnalysisRequest(analysis_id=uuid4(), pr_url="unused"))
            assert caught.value.code == "analysis_busy"
            for root in roots:
                shutil.rmtree(root)
            cleaned.append(True)

    monkeypatch.setattr(pipeline, "fetch_snapshots", snapshots)
    item = AnalysisRequest(analysis_id=uuid4(), pr_url="https://github.com/a/b/pull/1")
    return settings, registry, item, roots, cleaned


def run(setup):
    settings, registry, item, _, _ = setup
    return pipeline.run_analysis(item, registry, settings, client_factory=lambda *a, **kw: object())


def test_two_revisions_real_mapping_and_graphs(setup_pipeline):
    result = run(setup_pipeline)
    assert result.state == "complete"
    assert result.summary.affected_routes_base == result.summary.affected_routes_head == 1
    assert [(c.symbol_id, c.status) for c in result.summary.changed_symbols] == [
        ("main:helper", "modified")
    ]
    assert result.summary.changed_symbols[0].old.commit_sha == "b" * 40
    assert result.summary.changed_symbols[0].new.commit_sha == "c" * 40
    assert not result.summary.partial
    assert setup_pipeline[-1] == [True]
    assert all(not root.exists() for root in setup_pipeline[3])
    assert str(setup_pipeline[3][0]) not in result.model_dump_json()
    report = setup_pipeline[1].get_report(result.analysis_id)
    assert report.provenance.pull_request == result.revisions
    assert [change.symbol_id for change in report.changes] == ["main:helper"]
    assert [len(revision.findings) for revision in report.revisions] == [1, 1]
    assert report.revisions[1].findings[0].symbols == ["main:route", "main:helper"]
    assert str(setup_pipeline[3][0]) not in report.model_dump_json()


def test_removed_seeds_only_base_and_unrelated_has_no_routes(setup_pipeline):
    head = setup_pipeline[3][1] / "main.py"
    head.write_text(head.read_text().split("def helper")[0])
    result = run(setup_pipeline)
    assert result.summary.affected_routes_base == 1
    assert result.summary.affected_routes_head == 0
    assert result.summary.changed_symbols[0].status == "removed"
    report = setup_pipeline[1].get_report(result.analysis_id)
    assert report.changes[0].old.source.commit_sha == "b" * 40
    assert report.changes[0].new is None
    assert not report.revisions[1].findings


@pytest.mark.parametrize("failure", ["timeout", "exception"])
def test_fault_cleanup_no_partial_success(setup_pipeline, monkeypatch, failure):
    def fail(*a, **kw):
        if failure == "timeout":
            raise IngestionError("analysis_timeout", "Analysis timed out.", 504)
        raise RuntimeError("secret /private/source")

    monkeypatch.setattr(pipeline, "map_snapshot_changes", fail)
    result = run(setup_pipeline)
    assert result.state == ("timeout" if failure == "timeout" else "error")
    assert result.summary is None
    assert_report_unavailable(setup_pipeline)
    assert "secret" not in result.model_dump_json()
    assert setup_pipeline[-1] == [True]
    setup_pipeline[1].reserve(AnalysisRequest(analysis_id=uuid4(), pr_url="unused"))


def test_polling_while_work_is_active(setup_pipeline, monkeypatch):
    entered, proceed = Event(), Event()
    original = pipeline.map_snapshot_changes

    def pause(*a, **kw):
        entered.set()
        assert proceed.wait(5)
        return original(*a, **kw)

    monkeypatch.setattr(pipeline, "map_snapshot_changes", pause)
    thread = Thread(target=run, args=(setup_pipeline,))
    thread.start()
    try:
        assert entered.wait(5)
        assert setup_pipeline[1].get(setup_pipeline[2].analysis_id).stage == "mapping"
    finally:
        proceed.set()
        thread.join(5)
    assert not thread.is_alive()


@pytest.mark.parametrize(
    "stage", ["metadata", "sources", "mapping", "impact_base", "impact_head", "publication"]
)
def test_deadline_at_each_stage_prevents_success(setup_pipeline, monkeypatch, stage):
    registry, item = setup_pipeline[1:3]

    class FakeDeadline:
        def __init__(self, seconds):
            self.graph_checks = 0

        def remaining_seconds(self):
            return 0

        def check(self):
            current = registry.get(item.analysis_id).stage
            if current == "impact_head":
                self.graph_checks += 1
            expired = current == stage
            # Final check after consumer context (cleanup marker already present).
            if stage == "publication":
                expired = bool(setup_pipeline[-1])
            if expired:
                raise IngestionError("analysis_timeout", "Analysis timed out.", 504)

    monkeypatch.setattr(pipeline, "Deadline", FakeDeadline)
    result = run(setup_pipeline)
    assert result.state == "timeout"
    assert result.summary is None
    assert_report_unavailable(setup_pipeline)
    if stage not in {"metadata", "sources"}:
        assert setup_pipeline[-1] == [True]


def test_unrelated_change_and_source_is_never_executed(setup_pipeline):
    roots = setup_pipeline[3]
    for index, root in enumerate(roots):
        with (root / "main.py").open("a") as source:
            source.write(
                f'\nraise RuntimeError("NEVER EXECUTE")\ndef unrelated():\n    return {index}\n'
            )
        # Restore identical helper spans so only the unrelated function changes.
        path = root / "main.py"
        path.write_text(path.read_text().replace("return 2", "return 1"))
    result = run(setup_pipeline)
    assert result.state == "complete"
    assert result.summary.affected_routes_base == result.summary.affected_routes_head == 0
    assert [c.symbol_id for c in result.summary.changed_symbols] == ["main:unrelated"]
    assert all(not r.findings for r in setup_pipeline[1].get_report(result.analysis_id).revisions)


def test_budget_callback_reaches_graph_and_route_phases(tmp_path):
    from app.analysis.project_graph import build_project_graph
    from app.analysis.project_routes import analyze_route_impacts

    (tmp_path / "x.py").write_text("def f():\n    return 1\n")
    for operation in (
        lambda cb: build_project_graph(str(tmp_path), check_budget=cb),
        lambda cb: analyze_route_impacts(str(tmp_path), [], check_budget=cb),
    ):
        checks = []
        operation(lambda: checks.append(True))
        assert len(checks) >= 10

        def stop():
            raise IngestionError("analysis_timeout", "Analysis timed out.", 504)

        with pytest.raises(IngestionError):
            operation(stop)


def test_partial_diagnostics_redact_expressions_and_outside_paths(setup_pipeline, monkeypatch):
    from app.analysis.route_models import RouteDiagnostic

    original = pipeline.analyze_route_impacts

    def analyze(root, seeds, **kwargs):
        result = original(root, seeds, **kwargs)
        result.partial = True
        result.routes.diagnostics.extend(
            [
                RouteDiagnostic(
                    file_path=str(setup_pipeline[3][0] / "main.py"),
                    line=2,
                    expression="SECRET_SOURCE()",
                    reason="unsupported_receiver",
                ),
                RouteDiagnostic(
                    file_path="/private/credentials",
                    line=1,
                    expression="TOKEN",
                    reason="secret reason /private/root",
                ),
            ]
        )
        return result

    monkeypatch.setattr(pipeline, "analyze_route_impacts", analyze)
    result = run(setup_pipeline)
    assert result.summary.partial
    assert "base:main.py:2:unsupported_receiver" in result.summary.diagnostics
    assert "SECRET" not in result.model_dump_json()
    assert "/private" not in result.model_dump_json()
    report = setup_pipeline[1].get_report(result.analysis_id)
    assert report.partial
    assert any(u.category == "invalid_evidence" for u in report.uncertainties)
    assert "SECRET" not in report.model_dump_json()
    assert "/private" not in report.model_dump_json()


def test_added_and_renamed_identity_seeds_head_only(setup_pipeline):
    head = setup_pipeline[3][1] / "main.py"
    head.write_text(head.read_text().replace("helper", "replacement"))
    result = run(setup_pipeline)
    assert [(c.symbol_id, c.status) for c in result.summary.changed_symbols] == [
        ("main:helper", "removed"),
        ("main:replacement", "added"),
        ("main:route", "modified"),
    ]
    assert result.summary.affected_routes_base == result.summary.affected_routes_head == 1
    report = setup_pipeline[1].get_report(result.analysis_id)
    assert sorted((c.symbol_id, c.status) for c in report.changes) == [
        (c.symbol_id, c.status) for c in result.summary.changed_symbols
    ]


def assert_report_unavailable(setup):
    with pytest.raises(IngestionError) as caught:
        setup[1].get_report(setup[2].analysis_id)
    assert (caught.value.code, caught.value.http_status) == ("report_unavailable", 409)


@pytest.mark.parametrize("stage", ["assembly", "cleanup"])
def test_report_not_visible_until_assembly_and_cleanup_finish(setup_pipeline, monkeypatch, stage):
    entered, proceed = Event(), Event()
    original = pipeline.build_report if stage == "assembly" else shutil.rmtree

    def pause(*args, **kwargs):
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    if stage == "assembly":
        monkeypatch.setattr(pipeline, "build_report", pause)
    else:
        monkeypatch.setattr(shutil, "rmtree", pause)
    thread = Thread(target=run, args=(setup_pipeline,))
    thread.start()
    try:
        assert entered.wait(5)
        registry, item = setup_pipeline[1:3]
        assert registry.get(item.analysis_id).state == "running"
        with pytest.raises(IngestionError) as caught:
            registry.get_report(item.analysis_id)
        assert (caught.value.code, caught.value.http_status) == ("report_not_ready", 409)
        with pytest.raises(IngestionError) as busy:
            registry.reserve(AnalysisRequest(analysis_id=uuid4(), pr_url="unused"))
        assert busy.value.code == "analysis_busy"
    finally:
        proceed.set()
        thread.join(5)
    assert not thread.is_alive()
    assert registry.get(item.analysis_id).state == "complete"
    assert registry.get_report(item.analysis_id).report_id == str(item.analysis_id)
    assert all(not root.exists() for root in setup_pipeline[3])


@pytest.mark.parametrize("stage", ["assembly", "cleanup", "publication"])
def test_report_fault_never_publishes(setup_pipeline, monkeypatch, stage):
    def fail(*args, **kwargs):
        raise RuntimeError("secret /private/source")

    if stage == "assembly":
        monkeypatch.setattr(pipeline, "build_report", fail)
    elif stage == "publication":
        monkeypatch.setattr(setup_pipeline[1], "complete", fail)
    else:
        original = shutil.rmtree

        def cleanup(path, *args, **kwargs):
            original(path, *args, **kwargs)
            if path == setup_pipeline[3][1]:
                fail()

        monkeypatch.setattr(shutil, "rmtree", cleanup)
    result = run(setup_pipeline)
    assert result.state == "error"
    assert result.error.code == "internal_error"
    assert "secret" not in result.model_dump_json()
    assert all(not root.exists() for root in setup_pipeline[3])
    assert_report_unavailable(setup_pipeline)
    setup_pipeline[1].reserve(AnalysisRequest(analysis_id=uuid4(), pr_url="unused"))


@pytest.mark.parametrize("limit", ["max_report_bytes", "max_summary_bytes"])
def test_serialized_limits_prevent_report_publication(setup_pipeline, limit):
    settings = setup_pipeline[0].model_copy(update={"limits": Limits(**{limit: 100})})
    setup_pipeline[1]._limits = settings.limits
    result = pipeline.run_analysis(
        setup_pipeline[2], setup_pipeline[1], settings, client_factory=lambda *a, **kw: object()
    )
    assert result.state == "error"
    assert result.error.code == "result_limit_exceeded"
    assert setup_pipeline[-1] == [True]
    assert_report_unavailable(setup_pipeline)


def test_renamed_file_retains_distinct_pinned_paths(setup_pipeline, monkeypatch):
    original = pipeline.fetch_snapshots
    head = setup_pipeline[3][1]
    (head / "main.py").rename(head / "renamed.py")

    @contextmanager
    def renamed(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            pair.files = [ChangedFile(old_path="main.py", new_path="renamed.py", status="renamed")]
            yield pair

    monkeypatch.setattr(pipeline, "fetch_snapshots", renamed)
    result = run(setup_pipeline)
    assert result.state == "complete"
    report = setup_pipeline[1].get_report(result.analysis_id)
    assert {c.old.source.file_path for c in report.changes if c.old} == {"main.py"}
    assert {c.new.source.file_path for c in report.changes if c.new} == {"renamed.py"}


def test_publication_validation_failure_after_cleanup_keeps_report_private(
    setup_pipeline, monkeypatch
):
    original = pipeline.build_report

    def inconsistent(*args, **kwargs):
        report = original(*args, **kwargs)
        report.report_id = str(uuid4())
        return report

    monkeypatch.setattr(pipeline, "build_report", inconsistent)
    result = run(setup_pipeline)
    assert result.state == "error"
    assert result.error.code == "report_evidence_invalid"
    assert setup_pipeline[-1] == [True]
    assert_report_unavailable(setup_pipeline)


def test_assembly_timeout_is_cooperative_and_cleans_sources(setup_pipeline, monkeypatch):
    original = pipeline.build_report

    def expire(*args, **kwargs):
        checks = []

        def timeout():
            checks.append(True)
            assert all(root.exists() for root in setup_pipeline[3])
            if len(checks) == 4:
                raise IngestionError("analysis_timeout", "Analysis timed out.", 504)

        kwargs["check_budget"] = timeout
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "build_report", expire)
    result = run(setup_pipeline)
    assert result.state == "timeout"
    assert setup_pipeline[-1] == [True]
    assert_report_unavailable(setup_pipeline)
