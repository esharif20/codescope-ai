# Source-reviewed evaluation labels

Labels were authored from fixture source before running predictions. They are
reviewable truth, never generated or overwritten from analyser output. All Python
files are read as bytes and parsed; none are imported or executed. The cycle
fixture raises at module scope to guard against accidental execution.

The sample scope includes its fixture test as source. Constructors of local
classes count as edges. Repeated calls count once per caller/callee pair. External
framework constructors, registration/decorator calls outside functions and
builtins have no local target and are excluded from edge denominators.

`routes/users.py:14-15` binds `auth` to `AuthService` then calls `login`;
`tests/test_services.py:7-8` does the same with `svc`. Both are provable positive
relationships even when unsupported by the conservative resolver. The audit seed
reaches GET `/users/me` through `get_user -> AuthService.login -> BaseService.audit`.
Missing predictions remain false negatives; labels must not be weakened for recall.

Dynamic callbacks, getattr-derived handlers and parameter receivers have no
source-provable target. Each is separately source-located under
`adjudicated_unknowns`; these targets are excluded from truth denominators, not
counted as negative edges. Expected unresolved entries express implementation
uncertainty separately from source truth and may include known positives.

Each case declares explicit files and support scope. Only those bytes enter a
temporary root, retaining relative paths, with a shared SHA256 snapshot manifest.
Base/head use the same controlled source with hand-labelled hypothetical modified
seeds; this is not a real PR or Git revision. Edges and endpoint registrations are
sets, deduplicated across call sites, paths and seeds, scored separately per
revision. Precision is null without predictions; recall is null without truth.
Micro metrics recompute from summed counts; macro means ignore null values and
state their defined denominators. Empty negative cases remain visible.

These small controlled fixtures measure structural correctness only. They do not
establish completeness, runtime behaviour, performance, or improvement over another
method.

## Measured fixture results

First measured with `python -m app.reporting.evaluation --labels
../fixtures/report_evaluation/labels.json` from `backend/`. Both revisions have
identical results because their source snapshots are identical:

| Case | Edge TP / FP / FN | Endpoint TP / FP / FN | Unresolved calls |
| --- | --- | --- | --- |
| auth-positive | 10 / 0 / 2 | 2 / 0 / 0 | 7 |
| unsupported-audit | 10 / 0 / 2 | 0 / 0 / 1 | 7 |
| unrelated-callers | 10 / 0 / 2 | 0 / 0 / 0 | 7 |
| cycle-positive | 3 / 0 / 0 | 1 / 0 / 0 | 1 |
| unresolved-negative | 3 / 0 / 0 | 0 / 0 / 0 | 1 |

Pooled across five cases and two separately scored revisions, edge micro precision
is 1.0 and recall is 72/84 = 0.8571428571428571 (12 FN). Endpoint micro precision is
1.0 and recall is 6/8 = 0.75 (2 FN). Edge macro precision/recall are 1.0/0.9
(10 defined values each); endpoint macro precision is 1.0 (4 defined), recall is
2/3 (6 defined). Empty endpoint cases have null precision and recall; the missed
audit endpoint has null precision and zero recall. These repeated source cases
are not independent samples of real changes.

Both missing edges are the source-bound `login` receivers described above. The
audit path's missing route edge causes its endpoint FN. All expected unresolved
locations are retained as uncertainties. Four unknown relationship sites in the
sample and one callback site in the cycle fixture remain outside truth target
denominators, listed explicitly in each case. Sample reports retain partial
route-analysis diagnostics; no truncation is observed on these fixtures.
