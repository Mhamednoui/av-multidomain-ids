# WP0 Foundation

Goal: everything the parallel work packages share: git, common code implementing the
contracts of ARCHITECTURE.md, the evaluation harness, the test runner, and a proof that the
harness reproduces a v2 number exactly. Runs alone, before any other WP.

Owns: `common/`, `tests/common/`, `tests/run_tests.py`, `tools/WP0_*`, `results/WP0/`,
`notes/WP0_foundation.md`, `reports/WP0_*`, `.gitignore`, `requirements.txt`.

## Steps

### S1 Repository and environment
- `git init` in codes_v3 (local only, no remote). `.gitignore`: `__pycache__/`, `*.pyc`,
  `results/*/logs/`, `results/*/cache/`, `*.pkl`, `*.npz`, model files > 50 MB, `locks/*.lock`.
- `requirements.txt`: copy `../codes_v2/requirements.txt` (pinned, incl. scipy 1.13.1).
- Check the tf environment imports everything (print versions into the report).
- Read every doc of codes_v3; list contradictions or gaps in the report (do not edit the
  supervisor's docs; propose fixes).
- First commit `[WP0.S1] repository, docs`.
- Acceptance: git log shows the commit; versions match RULES.md section 4; report lists doc issues (or "none").

### S2 Common code (contracts)
- `common/config.py` (paths, SEED, budgets), `common/evidence.py` (Evidence),
  `common/layer.py` (Layer base class), `common/combiner.py` (DomainCombiner: noisy_or,
  logistic, max; tie-safe calibration; group-aware validation halves),
  `common/motion.py` (MotionEstimate), `common/metrics.py` (copy v2 metrics + `budget_threshold`
  with np.nextafter + detection at budget + AUC + delay), `common/calibration.py` (empirical-CDF
  score calibration), `common/evaluate.py` (harness: per-layer + combined + ablation -> JSON
  + markdown table), `common/splits.py` (group split helpers, save/load split lists).
- `tests/run_tests.py` (copy v2 runner) + `tests/common/` covering: tie-safe threshold never
  exceeds the budget; combiner on synthetic layers; calibration monotone; ablation output shape;
  group split never puts one group on both sides.
- Acceptance: all tests pass; a toy example (synthetic 3-layer domain) in the report shows the
  harness output table.

### S3 Regression: reproduce one v2 result through v3
- Wrap the v2 GPS dead-reckoning rule (B2 in `../codes_v2/gps/kitti_external.py`) as a v3
  Layer (copy the code into `tools/WP0_regression.py` or `common/` test fixtures, not into gps/),
  run the harness on the same KITTI tracks and split, and show the same false-alarm rate
  (1.58%) and detection per attack type as `../codes_v2/results/gps_kitti_external.json`
  (B2_dead_reckoning_rule), or explain any difference.
- Split (same as v2 and WP1 S1): TEST drives 0001 0005 0095 0039 0079 0028 0052; VAL drives
  0011 0035 0027; TRAIN = the other 13 KITTI raw drives used by v2.
- Numbers to match (all from `B2_dead_reckoning_rule` in the v2 json; orchestrator decision
  2026-10-19): threshold_m 6.658; false_alarm_rate_clean_runs 0.0158; row-level
  detection_by_attack (drift 0.336, accel_drift 0.458, jump 0.719, freeze 0.866); run_level
  detected (drift 0.386, accel_drift 0.429, jump 1.000, freeze 0.886); all_test_rows tp/fp/fn/tn.
- Acceptance: numbers match v2 to 0.01 percentage points. This closes M0.

## Pitfalls from v2
- Base Python 3.13 writes numpy-2 pickles the tf env cannot read: always the tf env.
- Python heredocs in Git Bash mangle backslashes: write scripts to files.

## Progress
(worker updates this section)
