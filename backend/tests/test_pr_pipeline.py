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
from app.ingestion.settings import Settings


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


def test_removed_seeds_only_base_and_unrelated_has_no_routes(setup_pipeline):
    head = setup_pipeline[3][1] / "main.py"
    head.write_text(head.read_text().split("def helper")[0])
    result = run(setup_pipeline)
    assert result.summary.affected_routes_base == 1
    assert result.summary.affected_routes_head == 0
    assert result.summary.changed_symbols[0].status == "removed"


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
