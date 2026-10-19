# Notes WP0 Foundation

## 2026-10-19 S1 start (worker sonnet)

Acceptance rule (written before any check was run), from workpackages/WP0_foundation.md S1:
1. `git log` shows the commit `[WP0.S1] repository, docs`.
2. Package versions in the tf env equal RULES.md section 4 (Python 3.9.21, numpy 1.23.5,
   pandas 2.2.3, xgboost 2.1.4, scikit-learn 1.6.1, scipy 1.13.1) and every package of
   requirements.txt imports.
3. The report lists doc issues (or says "none").
Extra checks: .gitignore patterns work; requirements.txt identical to ../codes_v2/requirements.txt;
nothing in ../codes or ../codes_v2 modified; no download in this step.

2026-10-19 S1 results: git init (branch main, local); .gitignore, requirements.txt (copy of v2),
locks/.gitkeep created. tf env versions all match RULES.md section 4 (Python 3.9.21, numpy
1.23.5, pandas 2.2.3, xgboost 2.1.4, sklearn 1.6.1, scipy 1.13.1) and the 5 other pinned
packages import with the pinned versions. Doc review: 9 items listed in reports/WP0_S1.md
(main ones: v2 B2 numbers exist at row level and run level, S3 must pick; KITTI split ids not in
WP0; downloads policy differs between RULES/DATASETS and ORCHESTRATOR). No download. Disk 52 GB free.
Acceptance rule items 1-3: met (commit hash in report/log).

## 2026-10-19 S2 start (worker sonnet)

Acceptance rule (written before any code ran), from workpackages/WP0_foundation.md S2:
1. All tests in tests/common/ pass via `python tests/run_tests.py` (tf env).
2. Tests cover: tie-safe threshold never exceeds budget (incl. heavy ties); combiner on synthetic
   layers (noisy_or, logistic, max; combined beats the weakest layer and reason lists fired layers);
   calibration monotone; ablation output shape (each alone, all, all-but-one); group split never
   shares a group across sides.
3. A toy 3-layer synthetic domain run through common/evaluate.py produces a JSON + markdown table
   shown in the report; on the toy, the false-alarm rate on val normal <= budget (1%) by construction
   and the combined AUC >= best single-layer AUC - 0.02.
4. All contract classes importable; no import from ../codes_v2; test fixtures csv/json only.

2026-10-19 S2 results: common/ (config, evidence, layer, combiner, motion, metrics, calibration,
evaluate, splits, toy), tests/run_tests.py (recursive), tests/common/test_common.py (14 tests, all
pass), tools/WP0_toy_example.py -> results/WP0/toy_example.{json,md}. Toy: combined AUC 0.955 vs best
single layer 0.746; layer FA on test normal 0.83-1.04%, combined 1.09%. Acceptance items 1-4: met.
Decisions (details in reports/WP0_S2.md): Layer.raw_scores template; logistic combiner uses
-log(1-s+1e-3) features (raw ECDF scores gave 12% vs 49% toy detection); auto method selection on
group halves; score_groups resets per group. Pitfall: ECDF scores saturate at 1.0 above the max
validation normal score (ties inside combiner); logged as open question.

2026-10-19 S2b: ECDF tail fix in common/calibration.py (strictly increasing tail above the max validation normal, scale stored). 16 tests pass. Toy combined detection unchanged (51.5%, AUC 0.955). See reports/WP0_S2.md "S2b".
