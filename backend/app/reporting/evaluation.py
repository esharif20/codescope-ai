"""Offline, exact-set evaluation against independently source-reviewed labels."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, Literal

from pydantic import Field, model_validator

from app.analysis.project_routes import analyze_route_impacts
from app.ingestion.models import RelativePath
from app.reporting.builder import build_report, canonical_json_bytes, snapshot_digest
from app.reporting.models import (
    AnalysisReport,
    Contract,
    ControlledProvenance,
    ControlledReference,
    ReportChange,
    ReportInput,
    Text,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ALLOWED_SOURCES = {
    "fixtures/sample_fastapi_repo": frozenset(
        {
            "__init__.py",
            "callers.py",
            "main.py",
            "routes/__init__.py",
            "routes/users.py",
            "services/__init__.py",
            "services/auth.py",
            "services/base.py",
            "tests/__init__.py",
            "tests/test_services.py",
        }
    ),
    "fixtures/report_evaluation": frozenset({"cycle_unresolved.py"}),
}
Positive = Annotated[int, Field(gt=0, strict=True)]


class SourceRange(Contract):
    file_path: RelativePath
    start_line: Positive
    end_line: Positive

    @model_validator(mode="after")
    def check_range(self):
        if self.end_line < self.start_line:
            raise ValueError("invalid source range")
        return self


class Seed(Contract):
    symbol_id: Text
    status: Literal["added", "modified", "removed"]
    kind: Literal["function", "method", "class", "nested_function"]
    old: SourceRange | None
    new: SourceRange | None


class Unknown(Contract):
    symbol_id: Text
    file_path: RelativePath
    line: Positive
    reason: Text


class Unresolved(Unknown):
    status: Literal["unresolved", "uncertain"]


class Case(Contract):
    case_id: Annotated[str, Field(pattern=r"^[a-z][a-z0-9-]{0,79}$")]
    fixture_root: RelativePath
    source_files: list[RelativePath] = Field(min_length=1)
    changed_symbols: list[Text] = Field(min_length=1)
    seed_changes: list[Seed] = Field(min_length=1)
    expected_edges: list[tuple[Text, Text]]
    expected_endpoints: list[tuple[Text, Text, Text, Text]]
    expected_unresolved: list[Unresolved]
    adjudicated_unknowns: list[Unknown]
    support_scope: Text
    rationale: Text

    @model_validator(mode="after")
    def check_scope(self):
        allowed = ALLOWED_SOURCES.get(self.fixture_root)
        if allowed is None or not set(self.source_files) <= allowed:
            raise ValueError("source outside fixed fixture allowlist")
        for values in (
            self.source_files,
            self.changed_symbols,
            self.expected_edges,
            self.expected_endpoints,
        ):
            if len(set(values)) != len(values):
                raise ValueError("duplicate label identity")
        seeds = [seed.symbol_id for seed in self.seed_changes]
        if len(set(seeds)) != len(seeds) or set(seeds) != set(self.changed_symbols):
            raise ValueError("seeds contradict changed symbols")
        locations = [s for seed in self.seed_changes for s in (seed.old, seed.new) if s]
        locations += [*self.expected_unresolved, *self.adjudicated_unknowns]
        if any(s.file_path not in self.source_files for s in locations):
            raise ValueError("label location outside declared source scope")
        # Reuse the report change-side validator before touching any source bytes.
        for seed in self.seed_changes:
            _report_change(self.case_id, seed)
        return self


class Labels(Contract):
    schema_version: Literal["1"]
    cases: list[Case] = Field(min_length=1)

    @model_validator(mode="after")
    def check_ids(self):
        ids = [case.case_id for case in self.cases]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate case ID")
        return self


def score_sets(expected: set[tuple[str, ...]], predicted: set[tuple[str, ...]]) -> dict:
    """Score unique identities, retaining exact errors and undefined denominators."""
    tp, fp, fn = expected & predicted, predicted - expected, expected - predicted
    return {
        "tp": [list(x) for x in sorted(tp)],
        "fp": [list(x) for x in sorted(fp)],
        "fn": [list(x) for x in sorted(fn)],
        "tp_count": len(tp),
        "fp_count": len(fp),
        "fn_count": len(fn),
        "expected_count": len(expected),
        "predicted_count": len(predicted),
        "precision": len(tp) / len(predicted) if predicted else None,
        "recall": len(tp) / len(expected) if expected else None,
    }


def _report_change(case_id: str, seed: Seed) -> ReportChange:
    def ref(revision, location):
        return (
            ControlledReference(fixture_id=case_id, revision=revision, **location.model_dump())
            if location
            else None
        )

    return ReportChange(
        symbol_id=seed.symbol_id,
        status=seed.status,
        kind=seed.kind,
        old=ref("base", seed.old),
        new=ref("head", seed.new),
    )


def _source_bytes(case: Case) -> dict[str, bytes]:
    result = {}
    for name in case.source_files:
        relative = f"{case.fixture_root}/{name}"
        cursor = REPOSITORY_ROOT
        for segment in relative.split("/"):
            cursor = cursor / segment
            if cursor.is_symlink():
                raise ValueError("symlink fixture source")
        cursor.resolve(strict=True).relative_to(REPOSITORY_ROOT.resolve(strict=True))
        result[name] = cursor.read_bytes()
    locations = [s for seed in case.seed_changes for s in (seed.old, seed.new) if s]
    locations += [*case.expected_unresolved, *case.adjudicated_unknowns]
    for location in locations:
        end = location.end_line if isinstance(location, SourceRange) else location.line
        if end > len(result[location.file_path].splitlines()):
            raise ValueError("label location exceeds source")
    return result


def build_case_report(case: dict) -> AnalysisReport:
    """Copy only declared source bytes and run the real shared report pipeline."""
    label = Case.model_validate(case)
    sources = _source_bytes(label)
    with TemporaryDirectory(prefix="codescope-evaluation-") as directory:
        root = Path(directory)
        for name, content in sources.items():
            destination = root / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(content)
        digest = snapshot_digest(root, label.source_files)
        inputs = ReportInput(
            report_id=label.case_id,
            provenance=ControlledProvenance(
                fixture_id=label.case_id,
                base_digest=digest,
                head_digest=digest,
                description="Controlled source snapshot with source-reviewed hypothetical seeds.",
            ),
            changes=[_report_change(label.case_id, seed) for seed in label.seed_changes],
        )
        analyses = {
            rev: analyze_route_impacts(
                str(root),
                [
                    seed.symbol_id
                    for seed in label.seed_changes
                    if getattr(seed, "old" if rev == "base" else "new") is not None
                ],
            )
            for rev in ("base", "head")
        }
        return build_report(inputs, **analyses, roots={"base": root, "head": root})


def _aggregate(scores: list[dict]) -> dict:
    tp, fp, fn = (sum(s[key] for s in scores) for key in ("tp_count", "fp_count", "fn_count"))
    macro = {}
    for metric in ("precision", "recall"):
        defined = [s[metric] for s in scores if s[metric] is not None]
        macro[metric] = sum(defined) / len(defined) if defined else None
        macro[f"{metric}_defined_count"] = len(defined)
    return {
        "micro": {
            "tp_count": tp,
            "fp_count": fp,
            "fn_count": fn,
            "expected_count": tp + fn,
            "predicted_count": tp + fp,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        },
        "macro": macro,
        "revision_case_count": len(scores),
    }


def evaluate_suite(labels_path: Path) -> dict:
    """Measure labels without modifying them, importing sources, or using network."""
    labels = Labels.model_validate(json.loads(labels_path.read_bytes()))
    cases = []
    scores = {"edges": [], "endpoints": []}
    for case in sorted(labels.cases, key=lambda value: value.case_id):
        report = build_case_report(case.model_dump(mode="json"))
        revisions = []
        for revision in report.revisions:
            edges = {(edge.caller, edge.callee) for edge in revision.edges}
            endpoints = {
                (f.route.app_id, f.route.handler_id, f.route.method, f.route.path)
                for f in revision.findings
            }
            uncertainties = [u for u in report.uncertainties if u.revision == revision.revision]
            unresolved = [
                u for u in uncertainties if u.category in {"unresolved_call", "uncertain_call"}
            ]
            actual_unresolved = {
                (
                    u.symbol_id,
                    u.source.file_path,
                    u.source.start_line,
                    "uncertain" if u.category == "uncertain_call" else "unresolved",
                )
                for u in unresolved
                if u.source
            }
            expected_unresolved = {
                (u.symbol_id, u.file_path, u.line, u.status) for u in case.expected_unresolved
            }
            # Unresolved checks are expectations, not a second ground-truth call graph.
            revisions.append(
                {
                    "revision": revision.revision,
                    "edges": score_sets(set(case.expected_edges), edges),
                    "endpoints": score_sets(set(case.expected_endpoints), endpoints),
                    "partial": revision.partial,
                    "uncertainties": [u.model_dump(mode="json") for u in uncertainties],
                    "unresolved_count": len(unresolved),
                    "unresolved_status_counts": dict(
                        sorted(
                            Counter(
                                "uncertain" if u.category == "uncertain_call" else "unresolved"
                                for u in unresolved
                            ).items()
                        )
                    ),
                    "missing_expected_unresolved": [
                        list(x) for x in sorted(expected_unresolved - actual_unresolved)
                    ],
                    "truncation_diagnostics": [
                        u.reason for u in uncertainties if u.category == "truncation"
                    ],
                }
            )
            for metric in scores:
                scores[metric].append(revisions[-1][metric])
        cases.append(
            {
                "case_id": case.case_id,
                "support_scope": case.support_scope,
                "rationale": case.rationale,
                "revisions": revisions,
                "adjudicated_unknowns": [u.model_dump() for u in case.adjudicated_unknowns],
                "excluded_unknown_target_count": len(case.adjudicated_unknowns),
                "excluded_constructs": (
                    "External/builtin targets and module-level registration/decorator calls."
                ),
                "partial": report.partial,
            }
        )
    return {
        "schema_version": "1",
        "cases": cases,
        "aggregates": {metric: _aggregate(values) for metric, values in scores.items()},
        "scope": (
            "Controlled fixtures only; identical base/head source, scored separately; "
            "no runtime or completeness claim."
        ),
        "excluded_denominators": (
            "Unknown dynamic targets, external/builtin calls and module-level registrations; "
            "unknown counts are per case, not multiplied by revision."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    encoded = canonical_json_bytes(evaluate_suite(arguments.labels))
    if arguments.output:
        arguments.output.write_bytes(encoded)
    sys.stdout.buffer.write(encoded)


if __name__ == "__main__":
    main()
