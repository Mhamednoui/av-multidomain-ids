# WP1 GPS brief (state after S8 = M1-GPS candidate, 2026-10-21)

## Current state
- S0-S7 APPROVED (S6 and S7 as negative results). S8 (combiner, full ablation, external tests, frozen GPS domain output): REVIEW, milestone M1-GPS PARTIAL. Milestone report: `reports/M1_GPS.md` (self-contained). Acceptance verdicts: `results/WP1/S8_acceptance.json`; tables: `results/WP1/S8_tables.md`.
- Default stack (16 layers): B2 + L1 (5 kinematic rules + Doppler-vs-position) + L2a ekf_nis + L2b (cusum_ekf, cusum_dr with L2c) + 6 instantaneous L2d. Out (optional ablation rows only): L2e map, cusum_lidar, L3, L4.
- Calibration: nested LODO over the 15 dev drives with runs (CUSUM configuration, per-layer ECDF + 1% threshold, combiner method / fit / threshold all inside the folds; combiner halves by drive). Receiver noise model re-estimated per fold: unchanged (q_acc 0.1 in 15/15). Combiner = `noisy_or_log` (parameter-free), fitted WITHOUT the Doppler / meaconing rows (zero-shot on them).
- KITTI test (one pass, 7 drives, 490 runs): clean-run FA 1.83% [0.78, 2.76 over drives] (rule 1.5%: NOT met; nested dev 1.24%), run-level drift 76 / accel 63 / jump 100 / freeze 89 / Doppler 69 / meaconing 61, mean 76.2% [59, 90 drives; 72, 80 runs], AUC 0.895. B2 60.0% at 1.58%: +16.2 points [+10, +22]. Best single layer cusum_dr 74.5% (+1.7 [-1, +4] not significant). Targets Doppler / meaconing >= 75%: NOT met (kept). Slow drift 0.2-0.5 m/s within 30 s: UNTESTABLE on KITTI.
- Ablation: no single layer essential (max drop 1.2 points), weak kinematic rules dilute slightly, optional layers add +0.2 to +1.0 (noise). Shuffled-label control (L4, 5 seeds) mean AUC 0.44 (bound 0.55 met).
- External: UAV spoofing flight combined alarm 118.0003 s, pre-onset 3/118 = 2.54% (bound 2%: NOT met; EKF-CUSUM alone 0/118); AV-GPS: nothing usable (placeholder sessions; combined FA 17.5%, AUC 0.883 = permutation-null 95th percentile).

## Frozen GPS domain output (for WP6 / WP7)
- `gps/domain.py`: `GPSDomain.load("results/WP1/frozen_gps")` (domain.json + calibrators.npz, 1.9 MB); `prepare(stream_df)` adds B2 / L1 / LiDAR feature columns (whole runs, time order, 1 Hz; needs odometry speed, compass heading, IMU, LiDAR odometry columns lid_*); `score_arrays(df)` -> (statistic, score, alarm); `score(df, with_layers=True)` -> Evidence(domain "gps", layer "combined", name "gps.combined", score in [0,1] = ECDF of S = -sum log(1 - s_i) on dev normals, alarm = score >= 0.98997, reason, details {statistic, method, layer_scores}, sample_id "run/k") + per-layer Evidence.
- MotionEstimate: LiDAR (source "lidar", body frame, 1 Hz, sigma model) from `gps.lidar_odom.motion_estimates` (sample `results/WP1/S5_motion_estimates.json`) = the independent witness; GPS (source "gps") from `gps.domain.gps_motion_estimates` = the receiver's CLAIM (displacement from reported position rotated by compass heading, sigma 0.45 m/s), to be compared against CAN wheel speed / LiDAR.
- Fixtures: `results/WP1/frozen_gps/example_evidence_doppler_spoof_run.json`, `example_gps_motion_estimates.json`. Reload check: `results/WP1/S8_freeze.json`. Expect FA 1.2-1.8% on unseen drives at the 1% setting; delays median 0-4 s per attack.
- Subsets without odometry (UAV): L1 receiver rules, EKF NIS, EKF-CUSUM only (no B2, dead-reckoning CUSUM, LiDAR).

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
- gps/: stream.py (data + attacks), l1.py, ekf.py, cusum.py, lidar_odom.py, lidar_dr.py, map_match.py, lodo.py, learned.py (L3 residual models, C2 features / XGBoost search, ScoreColumnLayer), b2.py (B2 inside gps/), stack.py (matrix-level LODO pieces, MatrixCombiner, noisy_or_log, RunIndex), domain.py (GPSDomain, prepare, gps_motion_estimates).
- tests/gps/test_*.py (all run via tests/run_tests.py).
- tools/WP1_S<k>_*.py: dev (16 drives), test (one pass), tables, report per step; WP1_S4_lib.py is the shared helper (summarize, J, delays).
- results/WP1/S<k>_*.json|md; S<k>_tables.md = readable tables; S<k>_acceptance.json = verdicts; S6_diag.json post-hoc FA by drive.
- reports/WP1_S0..S8.md, reports/M1_GPS.md (milestone), reports/REQUEST_WP1_combiner_noisy_or.md, notes/WP1_gps.md (full log, acceptance rules), workpackages/WP1_gps.md.
- MotionEstimate (LiDAR, 1 Hz) for WP6: results/WP1/S5_motion_estimates.json.

## S8 pitfalls
- common `noisy_or` saturates at exactly 1.0 with many correlated layers (0 alarms): use the log form (gps/stack.py noisy_or_log); request in reports/REQUEST_WP1_combiner_noisy_or.md.
- Combiner halves must be split by DRIVE (S4-S7 harness used run ids). A combiner fitted with the Doppler / meaconing rows inflates them (+17 / +10 points on dev): fit without them.
- Pipeline check: `tools/WP1_S8_check.py` (dev) and `regression_vs_S7` in S8_kitti.json prove the score matrix equals the Layer pipeline; any new tool must keep passing them.
- Test drive 0005 is short (154 scans): it alone gives 4.98% FA; interpret pooled test FA with the drive-cluster interval.
- results/WP1/cache/s8_raw.pkl is rebuilt by tools/WP1_S8_scores.py (~4 min); the KITTI stream pickle lives in the temp folder (WP1_S4_lib.kitti_stream).
- tools: WP1_S8_scores -> _check -> _dev -> _test (once) -> _control, _noise, _freeze, _external -> _tables.

## S7 pitfalls
- Learned layers read precomputed score columns (ScoreColumnLayer): out-of-fold scores on dev rows, final-model scores on test rows. The LODO threshold must come from the out-of-fold scores, never from in-sample scores.
- L3 strictly nested selection uses leave-two-out fits (fit without d and e scores both); MinCovDet hangs on exactly duplicated rows (the first fix of every run, k = 0): excluded from fitting.
- tools/WP1_S7_dev.py takes ~20 min (MCD 2.5 min per candidate, 15 x 15 XGBoost fits per L4 variant), WP1_S7_test.py ~17 min. Feature frames cached in results/WP1/cache/s7_feat_*.pkl.
- Dev runs are short (10-100 s): runs have few rows, so L4 FA per drive is noisy (drive 0027 9.5% at the pooled threshold).
