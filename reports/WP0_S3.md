# WP0 S3: Regression, reproduce the v2 GPS B2 result through v3

Date: 2026-10-19    Worker: sonnet (WP0)

## Goal of the step
Wrap the v2 dead-reckoning rule (B2, `../codes_v2/gps/kitti_external.py`) as a v3 Layer, run it on the same KITTI tracks and split through the v3 harness, and match `B2_dead_reckoning_rule` of `../codes_v2/results/gps_kitti_external.json`, or explain any difference.

## Acceptance rule (written in notes/WP0_foundation.md before any code ran)
1. Same data: row/run counts equal v2 (test 7910/350, train 23859/1080, val 2850/150), same rng order, same split. 2. B2 as a v3 Layer calibrated with Layer.calibrate (ECDF + tie-safe 1% threshold) on v2's normal rows (train+val). 3. Match within 0.01 pp: false alarms on clean runs, row-level and run-level detection per attack, tp/fp/fn/tn exactly, raw-equivalent threshold 6.658 (3 decimals). 4. Any difference: find the cause, no tuning.

## What was done
- `tools/WP0_regression.py`: copied data loading, receiver noise, attack injection, dead-reckoning residual and v2 `evaluate` metrics (header says so); `B2Layer(Layer)` (kind physics, raw score = dr_resid_10, rows with still_gps_moving_imu get a huge score so the OR rule is one score). Scored run by run with `score_groups` (reset per run). Harness `evaluate_domain` run on the same layer.
- `tests/common/test_regression_b2.py` (3 tests); full suite 19 passed.
- Outputs: `results/WP0/regression_b2.json` (comparison block `comparison_with_v2`), `regression_b2_harness.{json,md}`, `regression_b2_val_only.{json,md}`.
- Data: 23 KITTI drives, split TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; TRAIN the other 13. Same seed: one `default_rng(42)` consumed in `sorted(SCENE)` order. Nothing in ../codes or ../codes_v2 modified.

## Results (from results/WP0/regression_b2.json, key `comparison_with_v2`)
| quantity | v2 | v3 | match |
|---|---|---|---|
| rows test/train/val; runs | 7910/23859/2850; 350/1080/150 | identical | yes |
| false alarms, clean test runs | 0.015803 | 0.015803 | yes |
| row detection drift / accel_drift / jump / freeze | 0.3364 / 0.4582 / 0.7194 / 0.8658 | identical to 6 digits | yes |
| run detected drift / accel / jump / freeze | 0.3857 / 0.4286 / 1.0000 / 0.8857 | identical | yes |
| run median delay (s) | 5 / 6 / 0 / 1 | identical | yes |
| all test rows tp / fp / fn / tn | 1770 / 67 / 1151 / 4922 | identical | yes |
| threshold (m, raw equivalent) | 6.657975 | 6.658872 | differs by 0.0009 m (see below) |

Acceptance: MET for every alarm-level number (exact). The only item that is not equal to 3 decimals is the threshold in metres; it is a definition difference with no effect on any decision (below). So M0's regression is reproduced.

## Cause of the threshold difference (checked, not tuned)
v2 `threshold_at` uses `np.quantile(score, 0.99)`, which linearly interpolates between the two order statistics 6.655780 and 6.658872 (n = 14830 calibration rows, position 14680.71) and gives 6.657975. v3 `budget_threshold` returns the next float above the (k+1)-th largest value, k = floor(0.01 n) = 148, i.e. the order statistic 6.658872 (rule: alarm if raw > 6.658872, at most 1% alarms, tie-safe). No test row has a score in (6.657975, 6.658872] (counted), so the alarms are identical. The ECDF calibration is monotone (strictly increasing tail from S2b), so `calibrated >= thr` is equivalent to `raw > 6.658872` (`raw_equiv_threshold`, tested). The still rule (`still_gps_moving_imu`) fired on 0 calibration rows, so v2's "base" subtraction (0.01 - base) is 0 and the two budget definitions coincide. Seed, ordering, tie handling in the data: no difference.

## Information only: v3 protocol (calibration on the 3 VAL drives' normal rows, not on train+val)
v2 sets the B2 threshold on train+val normal rows (14830 rows); RULES 5.2 says validation. Variant (results/WP0/regression_b2_val_only.json): threshold 6.789 m, false alarms clean runs 1.45%, row detection drift 32.7 / accel 45.6 / jump 71.5 / freeze 86.5 %, run detected 0.371 / 0.429 / 1.000 / 0.886, AUC 0.862, tp/fp/fn/tn 1758/60/1163/4929. Close to v2: the rule has no learned parameters, so the choice of normal rows barely matters.

Harness table (val-only variant, copied from `regression_b2_val_only.md`; one layer, so "all" = the layer):

| configuration | AUC | detection | false alarms | det accel_drift | det drift | det freeze | det jump | median delay (s) |
|---|---|---|---|---|---|---|---|---|
| all | 0.862 | 60.2% | 1.20% | 45.6% | 32.7% | 86.5% | 71.5% | 1.0 |
| only_gps.dr_resid_10 | 0.862 | 60.2% | 1.20% | 45.6% | 32.7% | 86.5% | 71.5% | 1.0 |

With the v2 calibration rows the harness gives AUC 0.862 and test-normal false alarms 1.34%.

## Ablation row(s)
Single layer (B2 dead reckoning): AUC 0.862, detection 60.6% of attack rows at 1.58% false alarms on clean runs (v2 calibration). Test false alarms are above the 1% budget because the normal rows of the test drives differ from train+val (same as in v2); not tuned.

## Problems, surprises, open questions
- The test set was scored in one run that also produced the val-only variant (both fixed beforehand); nothing was re-run or chosen on test.
- The 1.58% (vs 1% budget) false-alarm rate on test is a real drive-to-drive shift in the residual, inherited from v2; WP1 should treat it as a baseline, not a target.
- Windows scratch script for the interpolation check lived in the session scratchpad (not part of the repo).

## Proposed next step
M0 closed after review. WP1 S0 and the other domain WPs can start.
