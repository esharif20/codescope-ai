"""Offline, independent-truth structural scoring regressions."""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.reporting.builder import canonical_json_bytes
from app.reporting.evaluation import build_case_report, evaluate_suite, score_sets

LABELS = Path(__file__).resolve().parents[2] / "fixtures/report_evaluation/labels.json"


def test_exact_sets_and_undefined_metrics():
    score = score_sets({("A",), ("B",)}, {("A",), ("C",)})
    assert score == {
        "tp": [["A"]], "fp": [["C"]], "fn": [["B"]],
        "tp_count": 1, "fp_count": 1, "fn_count": 1,
        "expected_count": 2, "predicted_count": 2, "precision": 0.5, "recall": 0.5,
    }
    assert score_sets(set(), set())["precision"] is None
    assert score_sets(set(), set())["recall"] is None
    assert score_sets({("A",)}, set())["recall"] == 0
    assert score_sets(set(), {("A",)})["precision"] == 0


@pytest.fixture(scope="module")
def suite():
    return evaluate_suite(LABELS)


def test_known_misses_and_negative_cases_stay_visible(suite):
    cases = {c["case_id"]: c for c in suite["cases"]}
    for case in cases.values():
        assert [r["revision"] for r in case["revisions"]] == ["base", "head"]
        assert case["support_scope"]
        for revision in case["revisions"]:
            assert revision["unresolved_count"] > 0
    audit = cases["unsupported-audit"]["revisions"][0]
    assert audit["endpoints"]["fn"] == [
        ["main:app", "routes.users:get_user", "GET", "/users/me"]
    ]
    assert ["routes.users:get_user", "services.auth:AuthService.login"] in audit["edges"]["fn"]
    assert cases["auth-positive"]["revisions"][0]["endpoints"]["tp_count"] == 2
    for name in ("unrelated-callers", "unresolved-negative"):
        endpoints = cases[name]["revisions"][0]["endpoints"]
        assert endpoints["tp_count"] == endpoints["fp_count"] == endpoints["fn_count"] == 0
        assert endpoints["precision"] is endpoints["recall"] is None
    cycle = cases["cycle-positive"]["revisions"][0]
    assert cycle["edges"]["tp_count"] == 3
    assert cycle["endpoints"]["tp_count"] == 1


def test_aggregation_recomputes_counts_and_defined_denominators(suite):
    for metric in ("edges", "endpoints"):
        scores = [r[metric] for c in suite["cases"] for r in c["revisions"]]
        micro = suite["aggregates"][metric]["micro"]
        tp, fp, fn = (sum(s[k] for s in scores) for k in ("tp_count", "fp_count", "fn_count"))
        assert micro["precision"] == tp / (tp + fp)
        assert micro["recall"] == tp / (tp + fn)
        for name in ("precision", "recall"):
            values = [s[name] for s in scores if s[name] is not None]
            macro = suite["aggregates"][metric]["macro"]
            assert macro[f"{name}_defined_count"] == len(values)
            assert macro[name] == sum(values) / len(values)


@pytest.mark.parametrize("mutation", ["duplicate", "traversal", "absolute", "unknown_root", "extra", "duplicate_source"])
def test_invalid_labels_rejected(tmp_path, mutation):
    data = json.loads(LABELS.read_text())
    case = data["cases"][0]
    if mutation == "duplicate":
        data["cases"].append(copy.deepcopy(case))
    elif mutation == "traversal":
        case["source_files"][0] = "../secrets.py"
    elif mutation == "absolute":
        case["source_files"][0] = "/tmp/secrets.py"
    elif mutation == "unknown_root":
        case["fixture_root"] = "backend"
    elif mutation == "extra":
        case["unexpected"] = True
    else:
        case["source_files"].append(case["source_files"][0])
    path = tmp_path / "labels.json"
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError):
        evaluate_suite(path)


def test_source_guard_controlled_provenance_and_inventory():
    case = json.loads(LABELS.read_text())["cases"][3]
    assert "raise RuntimeError" in (LABELS.parent / "cycle_unresolved.py").read_text()
    report = build_case_report(case)
    assert report.provenance.kind == "controlled"
    assert report.provenance.base_digest == report.provenance.head_digest
    assert {n.source.file_path for r in report.revisions for n in r.nodes} == {"cycle_unresolved.py"}
    assert all(u.source.file_path == "cycle_unresolved.py" for u in report.uncertainties if u.source)


def test_symlink_sources_rejected(tmp_path, monkeypatch):
    import app.reporting.evaluation as module

    case = json.loads(LABELS.read_text())["cases"][3]
    root = tmp_path / case["fixture_root"]
    root.mkdir(parents=True)
    (root / "cycle_unresolved.py").symlink_to(LABELS.parent / "cycle_unresolved.py")
    monkeypatch.setattr(module, "REPOSITORY_ROOT", tmp_path)
    with pytest.raises(ValueError, match="symlink"):
        build_case_report(case)


def test_cli_uses_exact_shared_canonical_bytes(tmp_path, suite):
    output = tmp_path / "evaluation.json"
    command = [sys.executable, "-m", "app.reporting.evaluation", "--labels", str(LABELS)]
    first = subprocess.run([*command, "--output", str(output)], capture_output=True, check=True)
    second = subprocess.run(command, capture_output=True, check=True)
    assert first.stdout == second.stdout == output.read_bytes() == canonical_json_bytes(suite)
    assert first.stdout.endswith(b"\n") and not first.stdout.endswith(b"\n\n")
