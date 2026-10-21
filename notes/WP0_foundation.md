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

## 2026-10-19 S3 start (worker sonnet)

Acceptance rule (written before any code ran), from workpackages/WP0_foundation.md S3 + supervisor note:
1. Data: same KITTI tracks as v2 (23 drives, same rng order: one default_rng(42) consumed in
   sorted(SCENE) order, 10 phases, runs [none, drift, accel_drift, jump, freeze] x reps), same split
   (TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; TRAIN the other 13). Row/run counts must
   equal v2 json (test 7910 rows / 350 runs; train 23859 / 1080; val 2850 / 150).
2. The B2 rule (dr_resid_10 > thr or still_gps_moving_imu) is a v3 Layer (kind physics) calibrated through
   Layer.calibrate (ECDF + tie-safe budget_threshold, 1%) on the same normal rows v2 used (train+val normal
   rows: v2's choice, kept to reproduce; it differs from the v3 val-only protocol, so a val-only variant is
   also reported as information, not as the acceptance number).
3. MATCH = all of these within 0.01 percentage points (1e-4 absolute) of
   ../codes_v2/results/gps_kitti_external.json key B2_dead_reckoning_rule: false_alarm_rate_clean_runs 0.0158;
   row-level detection_by_attack (drift 0.336, accel 0.458, jump 0.719, freeze 0.866); run-level detected
   (0.386, 0.429, 1.000, 0.886); all_test_rows tp/fp/fn/tn exactly (1770/67/1151/4922); raw-equivalent
   threshold 6.658 m (to 3 decimals).
4. If anything differs: find the exact cause (seed, ordering, tie handling, interpolation) and report it;
   no tuning to match. The test set is scored once (the v3-protocol variant is computed in the same run,
   fixed in advance).

2026-10-19 S3 results: tools/WP0_regression.py (B2Layer + copied v2 data/attack code), results/WP0/regression_b2.json (+ harness and val-only variants), tests/common/test_regression_b2.py (19 tests pass in total). Data counts identical to v2 (test 7910/350 runs). Every alarm-level number identical to v2 B2: FA clean 0.015803, row detection 0.3364/0.4582/0.7194/0.8658, run detected 0.3857/0.4286/1.0/0.8857, tp/fp/fn/tn 1770/67/1151/4922, median delays 5/6/0/1. Threshold 6.658872 (v3, order statistic) vs 6.657975 (v2, np.quantile interpolation between 6.655780 and 6.658872): no test row in between, so no decision differs; v2 still-rule base was 0. Acceptance items 1,2,4 met; item 3 met except the 3-decimal threshold (explained, definition difference). Val-only variant (info): thr 6.789, FA 1.45%, AUC 0.862, detections within 1 pp of v2. Report: reports/WP0_S3.md.

## 2026-10-21 S4 start (worker sonnet): combiner noisy_or log form
Acceptance rule (written before any code ran), from the WP1 request + supervisor decision:
Design: S = -sum_i log1p(-clip(s_i, 0, 1-1e-16)) (= -log prod(1-s_i)); Evidence score = S / (S + n_layers), in [0,1), strictly increasing in S, so same ranking as 1 - prod(1 - s_i) and no float saturation (the old 1 - exp(-S) form would still tie). Method name, inputs, outputs unchanged; threshold still from budget_threshold on the same score (calibration path unchanged). Output VALUES change (monotone transform), ranks do not.
(a) Random non-saturated inputs: Spearman(new, old) = 1.0 and identical alarm sets at any threshold t_old mapped through the transform (and at the budget threshold fitted separately on each).
(b) 16 correlated layers near 1.0: new score has no ties at the top (old has), tie-safe threshold gives normal FA <= 1% and > 0 alarms where old gave 0.
(c) Full test suite passes. (d) tests/common/test_regression_b2.py unchanged and passing.
(e) Frozen GPS (gps/domain.py, results/WP1/frozen_gps/) reproduces its test scores exactly; state whether it uses common noisy_or (it uses gps.stack.noisy_or_log, so expected independent).
