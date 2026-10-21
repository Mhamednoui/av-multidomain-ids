# WP1 GPS brief (state after S7, 2026-10-21)

## Current state
- Done and APPROVED: S0 D15 download, S1 stream + attacks, S2 L1 rules, S3 L2a EKF/NIS, S4 L2b/L2c CUSUM + scale, S5 L2d LiDAR odometry + MotionEstimate. S6 L2e map matching APPROVED as a negative result (out of the default stack). S7 (L3 normal-only residual model, L4 retrained C2): REVIEW. Next: S8 (combiner, full ablation, external tests, M1-GPS).
- Best single layers on KITTI test (LODO, run-level drift/accel/jump/freeze/Doppler/meaconing): cusum_dr 70/61/100/84/70/61 at FA 1.64%; B2 39/43/100/89/41/49 at FA 1.58%. S5 stack harness AUC 0.922, FA 1.15%.
- L2d (lid_z_1) adds nothing to the S4 stack alone; L2e (map_dist) adds nothing to the S5 stack and has FA 4.11% on test (OSM per-road offset). Keep L2e out of the default stack (supervisor decides).
- Slow drift 0.2-0.5 m/s within 30 s (target 60% at <= 1% FA): NOT reached (best 43% cusum_ekf, test runs have no full 30 s window; untestable on KITTI test).

- S7 (default stack = B2 + L1 + L2a + L2b + 6 instantaneous L2d, harness AUC 0.924, FA 1.11%): L3 (isolation forest A|if1024 on the physics residual vector) test FA 0.51%, AUC 0.875, Doppler 76 / meaconing 64% run-level; L4 (v2 C2 retrained, 4 attacks) FA 0.82%, AUC 0.888, freeze 96%. Neither adds to the stack (AUC +0.001 / +0.005, max row gain 0.6 pt). L4 does not transfer (AV-GPS FA 61% at the KITTI threshold) and has no independent speed on the UAV. Shuffled-label control AUC 0.553 (bound 0.55 missed by 0.003, detection nil).
- Default stack for S8 (supervisor): B2 + L1 + L2a + L2b + L2d; L2e optional soft evidence; L3 optional low-FA evidence; L4 = v2 baseline row.

## Binding decisions
- LODO policy (2026-10-19): thresholds = tie-safe 1% budget on pooled clean scores of the 16 train+val drives (gps/lodo.py); parameters tuned on data are tuned on the 16 drives only (small pre-registered grid) or nested per fold, or frozen beforehand. Test drives touched once per step. Report LODO and val-only side by side.
- The 75% target (Doppler/meaconing run-level >= 75%, S5 C5) is KEPT as the goal; it is not reached (best 70/61%). Do not lower it silently.
- Drivable OSM classes fixed before S6 (see notes/WP1_gps.md S6); footway/path/track excluded.
- Stream split: TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; the rest train. UAV flights are all test.
- Honest numbers: report failures plainly (RULES 5.9).

## Pitfalls
- KITTI OXTS is RTK: receiver noise (AR(1) phi 0.9, sigma 1 m) is added in the stream; KITTI frames are ~0.1032 s apart (resample on real timestamps).
- Per-second tests are noise-limited (0.45 m per axis after differencing): small Doppler spoofs (<1 m/s) are seen in only ~28% of runs.
- Pooled FA hides per-drive spread: always read the worst-drive FA (map_dist 27.7% on dev drive 0027, 25.7% on test 0028 at the pooled threshold).
- CUSUM latch: false freezes/glitches make CUSUM scores run away (cusum_lidar FA 10%).
- First ICP pair needs a multi-start (no previous motion). Dev-only tuning, test once.
- Python: tf env only; run tools from codes_v3/ with -u -W ignore; features for S5/S6 are cached (results/WP1/cache/ for odometry; stream pickle in the temp folder).

## File map
- gps/: stream.py (data + attacks), l1.py, ekf.py, cusum.py, lidar_odom.py, lidar_dr.py, map_match.py, lodo.py, learned.py (L3 residual models, C2 features / XGBoost search, ScoreColumnLayer).
- tests/gps/test_*.py (all run via tests/run_tests.py).
- tools/WP1_S<k>_*.py: dev (16 drives), test (one pass), tables, report per step; WP1_S4_lib.py is the shared helper (summarize, J, delays).
- results/WP1/S<k>_*.json|md; S<k>_tables.md = readable tables; S<k>_acceptance.json = verdicts; S6_diag.json post-hoc FA by drive.
- reports/WP1_S0..S7.md, notes/WP1_gps.md (full log, acceptance rules), workpackages/WP1_gps.md.
- MotionEstimate (LiDAR, 1 Hz) for WP6: results/WP1/S5_motion_estimates.json.

## S7 pitfalls
- Learned layers read precomputed score columns (ScoreColumnLayer): out-of-fold scores on dev rows, final-model scores on test rows. The LODO threshold must come from the out-of-fold scores, never from in-sample scores.
- L3 strictly nested selection uses leave-two-out fits (fit without d and e scores both); MinCovDet hangs on exactly duplicated rows (the first fix of every run, k = 0): excluded from fitting.
- tools/WP1_S7_dev.py takes ~20 min (MCD 2.5 min per candidate, 15 x 15 XGBoost fits per L4 variant), WP1_S7_test.py ~17 min. Feature frames cached in results/WP1/cache/s7_feat_*.pkl.
- Dev runs are short (10-100 s): runs have few rows, so L4 FA per drive is noisy (drive 0027 9.5% at the pooled threshold).
