"""Hermetic HTTP contract tests using raw ASGI, without sockets or HTTP clients."""

import asyncio
import json
from contextlib import contextmanager
from threading import Event
from uuid import uuid4

import pytest

from app.ingestion import pipeline
from app.ingestion.github import fail
from app.ingestion.models import (
    ChangedFile,
    IngestionError,
    PinnedPullRequest,
    PullRequestRef,
    SnapshotPair,
)
from app.ingestion.runtime import AnalysisRegistry
from app.ingestion.settings import Settings
from app.main import create_app


async def request(app, method="GET", path="/health", body=b"", headers=None, chunks=None):
    messages = []
    parts = list(chunks if chunks is not None else [body])

    async def receive():
        if parts:
            return {"type": "http.request", "body": parts.pop(0), "more_body": bool(parts)}
        return {"type": "http.disconnect"}

    async def send(message):
        messages.append(message)

    scope = dict(
        type="http",
        asgi={"version": "3.0"},
        http_version="1.1",
        method=method,
        scheme="http",
        path=path,
        raw_path=path.encode(),
        query_string=b"",
        root_path="",
        server=("test", 80),
        client=("test", 123),
        headers=headers
        if headers is not None
        else [(b"authorization", b"Bearer access"), (b"content-type", b"application/json")],
    )
    await app(scope, receive, send)
    start = next(m for m in messages if m["type"] == "http.response.start")
    data = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    return start["status"], json.loads(data), dict(start["headers"])


def call(app, **kwargs):
    return asyncio.run(request(app, **kwargs))


def payload(analysis_id=None, url="https://github.com/a/b/pull/1"):
    return json.dumps({"analysis_id": str(analysis_id or uuid4()), "pr_url": url}).encode()


@pytest.fixture
def api(tmp_path, monkeypatch):
    settings = Settings(
        allowed_repositories={"a/b"}, live_access_token="access", github_token="github-secret"
    )
    registry = AnalysisRegistry(settings)
    calls, cleaned = [], []
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

    def client(*args, **kwargs):
        calls.append(True)
        return object()

    @contextmanager
    def snapshots(ref, client, config, *, check_budget, on_stage):
        on_stage("metadata")
        roots = [tmp_path / "base", tmp_path / "head"]
        for i, root in enumerate(roots):
            root.mkdir(exist_ok=True)
            (root / "main.py").write_text(
                'from fastapi import FastAPI\napp = FastAPI()\n@app.get("/x")\n'
                "def route():\n    return helper()\ndef helper():\n"
                f"    return {i}\n"
            )
        on_stage("sources")
        try:
            yield SnapshotPair(
                metadata,
                *roots,
                [ChangedFile(old_path="main.py", new_path="main.py", status="modified")],
                [],
            )
        finally:
            cleaned.append(True)

    monkeypatch.setattr(pipeline, "fetch_snapshots", snapshots)
    return create_app(settings, registry, client), calls, cleaned, registry


def test_health_disabled_and_no_network():
    app = create_app(Settings(), client_factory=lambda *a, **k: pytest.fail("network"))
    assert call(app, headers=[])[0:2] == (200, {"status": "ok"})
    assert call(app, method="POST", path="/api/analyses", body=payload())[0:2] == (
        503,
        {
            "error": {
                "code": "live_analysis_disabled",
                "message": "Live analysis is currently disabled.",
                "retry_after_seconds": None,
            }
        },
    )


def test_success_links_duplicate_and_unknown(api):
    app, calls, cleaned, _ = api
    identity = uuid4()
    status, data, _ = call(app, method="POST", path="/api/analyses", body=payload(identity))
    assert status == 201 and data["state"] == "complete"
    assert data["summary"]["affected_routes_base"] == data["summary"]["affected_routes_head"] == 1
    change = data["summary"]["changed_symbols"][0]
    assert change["old"]["url"] == f"https://github.com/a/b/blob/{'b' * 40}/main.py#L6-L7"
    assert change["new"]["url"] == f"https://github.com/a/b/blob/{'c' * 40}/main.py#L6-L7"
    assert call(app, path=f"/api/analyses/{identity}")[0:2] == (200, data)
    assert call(app, path=f"/api/analyses/{uuid4()}")[0] == 404
    assert call(app, method="POST", path="/api/analyses", body=payload(identity))[0] == 409
    assert calls == [True] and cleaned == [True]
    assert "github-secret" not in json.dumps(data)


@pytest.mark.parametrize(
    "authorization",
    [None, b"Bearer wrong", b"Bearer github-secret", b"Basic access", b"Bearer \xff"],
)
@pytest.mark.parametrize("method", ["POST", "GET"])
def test_authentication_before_body_or_network(api, authorization, method):
    app, calls, _, _ = api
    headers = [] if authorization is None else [(b"authorization", authorization)]
    path = "/api/analyses" if method == "POST" else f"/api/analyses/{uuid4()}"
    status, data, _ = call(app, method=method, path=path, headers=headers, body=b"SECRET")
    assert status == 401 and data["error"]["code"] == "unauthorized"
    assert calls == [] and "SECRET" not in json.dumps(data)


@pytest.mark.parametrize(
    "body,expected",
    [
        (b"SECRET", 422),
        (b"[]", 422),
        (b"null", 422),
        (b"\xffSECRET", 422),
        (payload(url="https://evil.example/SECRET"), 422),
        (payload(url="https://github.com/unapproved/repo/pull/1"), 403),
        (b'{"analysis_id":"SECRET","pr_url":"SECRET"}', 422),
        (b"{" + b" " * 8192, 413),
    ],
)
def test_invalid_input_no_admission_or_network(api, body, expected):
    app, calls, _, _ = api
    status, data, _ = call(app, method="POST", path="/api/analyses", body=body)
    assert status == expected
    assert "SECRET" not in json.dumps(data) and not calls


def test_chunked_cap_and_content_type(api):
    app = api[0]
    assert call(app, method="POST", path="/api/analyses", chunks=[b" " * 4096] * 3)[0] == 413
    for content in (b"text/plain", b"application/jsonp", b"application/json; charset=latin1"):
        assert (
            call(
                app,
                method="POST",
                path="/api/analyses",
                body=payload(),
                headers=[(b"authorization", b"Bearer access"), (b"content-type", content)],
            )[0]
            == 415
        )
    assert not api[1]


@pytest.mark.parametrize(
    "code,expected",
    [
        ("github_not_found", 404),
        ("repository_not_allowed", 403),
        ("unsupported_repository", 403),
        ("github_rate_limited", 429),
        ("github_authentication", 502),
        ("github_permission_denied", 502),
        ("github_unavailable", 502),
        ("github_invalid_response", 502),
        ("resource_limit", 413),
        ("pr_changed", 409),
        ("analysis_timeout", 504),
    ],
)
def test_terminal_http_mapping_and_polling(api, monkeypatch, code, expected):
    def fail_mapping(*args, **kwargs):
        error = fail(code)
        if code == "github_rate_limited":
            error.retry_after_seconds = 17
        raise error

    monkeypatch.setattr(pipeline, "map_snapshot_changes", fail_mapping)
    identity = uuid4()
    status, data, headers = call(
        api[0], method="POST", path="/api/analyses", body=payload(identity)
    )
    assert status == expected and data["error"]["code"] == code
    assert data["state"] == ("timeout" if code == "analysis_timeout" else "error")
    assert call(api[0], path=f"/api/analyses/{identity}")[0:2] == (200, data)
    assert api[2] == [True]
    if code == "github_rate_limited":
        assert headers[b"retry-after"] == b"17"


@pytest.mark.parametrize(
    "code,message",
    [
        ("diff_limit_exceeded", "Source diff exceeds processing limits."),
        ("mapping_limit_exceeded", "Changed source exceeds mapping limits."),
    ],
)
def test_mapping_limits_return_413_and_preserve_terminal_status(api, monkeypatch, code, message):
    def fail_mapping(*args, **kwargs):
        raise IngestionError(code, message, 422)

    monkeypatch.setattr(pipeline, "map_snapshot_changes", fail_mapping)
    identity = uuid4()
    status, data, _ = call(api[0], method="POST", path="/api/analyses", body=payload(identity))
    assert status == 413
    assert data["state"] == "error" and data["stage"] == "finished"
    assert data["summary"] is None
    assert data["error"] == {"code": code, "message": message, "retry_after_seconds": None}
    assert call(api[0], path=f"/api/analyses/{identity}")[0:2] == (200, data)
    assert api[2] == [True]


def test_unexpected_error_redacted(api, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("github-secret /private/root SECRET")

    monkeypatch.setattr(pipeline, "map_snapshot_changes", broken)
    status, data, _ = call(api[0], method="POST", path="/api/analyses", body=payload())
    assert status == 502
    assert all(secret not in json.dumps(data) for secret in ("github-secret", "/private", "SECRET"))


def test_real_concurrent_get_observes_running_post_and_busy(api, monkeypatch):
    entered, proceed = Event(), Event()
    original = pipeline.map_snapshot_changes

    def pause(*args, **kwargs):
        entered.set()
        assert proceed.wait(5)
        return original(*args, **kwargs)

    monkeypatch.setattr(pipeline, "map_snapshot_changes", pause)

    async def scenario():
        identity = uuid4()
        post = asyncio.create_task(request(api[0], "POST", "/api/analyses", payload(identity)))
        try:
            assert await asyncio.to_thread(entered.wait, 5)
            status, data, _ = await asyncio.wait_for(
                request(api[0], path=f"/api/analyses/{identity}"), 2
            )
            assert status == 200 and data["state"] == "running" and data["stage"] == "mapping"
            assert (await request(api[0]))[0] == 200
            assert (await request(api[0], "POST", "/api/analyses", payload()))[0] == 409
            assert api[1] == [True]
        finally:
            proceed.set()
            result = await asyncio.wait_for(post, 5)
        assert result[0] == 201

    asyncio.run(scenario())
