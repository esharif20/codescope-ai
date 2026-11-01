"""Report HTTP contracts through raw ASGI and controlled local pipeline inputs."""

import asyncio
import json
from threading import Event
from uuid import uuid4

import pytest
from test_analysis_api import api as api
from test_analysis_api import call, payload, request

from app.ingestion import pipeline
from app.ingestion.models import AnalysisRequest, IngestionError
from app.ingestion.runtime import AnalysisRegistry
from app.ingestion.settings import Limits, Settings
from app.main import create_app
from app.reporting import demos


def report_path(identity):
    return f"/api/analyses/{identity}/report"


def test_retained_live_report_after_cleanup(api, tmp_path):
    app, calls, cleaned, registry = api
    identity = uuid4()
    assert call(app, method="POST", path="/api/analyses", body=payload(identity))[0] == 201
    assert cleaned == [True]
    # Retrieval must use retained evidence even after the source snapshots disappear.
    for source in tmp_path.glob("*/main.py"):
        source.unlink()
    status, data, _ = call(app, path=report_path(identity))
    assert status == 200
    assert data == registry.get_report(identity).model_dump(mode="json")
    assert data["schema_version"] == "1" and data["provenance"]["kind"] == "github"
    change = data["changes"][0]
    for side, sha in (("old", "b"), ("new", "c")):
        assert change[side]["source"]["url"] == (
            f"https://github.com/a/b/blob/{sha * 40}/main.py#L6-L7"
        )
    for revision, sha in zip(data["revisions"], ("b", "c"), strict=True):
        assert revision["nodes"] and revision["edges"] and len(revision["findings"]) == 1
        finding = revision["findings"][0]
        assert finding["symbols"] == ["main:route", "main:helper"]
        assert finding["edges"][0]["evidence"][0]["source"]["url"] == (
            f"https://github.com/a/b/blob/{sha * 40}/main.py#L5"
        )
    assert isinstance(data["uncertainties"], list) and isinstance(data["partial"], bool)
    assert calls == [True] and "github-secret" not in json.dumps(data)
    assert call(app, path=f"/api/demos/{identity}/report", headers=[])[0] == 404


@pytest.mark.parametrize("identity", ["not-a-uuid-SECRET", str(uuid4()), "auth-positive"])
@pytest.mark.parametrize("enabled", [False, True])
def test_live_boundary_precedes_report_validation(identity, enabled):
    settings = (
        Settings(allowed_repositories={"a/b"}, live_access_token="access")
        if enabled
        else Settings()
    )
    app = create_app(settings)
    status, data, _ = call(app, path=report_path(identity), headers=[])
    assert status == (401 if enabled else 503)
    assert data["error"]["code"] == ("unauthorized" if enabled else "live_analysis_disabled")
    assert "SECRET" not in json.dumps(data)
    if enabled:
        assert call(app, path=report_path("SECRET"))[0] == 422


def test_pending_running_failed_and_unknown_reports(api):
    app, calls, _, registry = api
    identity = uuid4()
    registry.reserve(AnalysisRequest(analysis_id=identity, pr_url="https://github.com/a/b/pull/1"))
    for stage in (None, "mapping"):
        if stage:
            registry.update(identity, stage)
        status, data, _ = call(app, path=report_path(identity))
        assert status == 409 and data["error"]["code"] == "report_not_ready"
    registry.fail(identity, IngestionError("internal_error", "Analysis could not complete.", 500))
    registry.release(identity)
    status, data, _ = call(app, path=report_path(identity))
    assert status == 409 and data["error"]["code"] == "report_unavailable"
    status, data, _ = call(app, path=report_path(uuid4()))
    assert status == 404 and data["error"]["code"] == "analysis_not_found"
    assert calls == []


@pytest.mark.parametrize("expired", [False, True])
def test_terminal_report_eviction_and_ttl(api, expired):
    now = [0.0]
    settings = Settings(
        allowed_repositories={"a/b"},
        live_access_token="access",
        limits=Limits(max_terminal_records=1, terminal_ttl_seconds=2),
    )
    registry = AnalysisRegistry(settings, clock=lambda: now[0])
    app = create_app(settings, registry, lambda *a, **k: object())
    first = uuid4()
    assert call(app, method="POST", path="/api/analyses", body=payload(first))[0] == 201
    assert call(app, path=report_path(first))[0] == 200
    if expired:
        now[0] = 2
    else:
        assert call(app, method="POST", path="/api/analyses", body=payload())[0] == 201
    assert call(app, path=report_path(first))[0] == 404


def test_concurrent_report_remains_not_ready_through_cleanup(api, monkeypatch):
    entered, proceed = Event(), Event()
    original = pipeline.fetch_snapshots
    from contextlib import contextmanager

    @contextmanager
    def paused_cleanup(*args, **kwargs):
        with original(*args, **kwargs) as pair:
            yield pair
            entered.set()
            assert proceed.wait(5)

    monkeypatch.setattr(pipeline, "fetch_snapshots", paused_cleanup)

    async def scenario():
        identity = uuid4()
        post = asyncio.create_task(request(api[0], "POST", "/api/analyses", payload(identity)))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            status, data, _ = await asyncio.wait_for(request(api[0], path=report_path(identity)), 2)
            assert status == 409 and data["error"]["code"] == "report_not_ready"
            assert api[2] == []
            assert (await request(api[0], "POST", "/api/analyses", payload()))[0] == 409
        finally:
            proceed.set()
            assert (await asyncio.wait_for(post, 5))[0] == 201
        assert (await request(api[0], path=report_path(identity)))[0] == 200
        assert api[2] == [True]

    asyncio.run(scenario())


@pytest.mark.parametrize("enabled", [False, True])
def test_public_frozen_demos_never_compute_or_reserve(monkeypatch, enabled):
    def forbidden(*args, **kwargs):
        pytest.fail("public demo attempted analysis, admission or network")

    settings = (
        Settings(allowed_repositories={"a/b"}, live_access_token="access")
        if enabled
        else Settings()
    )
    registry = AnalysisRegistry(settings)
    app = create_app(settings, registry, forbidden)
    monkeypatch.setattr(registry, "reserve", forbidden)
    monkeypatch.setattr(pipeline, "fetch_snapshots", forbidden)
    monkeypatch.setattr(pipeline, "analyze_route_impacts", forbidden)
    monkeypatch.setattr(demos, "_regenerated_bytes", forbidden)
    expected = demos.list_demos()
    assert call(app, path="/api/demos", headers=[])[0:2] == (
        200,
        {"schema_version": "1", "demos": expected},
    )
    for entry in expected:
        path = f"/api/demos/{entry['id']}/report"
        assert call(app, path=path, headers=[])[0:2] == (
            200,
            demos.get_demo_report(entry["id"]).model_dump(mode="json"),
        )
        assert call(app, method="POST", path=path, headers=[])[0] == 405
    assert call(app, method="POST", path="/api/demos", headers=[])[0] == 405
    assert not registry._records and registry._active is None


@pytest.mark.parametrize(
    "identity",
    [
        "unknown",
        str(uuid4()),
        "catalog.json",
        "..",
        "%2e%2e",
        "../../api/analyses/live",
        "auth-positive.json",
    ],
)
def test_public_unknown_and_traversal_ids_never_read_artifacts(monkeypatch, identity):
    def forbidden(*args, **kwargs):
        pytest.fail("unrecognized ID attempted file access")

    monkeypatch.setattr(demos, "_read", forbidden)
    assert call(create_app(Settings()), path=f"/api/demos/{identity}/report", headers=[])[0] == 404


@pytest.mark.parametrize("path", ["/api/demos", "/api/demos/auth-positive/report"])
def test_public_artifact_error_is_safe_503(monkeypatch, tmp_path, path):
    monkeypatch.setattr(demos, "_DEMO_ROOT", tmp_path / "SECRET-private-root")
    status, data, _ = call(create_app(Settings()), path=path, headers=[])
    assert status == 503 and data["error"]["code"] == "demo_unavailable"
    assert "SECRET" not in json.dumps(data)
