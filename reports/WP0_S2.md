# WP0 S2: Common code (contracts)

Date: 2026-10-19    Worker: sonnet (WP0)

## Goal of the step
Implement the contracts of ARCHITECTURE.md in `common/` (Evidence, Layer, DomainCombiner, MotionEstimate), metrics, calibration, evaluation harness, split helpers, test runner and tests.

## Acceptance rule (written in notes/WP0_foundation.md before any code ran)
1. All tests in tests/common/ pass via `python tests/run_tests.py`. 2. Tests cover: tie-safe threshold never exceeds budget (incl. heavy ties), combiner on synthetic layers, calibration monotone, ablation output shape, group split never shares a group. 3. Toy 3-layer domain through the harness gives JSON + table; false alarms on val normal <= budget by construction; combined AUC >= best single-layer AUC - 0.02. 4. Contract classes importable; no import from ../codes_v2; fixtures csv/json only.

## What was done
- `common/`: config, evidence, layer, combiner, motion, metrics, calibration, evaluate, splits, toy (synthetic domain for tests / example).
- `tests/run_tests.py` (v2 runner, now recursive: tests/**/test_*.py, optional path filter), `tests/common/test_common.py` (14 tests).
- `tools/WP0_toy_example.py` -> `results/WP0/toy_example.json` and `.md`.
- metrics.py copies classification_summary / binary_summary / pct from v2 and adds budget_threshold, false_alarm_rate, auc, detection_at_budget, detection_delay, merge_delays.
- No data used (synthetic only). No download. ../codes and ../codes_v2 untouched.

## Results (toy example, copied from results/WP0/toy_example.md; test = 4 unseen synthetic streams)
Budget 1.0% false alarms on validation normal data. Domain: toy_example.

| configuration | AUC | detection | false alarms | det alpha | det beta | det gamma | median delay (s) |
|---|---|---|---|---|---|---|---|
| all | 0.955 | 51.5% | 1.09% | 56.9% | 55.0% | 42.5% | 1.0 |
| only_toy.f1 | 0.742 | 26.9% | 0.99% | 73.1% | 0.0% | 7.5% | 1.5 |
| only_toy.f2 | 0.746 | 24.2% | 0.83% | 5.6% | 66.2% | 0.6% | 3.0 |
| only_toy.f3 | 0.654 | 21.2% | 1.04% | 0.6% | 1.2% | 61.9% | 0.0 |
| all_but_toy.f1 | 0.862 | 37.1% | 1.20% | 3.1% | 60.0% | 48.1% | 2.0 |
| all_but_toy.f2 | 0.815 | 40.4% | 1.15% | 60.6% | 0.6% | 60.0% | 1.0 |
| all_but_toy.f3 | 0.871 | 43.8% | 0.99% | 68.1% | 58.8% | 4.4% | 1.0 |

Tests: 14 passed, 0 failed. Combiner on the toy chose `max` (held-out-half detection: noisy_or 0.547, logistic 0.472, max 0.564; results/WP0/toy_example.json).
Acceptance: MET (1: 14/14 pass; 2: each listed property has a test; 3: combined AUC 0.955 vs best single 0.746; layer false alarms on test normal 0.83-1.04%, combined 1.09% (val budget 1%, test differs by sampling); 4: yes).

## Decisions (ARCHITECTURE.md ambiguous or silent; simplest reading, ARCHITECTURE.md not edited)
1. Layer subclass implements `raw_scores(samples) -> ndarray`; the base class does ECDF calibration, the tie-safe threshold and builds Evidence in `calibrate()` / `score()`. `Layer.score` takes a DataFrame (optional columns `t`, `sample_id`) or any sequence (index used). Layers needing fit-time state override `fit`.
2. Alarm of a layer = ECDF-calibrated score >= threshold, with the threshold set by `budget_threshold` on the calibrated validation-normal scores.
3. `budget_threshold`: k = floor(budget*n) alarms allowed; threshold = nextafter(k-th largest, +inf); tests include all-tied and tie-at-quantile cases.
4. Combiner inputs are `dict layer_name -> list[Evidence]` aligned by sample. `method="auto"` picks among noisy_or / logistic / max by detection at the budget on the held-out validation half, averaged over both directions (halves split by group with `group_halves`). Logistic model: fitted on half A, threshold from half B normal samples. Logistic features are `-log(1 - s + 1e-3)` (not raw s): with raw ECDF scores the top 1% is squeezed into [0.99, 1] and a linear model detected only 12% of toy attacks at the 1% budget vs 49% with this transform (found while writing the tests, before the final toy numbers; the test bound 0.4 was set after seeing this). Noisy_or / max thresholds use all validation normal samples.
5. Harness: `evaluate_domain(name, val, test, ...)` with `EvalSet(evidence, y, attack_type, group, t)`. Per-layer threshold is recomputed from validation normal scores (does not rely on the layer's own alarm flag). Ablation = only_<layer>, all, all_but_<layer> (the latter only when >= 3 layers); combiner refitted on validation each time. Delay = per consecutive attack segment per group, median over detected segments, plus detected fraction.
6. State leak (S1 item 8): `evaluate.score_groups(layer, {group: samples})` calls `reset()` before every group; tested.
7. Paths (S1 item 7): config.py has `DATASET_PATHS` for D01-D06 (KITTI in two places).
8. `tests/run_tests.py` made recursive (tests/<domain>/), as required by the layout; test modules are loaded under unique names.
9. `common/toy.py` is an addition (not in the WP list): synthetic data shared by tests and the example.

## Ablation row(s)
Toy domain only (table above). Real layers: later WPs.

## Problems, surprises, open questions
- Detection on the toy at a 1% budget is only ~51% by design (attack shifts of 2.5-3 sigma); not a quality claim.
- The ECDF calibration saturates at 1.0 above the largest validation normal score: layers whose attacks all exceed the validation normal range tie at 1.0 and rank information is lost inside a combiner (AUC of the combiner can then fall below the layer's raw AUC). Possible follow-up for WP owners: use raw scores for AUC, or add a tail extrapolation. Not changed (frozen contract: "fraction of normal samples below").
- Bash heredocs with apostrophes inside parentheses failed to parse here; used file-writing tools.

## Proposed next step
WP0 S3 (regression of the v2 GPS B2 rule through the harness), after review.
