"""Report boundaries reject contradictions without depending on the web layer."""

import pytest
from pydantic import ValidationError

from app.reporting.models import (
    AnalysisReport, ControlledProvenance, ControlledReference, ReportChange,
    ReportEdge, ReportFinding, ReportNode, ReportRoute, RevisionReport,
)


def ref(revision="base", **kwargs):
    return ControlledReference(fixture_id="case", revision=revision, file_path="main.py",
                               start_line=1, end_line=2, **kwargs)


def report(**kwargs):
    return AnalysisReport(report_id="case", provenance=ControlledProvenance(
        fixture_id="case", base_digest="a" * 64, head_digest="b" * 64, description="case"),
        revisions=[RevisionReport(revision="base"), RevisionReport(revision="head")], **kwargs)


def test_round_trip_and_independent_defaults():
    result = report()
    assert AnalysisReport.model_validate_json(result.model_dump_json()) == result
    result.changes.append(ReportChange(status="removed", symbol_id="main:f", kind="function",
                                       old=ref()))
    assert report().changes == []


@pytest.mark.parametrize("fields", [{"url": "https://github.com/x"}, {"commit_sha": "a" * 40}])
def test_controlled_references_have_no_github_fields(fields):
    with pytest.raises(ValidationError):
        ref(**fields)


def test_ranges_and_change_sides():
    with pytest.raises(ValidationError):
        ControlledReference(fixture_id="case", revision="base", file_path="../secret",
                            start_line=2, end_line=1)
    with pytest.raises(ValidationError):
        ReportChange(status="removed", symbol_id="main:f", kind="function", old=ref("head"))


def test_revision_and_fixture_identity():
    with pytest.raises(ValidationError):
        report(unmapped_changes=[ref().model_copy(update={"fixture_id": "other"})])
    with pytest.raises(ValidationError):
        RevisionReport(revision="head", nodes=[ReportNode(symbol_id="main:f", kind="function",
                                                          source=ref())])


def test_dangling_edges_and_paths():
    edge = ReportEdge(caller="main:f", callee="main:g", evidence=[ref()])
    with pytest.raises(ValidationError):
        RevisionReport(revision="base", edges=[edge])
    route = ReportRoute(app_id="main:app", handler_id="main:f", method="GET", path="/",
                        declaration=ref(), handler=ref())
    with pytest.raises(ValidationError):
        ReportFinding(changed_symbol="main:g", route=route,
                      symbols=["main:f", "main:g"], edges=[])
