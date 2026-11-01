"""Frozen demo artifacts preserve controlled evidence and exact serialization."""

import hashlib
import json
import subprocess
import sys

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
