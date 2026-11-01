"""Checked-in controlled demos; regeneration is an explicit offline CLI action."""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Literal

from pydantic import Field

from app.ingestion.models import IngestionError
from app.reporting.builder import canonical_json_bytes
from app.reporting.models import AnalysisReport, Contract, Digest, Text

_DEMO_ROOT = Path(__file__).resolve().parent / "demo_reports"
_DEMO_FILES = {
    "auth-positive": "auth-positive.json",
    "unrelated-negative": "unrelated-negative.json",
}
_REPORT_LIMIT = 2097152
_REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
_CASES = {"auth-positive": "auth-positive", "unrelated-negative": "unrelated-callers"}
_DESCRIPTIONS = {
    "auth-positive": (
        "Authentication helper change",
        "A controlled authentication helper change reaches two registered API routes.",
    ),
    "unrelated-negative": (
        "Unrelated caller change",
        "A controlled unrelated caller change has no verified affected API routes.",
    ),
}


class _Entry(Contract):
    id: Text
    title: Text
    description: Text
    provenance_kind: Literal["controlled"]
    report_sha256: Digest


class _Catalog(Contract):
    schema_version: Literal["1"]
    entries: list[_Entry] = Field(min_length=2, max_length=2)


def _unavailable() -> IngestionError:
    return IngestionError("demo_unavailable", "Demo is unavailable.", 503)


def _read(path: Path) -> bytes:
    if path.is_symlink():
        raise ValueError("symlink artifact")
    with path.open("rb") as handle:
        raw = handle.read(_REPORT_LIMIT + 1)
    if len(raw) > _REPORT_LIMIT:
        raise ValueError("artifact too large")
    return raw


def _catalog() -> _Catalog:
    raw = _read(_DEMO_ROOT / "catalog.json")
    catalog = _Catalog.model_validate_json(raw)
    if raw != canonical_json_bytes(catalog) or [e.id for e in catalog.entries] != list(_DEMO_FILES):
        raise ValueError("invalid catalog")
    if any(
        (entry.title, entry.description) != _DESCRIPTIONS[entry.id] for entry in catalog.entries
    ):
        raise ValueError("unreviewed catalog metadata")
    return catalog


def _load(entry: _Entry) -> AnalysisReport:
    raw = _read(_DEMO_ROOT / _DEMO_FILES[entry.id])
    report = AnalysisReport.model_validate_json(raw)
    if (
        raw != canonical_json_bytes(report)
        or hashlib.sha256(raw).hexdigest() != entry.report_sha256
        or report.report_id != entry.id
        or report.provenance.kind != "controlled"
        or report.provenance.fixture_id != _CASES[entry.id]
    ):
        raise ValueError("invalid artifact")
    return report


def list_demos() -> list[dict]:
    """Return fresh catalog metadata after validating every advertised artifact."""
    try:
        catalog = _catalog()
        for entry in catalog.entries:
            _load(entry)
        return [entry.model_dump(exclude={"report_sha256"}) for entry in catalog.entries]
    except (OSError, ValueError, KeyError):
        raise _unavailable() from None


def get_demo_report(demo_id: str) -> AnalysisReport:
    """Load only exact allowlisted IDs; caller input never forms a path."""
    if demo_id not in _DEMO_FILES:
        raise IngestionError("demo_not_found", "Demo was not found.", 404)
    try:
        entry = next(entry for entry in _catalog().entries if entry.id == demo_id)
        return _load(entry)
    except (OSError, ValueError, KeyError, StopIteration):
        raise _unavailable() from None


def _regenerated_bytes() -> dict[str, bytes]:
    # Scanner/evaluation imports belong only to this explicit offline operation.
    from app.reporting.evaluation import Labels, build_case_report

    labels = Labels.model_validate_json(
        (_REPOSITORY_ROOT / "fixtures/report_evaluation/labels.json").read_bytes()
    )
    cases = {case.case_id: case for case in labels.cases}
    artifacts = {}
    entries = []
    for demo_id, filename in _DEMO_FILES.items():
        report = build_case_report(cases[_CASES[demo_id]].model_dump(mode="json"))
        report.report_id = demo_id
        report.provenance.description = (
            "Controlled changed-symbol scenarios, not real GitHub PR analyses. "
            "Base and head use the same source-reviewed fixture snapshot with hypothetical seeds."
        )
        raw = canonical_json_bytes(report)
        if len(raw) > _REPORT_LIMIT:
            raise ValueError("artifact too large")
        artifacts[filename] = raw
        title, description = _DESCRIPTIONS[demo_id]
        entries.append(
            {
                "id": demo_id,
                "title": title,
                "description": description,
                "provenance_kind": "controlled",
                "report_sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    artifacts["catalog.json"] = canonical_json_bytes({"schema_version": "1", "entries": entries})
    return artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--regenerate", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args(argv)
    try:
        artifacts = _regenerated_bytes()
        if arguments.check:
            if any((_DEMO_ROOT / name).read_bytes() != raw for name, raw in artifacts.items()):
                raise ValueError("artifact drift")
        else:
            _DEMO_ROOT.mkdir(parents=True, exist_ok=True)
            for name, raw in artifacts.items():
                (_DEMO_ROOT / name).write_bytes(raw)
    except (OSError, ValueError, KeyError):
        print("Demo artifact verification failed.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
