# WP1 S5: L2d LiDAR odometry (point-to-plane ICP) as an independent motion witness, MotionEstimate

Date: 2026-10-20    Worker: sonnet (WP1)

## Goal of the step
Build LiDAR odometry from consecutive KITTI velodyne scans (numpy + scipy cKDTree), validate it against the OXTS ground truth, use the 1 s LiDAR displacement (and heading change) as a GPS consistency check that does not depend on the GPS receiver, calibrate it with LODO over the 16 train+val drives at a 1% budget (tie-safe), publish a MotionEstimate per second for WP6, and report the harness ablation on top of B2 + L1 + L2a + L2b.

## Acceptance rule (notes/WP1_gps.md, "2026-10-20 S5", written before any detection result; amendments listed under Deviations)
| criterion | value | verdict |
|---|---|---|
| C1 tests | 133 pass (8 new in tests/gps/test_lidar_odom.py) | MET |
| C2a odometry translation error <= 2.0% (dev) | 1.73% (test 1.58%) | MET |
| C2b rotation <= 0.02 deg/m (dev) | 0.0078 (test 0.0069) | MET |
| C2c median 1 s displacement error <= 0.10 m (dev) | 0.129 m (test 0.135) | NOT MET |
| C3 sigma coverage (2 sigma) >= 90% on test | 89.4% (dev 92.6%) | NOT MET (narrow) |
| C4 clean-run FA on test <= 1.5% (LODO) and nested held-out FA <= 1.5% | 1.64% (val-only 1.33%); nested dev 1.01% | NOT MET (test FA 1.64%) |
| C5 Doppler spoof and meaconing run-level >= 75% (LODO) | 60% / 61% (cusum_dr 70% / 61%) | NOT MET |
| C6 L2d adds on top of B2 + L1 + L2a + L2b | primary: AUC +0.0000, FA 1.15%: no. All 7 L2d layers: AUC +0.0050, drift +7.1 points: yes (LODO); val-only: no | primary NOT adding; whole L2d family adds under LODO only |
| C7 slow drift | untestable on KITTI test (no run has 30 s after onset) | reported only |
| C8 MotionEstimate published, documented, tested | gps/lidar_odom.motion_estimates, results/WP1/S5_motion_estimates.json | MET |

## Data availability
Velodyne scans exist for ALL 23 drives (21 in `../data_extra/kitti_raw`, drives 0001 and 0015 in `../codes/data/Depth`, which the assignment did not count). No drive is without LiDAR; nothing had to be marked "layer not available". Drive 0048 lasts 2.3 s (22 scans): it is in the odometry validation but yields no 1 Hz stream run, so the LODO detection folds are 15 (as in S4, where the "16 drives" were also 15 with runs). Two drives (0017, 0060) are stationary (0.1 m of path), 0052 nearly (8 m): they contribute clean-run false-alarm exposure but almost no odometry segments.

## What was done
- `gps/lidar_odom.py`: voxel grid (0.5 m, range 2.5-60 m), normals by PCA of 8 neighbours, 6-DOF point-to-plane Gauss-Newton (gates 2.0 -> 0.5 m, 20% trimming, constant-velocity start, multi-start for the first pair), pose chaining, 1 s windows, stream features, `motion_estimates()`, `LidarLayer` (v3 Layer, domain gps, layer id L2d). All parameters fixed before any result.
- `gps/lidar_dr.py`: the S4 dead-reckoning branch with LiDAR displacement as odometry (no scale state) + CUSUM, `LidarCusumLayer` (sequential variant).
- `tests/gps/test_lidar_odom.py` (8 tests; suite 133 pass). Tools: `WP1_S5_odom_run.py` (ICP over all drives, Pool(4), cache), `WP1_S5_odometry.py` (validation, sigma fit), `WP1_S5_dev.py` (16 drives only: LODO, nested selection), `WP1_S5_test.py` (the single test pass; dry run on val rows first), `WP1_S5_tables.py`, `WP1_S5_severity.py` (post-hoc diagnostic), `WP1_S5_report.py`.
- Results: `results/WP1/S5_odometry.json`, `S5_dev.json`, `S5_kitti.json`, `S5_acceptance.json`, `S5_severity.json`, `S5_motion_estimates.json`, `S5_tables.md`, harness files `S5_*_{lodo,valonly}.json|md`. Odometry cache (gitignored): `results/WP1/cache/lidar_odom_<drive>.npz` (23 files). Logs in `results/WP1/logs/`.
- Cost: about 0.12 s per scan pair (4673 scans in total); all 23 drives in about 7 min with 4 workers; the features and layers then cost seconds, so later steps read the cache.

### The scores (all from the stream columns of `lidar_odom.stream_features`)
- `gps.lidar_resid_W`: |GPS displacement over the last W fixes - LiDAR displacement over the same interval| in metres (W = 1, 3, 10). The LiDAR displacement is rotated to east-north with the compass offset averaged over the window (compass minus LiDAR yaw): the compass is the vehicle's own sensor, so nothing in the check comes from the receiver.
- `gps.lidar_z_W`: the same residual divided by its modelled standard deviation (receiver AR(1) difference with the S3 values, LiDAR relative error 1.9% x path, compass 2 deg/sqrt(n) x path, floor 0.05 m; constants frozen before detection results).
- `gps.lidar_course`: lateral-metre equivalent of |change of GPS course - change of LiDAR direction of travel| (compass-free; 0 below 2 m/s).
- `gps.cusum_lidar`: sequential variant (LiDAR dead-reckoning branch, frozen when suspicious, CUSUM on its innovations).
- Primary L2d = `gps.lidar_z_1`: selected by J (mean of 6 run-level detections + slow drift) nested in LODO: chosen in 15 of 15 folds (LODO folds), nested held-out FA 1.01%.

## MotionEstimate published by this step (for WP6)
`gps.lidar_odom.motion_estimates(t_fix, P, tp, quality_ok)` returns one `common.motion.MotionEstimate` per second (`t_fix` = stream times; P, tp = poses and times of the cached odometry; `load_odometry(drive)` gives them). Fields: `t` = end of the second (stream clock = first OXTS timestamp); `source = "lidar"`; `displacement = (dx, dy)` in metres over the last second in the vehicle BODY frame at the start of that second (dx forward, dy left; the contract left the frame open, this choice needs no compass and no GPS; to compare with a GPS or CAN displacement WP6 compares norms, or rotates with a heading it trusts); `speed = |displacement| / 1 s` (m/s); `yaw_rate` = heading change over the second (rad/s, positive left); `sigma` = 1-sigma uncertainty of the speed (m/s) = sqrt(0.0821^2 + (0.0046 x speed)^2), multiplied by 3 when the second contains an ICP fallback (fitted on the 16 dev drives; coverage of 2 sigma: dev 92.6%, test 89.4%, just below the 90% rule on test). Seconds without a full window behind them (t < 1 s) are not published. A ready sample for all 23 drives (phase 0 of the 1 Hz grid) is in `results/WP1/S5_motion_estimates.json`. The LiDAR motion does not depend on the GPS attack, so one MotionEstimate stream serves every attacked variant of a drive.

## Results

**LiDAR odometry vs OXTS ground truth, per drive** (KITTI-style error over path segments of 10/25/50/100 m; 1 s windows with GT speed > 1 m/s)

| drive | part | scans | path (m) | translation error | rotation (deg/m) | median 1 s displacement error (m) | median 1 s speed error | ICP inlier fraction | fallback |
|---|---|---|---|---|---|---|---|---|---|
| 0001 | test | 108 | 107 | 0.59% | 0.0020 | 0.056 | 0.36% | 0.74 | 0.0% |
| 0002 | train | 77 | 82 | 0.73% | 0.0061 | 0.081 | 0.51% | 0.72 | 0.0% |
| 0005 | test | 154 | 69 | 5.14% | 0.0122 | 0.224 | 2.81% | 0.70 | 0.0% |
| 0011 | val | 233 | 114 | 1.13% | 0.0062 | 0.087 | 0.46% | 0.70 | 0.0% |
| 0013 | train | 144 | 173 | 1.22% | 0.0020 | 0.116 | 0.34% | 0.60 | 0.0% |
| 0015 | train | 297 | 362 | 0.69% | 0.0034 | 0.082 | 0.55% | 0.65 | 0.0% |
| 0017 | train | 114 | 0 | n/a% | n/a | n/a | n/a% | 0.76 | 0.0% |
| 0019 | train | 481 | 406 | 1.15% | 0.0049 | 0.138 | 0.56% | 0.58 | 0.0% |
| 0020 | train | 86 | 17 | 7.97% | 0.0062 | 0.217 | 4.86% | 0.49 | 0.0% |
| 0027 | val | 188 | 346 | 1.39% | 0.0093 | 0.214 | 0.49% | 0.36 | 0.0% |
| 0028 | test | 430 | 779 | 1.36% | 0.0081 | 0.230 | 0.92% | 0.38 | 0.0% |
| 0029 | train | 430 | 351 | 3.28% | 0.0130 | 0.145 | 0.99% | 0.51 | 0.0% |
| 0035 | val | 131 | 60 | 3.88% | 0.0220 | 0.091 | 1.01% | 0.61 | 0.0% |
| 0039 | test | 395 | 298 | 0.88% | 0.0033 | 0.083 | 0.61% | 0.66 | 0.0% |
| 0046 | train | 125 | 47 | 3.48% | 0.0294 | 0.139 | 1.00% | 0.73 | 0.0% |
| 0048 | train | 22 | 17 | 1.17% | 0.0053 | 0.092 | 0.53% | 0.65 | 0.0% |
| 0052 | test | 78 | 8 | n/a% | n/a | 0.108 | 5.66% | 0.74 | 0.0% |
| 0060 | train | 78 | 0 | n/a% | n/a | n/a | n/a% | 0.78 | 0.0% |
| 0070 | train | 420 | 645 | 1.36% | 0.0071 | 0.159 | 0.60% | 0.60 | 0.0% |
| 0079 | test | 100 | 26 | 1.86% | 0.0128 | 0.095 | 1.29% | 0.64 | 0.0% |
| 0095 | test | 268 | 254 | 1.99% | 0.0089 | 0.142 | 0.31% | 0.70 | 0.0% |
| 0106 | train | 227 | 114 | 1.63% | 0.0044 | 0.099 | 0.82% | 0.65 | 0.0% |
| 0113 | train | 87 | 18 | 5.50% | 0.0069 | 0.188 | 2.75% | 0.53 | 0.0% |

**LiDAR odometry, pooled**

| set | segments | translation error | rotation (deg/m) | median 1 s displacement error (m) | p95 (m) | median 1 s speed error (m/s) | median 1 s yaw error (deg) | sigma coverage (2 sigma) |
|---|---|---|---|---|---|---|---|---|
| 16 train+val drives | 7988 | 1.73% | 0.0078 | 0.129 | 0.399 | 0.065 | 0.057 | 92.6% |
| 7 test drives | 4358 | 1.58% | 0.0069 | 0.135 | 0.335 | 0.068 | 0.059 | 89.4% |

Sigma model of the published speed: sigma = sqrt(0.0821^2 + (0.0046 x speed)^2) m/s, x3 when an ICP fallback happened in the second (fitted on dev only).

Reading: the 1.7% translation / 0.008 deg/m is a plain point-to-plane ICP without loop closure or deskewing. The 1 s displacement error median of 0.13 m is larger than the speed error alone (0.065 m/s) would give, so part is cross-track; probable causes (not verified): an uncalibrated yaw offset between the velodyne and the OXTS frame and uncorrected motion distortion inside a scan. Drives 0005, 0020, 0113 (short, slow) and 0035, 0046 are the weak ones; low ICP inlier fractions (0027, 0028: 0.36-0.38, open roads) do not hurt the 1 s displacement much.

### Detection

**Development drives (16 train+val), candidates ranked by J (run-level detection, LODO pooled 1% threshold)**

| candidate | J | LODO held-out FA | worst drive | drift | accel_drift | jump | freeze | doppler_spoof | meaconing |
|---|---|---|---|---|---|---|---|---|---|
| lid_z_1 | 0.687 | 1.01% | 1.65% | 73% | 58% | 100% | 80% | 64% | 59% |
| lid_z_3 | 0.675 | 1.03% | 3.14% | 74% | 59% | 100% | 79% | 68% | 57% |
| lid_resid_3 | 0.638 | 1.11% | 3.51% | 73% | 57% | 100% | 78% | 63% | 51% |
| lid_resid_1 | 0.631 | 1.05% | 2.51% | 68% | 54% | 100% | 79% | 59% | 53% |
| lid_z_10 | 0.610 | 1.09% | 3.23% | 64% | 49% | 99% | 79% | 55% | 46% |
| lid_resid_10 | 0.594 | 1.21% | 4.27% | 63% | 46% | 100% | 74% | 51% | 43% |
| cusum_lidar_nis|k=2.0 | 0.518 | 1.92% | 11.42% | 44% | 39% | 100% | 71% | 46% | 38% |
| cusum_lidar_nis|k=1.5 | 0.515 | 1.90% | 11.22% | 43% | 39% | 100% | 71% | 46% | 38% |
| cusum_lidar_nis|k=1.0 | 0.512 | 1.89% | 11.02% | 42% | 39% | 100% | 70% | 46% | 37% |
| cusum_lidar_nis|k=0.5 | 0.509 | 1.81% | 10.46% | 41% | 39% | 100% | 70% | 46% | 37% |
| cusum_lidar_axis|k=2.0 | 0.497 | 1.91% | 11.06% | 39% | 38% | 99% | 67% | 45% | 36% |
| cusum_lidar_axis|k=1.5 | 0.482 | 1.83% | 10.39% | 36% | 37% | 99% | 65% | 42% | 35% |
| cusum_lidar_axis|k=1.0 | 0.463 | 1.70% | 9.13% | 34% | 36% | 98% | 62% | 36% | 34% |
| cusum_lidar_axis|k=0.5 | 0.448 | 1.55% | 7.90% | 33% | 33% | 97% | 61% | 34% | 33% |
| lid_course | 0.295 | 1.03% | 2.22% | 18% | 20% | 59% | 69% | 13% | 19% |

**Nested selection** (choice by J on the 15 other drives, per fold): choices {lid_z_1: 15}; held-out FA of the nested procedure 1.01%; J of the nested procedure 0.686; choice on all 16 drives (used on test): lid_z_1.

**KITTI test, LODO calibration (16 drives) - primary: run-level detection (row-level in brackets)**

| layer | FA clean runs | FA normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | slow drift <0.5 m/s within 30 s | AUC (row) |
|---|---|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 1.58% | 1.53% | 39% (34%) | 43% (46%) | 100% (72%) | 89% (87%) | 41% (47%) | 49% (33%) | 14% of 14 | 0.847 |
| gps.ekf_nis | 0.44% | 0.57% | 26% (12%) | 36% (42%) | 100% (41%) | 76% (83%) | 80% (42%) | 66% (48%) | 14% of 14 | 0.865 |
| gps.cusum_ekf | 2.53% | 1.78% | 80% (59%) | 67% (60%) | 100% (99%) | 84% (87%) | 23% (4%) | 29% (8%) | 43% of 14 | 0.791 |
| gps.cusum_dr | 1.64% | 1.27% | 70% (44%) | 61% (55%) | 100% (100%) | 84% (87%) | 70% (60%) | 61% (65%) | 14% of 14 | 0.846 |
| gps.lidar_z_1 | 1.64% | 1.06% | 61% (25%) | 59% (50%) | 100% (11%) | 84% (85%) | 60% (31%) | 61% (26%) | 7% of 14 | 0.776 |
| gps.lidar_z_3 | 1.45% | 0.94% | 67% (37%) | 61% (53%) | 100% (30%) | 84% (86%) | 71% (47%) | 63% (35%) | 7% of 14 | 0.819 |
| gps.lidar_z_10 | 0.88% | 0.48% | 47% (30%) | 46% (43%) | 99% (71%) | 83% (86%) | 46% (42%) | 46% (32%) | 7% of 14 | 0.844 |
| gps.lidar_resid_1 | 1.14% | 1.03% | 59% (22%) | 51% (49%) | 100% (11%) | 84% (84%) | 51% (35%) | 57% (26%) | 21% of 14 | 0.769 |
| gps.lidar_resid_3 | 1.96% | 0.96% | 66% (37%) | 56% (54%) | 100% (30%) | 83% (86%) | 61% (48%) | 59% (36%) | 0% of 14 | 0.823 |
| gps.lidar_course | 1.01% | 1.03% | 24% (3%) | 17% (3%) | 77% (16%) | 71% (15%) | 16% (2%) | 26% (3%) | 29% of 14 | 0.558 |
| gps.cusum_lidar | 10.11% | 5.38% | 41% (43%) | 40% (47%) | 100% (100%) | 77% (84%) | 43% (49%) | 47% (52%) | 29% of 14 | 0.852 |

**KITTI test, val-only calibration (3 drives): run-level detection (row-level in brackets)**

| layer | FA clean runs | FA normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | slow drift <0.5 m/s within 30 s | AUC (row) |
|---|---|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 0.38% | 0.70% | 34% (30%) | 41% (44%) | 100% (71%) | 89% (86%) | 39% (44%) | 40% (29%) | 7% of 14 | 0.847 |
| gps.ekf_nis | 2.59% | 2.41% | 54% (31%) | 56% (49%) | 100% (59%) | 81% (84%) | 97% (66%) | 79% (61%) | 14% of 14 | 0.865 |
| gps.cusum_ekf | 2.65% | 1.92% | 80% (60%) | 67% (60%) | 100% (99%) | 84% (87%) | 23% (4%) | 29% (8%) | 43% of 14 | 0.791 |
| gps.cusum_dr | 1.58% | 1.26% | 70% (44%) | 61% (55%) | 100% (100%) | 84% (87%) | 70% (60%) | 61% (65%) | 14% of 14 | 0.846 |
| gps.lidar_z_1 | 1.33% | 0.91% | 61% (24%) | 56% (49%) | 100% (11%) | 84% (85%) | 60% (30%) | 60% (25%) | 7% of 14 | 0.776 |
| gps.lidar_z_3 | 1.90% | 1.36% | 73% (39%) | 66% (55%) | 100% (31%) | 86% (87%) | 74% (50%) | 64% (37%) | 7% of 14 | 0.819 |
| gps.lidar_z_10 | 1.52% | 1.44% | 56% (34%) | 53% (46%) | 99% (71%) | 84% (87%) | 59% (46%) | 53% (38%) | 14% of 14 | 0.844 |
| gps.lidar_resid_1 | 0.82% | 0.85% | 53% (20%) | 50% (48%) | 100% (11%) | 83% (84%) | 51% (32%) | 54% (24%) | 0% of 14 | 0.769 |
| gps.lidar_resid_3 | 0.76% | 0.42% | 59% (33%) | 51% (52%) | 100% (30%) | 83% (85%) | 59% (45%) | 56% (33%) | 0% of 14 | 0.823 |
| gps.lidar_course | 1.07% | 1.20% | 26% (4%) | 20% (4%) | 77% (16%) | 71% (16%) | 16% (2%) | 27% (3%) | 36% of 14 | 0.558 |
| gps.cusum_lidar | 13.27% | 8.56% | 70% (59%) | 51% (58%) | 100% (100%) | 83% (87%) | 61% (62%) | 63% (65%) | 43% of 14 | 0.845 |

**FA transfer on test (clean test runs, 1% budget).**

| layer | val-only calibration | LODO calibration | LODO held-out estimate (dev) | worst dev drive |
|---|---|---|---|---|
| gps.dr_resid_10 | 0.38% | 1.58% | 1.21% | 4.28% |
| gps.ekf_nis | 2.59% | 0.44% | 1.30% | 19.50% |
| gps.cusum_ekf | 2.65% | 2.53% | 1.04% | 1.79% |
| gps.cusum_dr | 1.58% | 1.64% | 1.04% | 1.96% |
| gps.lidar_z_1 | 1.33% | 1.64% | 1.01% | 1.65% |
| gps.lidar_z_3 | 1.90% | 1.45% | 1.03% | 3.14% |
| gps.lidar_z_10 | 1.52% | 0.88% | 1.09% | 3.23% |
| gps.lidar_resid_1 | 0.82% | 1.14% | 1.05% | 2.51% |
| gps.lidar_resid_3 | 0.76% | 1.96% | 1.11% | 3.51% |
| gps.lidar_course | 1.07% | 1.01% | 1.03% | 2.22% |
| gps.cusum_lidar | 13.27% | 10.11% | 1.92% | 11.42% |

**Beat-or-not (LODO, run level): primary L2d vs B2 and vs cusum_dr (S4 best); rule: >= +5 points AND clean-run FA <= reference + 0.5 point.**

| attack | vs gps.dr_resid_10 | vs gps.cusum_dr |
|---|---|---|
| drift | +23 pts: beats | -9 pts: worse |
| accel_drift | +16 pts: beats | -3 pts: no difference |
| jump | +0 pts: no difference | +0 pts: no difference |
| freeze | -4 pts: no difference | +0 pts: no difference |
| doppler_spoof | +19 pts: beats | -10 pts: worse |
| meaconing | +13 pts: beats | +0 pts: no difference |

**Detection delay distribution, lodo** (fixes after onset of the first alarm, detected runs only; q10 / q25 / median / q75 / q90; share of ALL runs detected within 10 s / 30 s)

| layer | drift | accel_drift | jump | freeze | doppler_spoof | meaconing |
|---|---|---|---|---|---|---|
| gps.cusum_dr | 1/1/2/3/5 ; 70% / 70% | 3/3/4/6/7 ; 59% / 61% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 2/3/4/4/5 ; 69% / 70% | 1/2/3/4/5 ; 61% / 61% |
| gps.lidar_z_1 | 1/1/1/2/5 ; 61% / 61% | 2/3/4/6/7 ; 56% / 59% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 2/3/4/5/6 ; 59% / 60% | 1/2/3/4/4 ; 61% / 61% |
| gps.lidar_z_3 | 2/2/2/3/4 ; 66% / 67% | 3/4/4/6/10 ; 57% / 61% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 3/3/4/5/6 ; 71% / 71% | 2/3/3/4/5 ; 63% / 63% |
| gps.cusum_lidar | 0/2/4/5/8 ; 40% / 41% | 0/5/6/8/8 ; 39% / 40% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/2 ; 77% / 77% | 0/5/6/7/8 ; 41% / 43% | 2/4/5/6/7 ; 47% / 47% |

### Harness ablation (S4 stack = L1 + B2 + L2a EKF NIS + L2b cusum_ekf + cusum_dr; combiner refitted on the calibration drives each time)

| harness | calibration | AUC base -> with | detection base -> with | combined FA | best row-level gain (points) | adds? |
|---|---|---|---|---|---|---|
| S4 stack + gps.lidar_z_1 | lodo | 0.922 -> 0.922 | 70.6% -> 70.6% | 1.15% | +0.7 (doppler_spoof) | no |
| S4 stack + gps.cusum_lidar | lodo | 0.922 -> 0.925 | 70.6% -> 73.8% | 1.33% | +9.1 (drift) | yes |
| S4 stack + all 7 L2d layers | lodo | 0.922 -> 0.927 | 70.6% -> 73.4% | 1.23% | +7.1 (drift) | yes |
| S4 stack + gps.lidar_z_1 | valonly | 0.903 -> 0.904 | 73.0% -> 73.1% | 2.23% | +0.3 (drift) | no |
| S4 stack + gps.cusum_lidar | valonly | 0.903 -> 0.883 | 73.0% -> 76.6% | 8.95% | +11.5 (drift) | no |
| S4 stack + all 7 L2d layers | valonly | 0.903 -> 0.888 | 73.0% -> 76.8% | 8.76% | +13.0 (drift) | no |

Full tables, including every `all-but-one` row and the L2d-alone runs: `results/WP1/S5_tables.md`.

### Why Doppler spoof and meaconing stay near 60% (post-hoc diagnostic, `S5_severity.json`, nothing chosen from it)

| attack | severity range | test runs | run-level detected | median attacked fixes |
|---|---|---|---|---|
| doppler_spoof | 0.2 - 1.0 | 18 | 28% | 6.0 |
| doppler_spoof | 1.0 - 2.0 | 29 | 72% | 7.0 |
| doppler_spoof | 2.0 - 3.01 | 23 | 70% | 7.0 |
| meaconing | 0.5 - 1.0 | 17 | 82% | 10.0 |
| meaconing | 1.0 - 2.0 | 27 | 52% | 7.0 |
| meaconing | 2.0 - 3.01 | 26 | 58% | 7.0 |
| drift | 0.2 - 0.5 | 14 | 7% | 8.0 |
| drift | 0.5 - 1.0 | 18 | 50% | 9.0 |
| drift | 1.0 - 2.01 | 38 | 87% | 5.5 |
| accel_drift | 0.05 - 0.15 | 18 | 33% | 7.5 |
| accel_drift | 0.15 - 0.3 | 25 | 56% | 6.0 |
| accel_drift | 0.3 - 0.51 | 27 | 78% | 9.0 |

The LiDAR side is accurate (0.13 m per second) and cannot be dragged: the check never absorbs the attack. What limits detection is the receiver side: differencing a receiver whose error is AR(1) with 1 m sigma leaves 0.45 m per axis of noise on a 1 s displacement, so a velocity offset becomes visible only above about 1.3 m/s. A Doppler-consistent spoof ramps its velocity offset at 0.4 m/s^2 (reaches 1.3 m/s after about 3 s) and many test runs have only 6-7 attacked fixes; spoofs whose final offset is below 1 m/s are seen in 28% of runs, those above 1 m/s in about 70%. Longer windows (W = 3, lid_z_3: Doppler 71%, meaconing 63%) average more noise but the AR(1) noise also grows with the window, so there is a plateau. The sequential variant should have gained from accumulation but has a heavy false-alarm tail (below).

### Honest reading of the results
- LiDAR odometry is a working independent witness: with only the receiver-noise limit, `lid_z_1` beats B2 on drift (+23 points), accel drift (+16), Doppler spoof (+19) and meaconing (+13) at equal false alarms, and detects jumps and freezes as well as B2, but it does NOT beat the wheel-odometry dead-reckoning branch cusum_dr (-9 points on drift, -10 on Doppler spoof, equal otherwise), and on top of the full S4 stack the primary layer adds nothing (AUC +0.0000). The stack already holds a second, partly independent odometry (wheel speed + compass); LiDAR duplicates it.
- Value of independence: under LODO the whole L2d family lifts the stack AUC from 0.922 to 0.927 and the row-level drift detection by +7.1 points at combined FA 1.23% (rule met via the +5 points clause); with val-only calibration it does not (FA 8.76%, driven by gps.cusum_lidar). I would not claim more than "marginal gain".
- `gps.cusum_lidar` is a failure as a calibrated layer: clean-run FA 10.11% on test (LODO) and 13.27% (val-only) against a dev held-out estimate of 1.92%: a few clean runs where the ICP is momentarily wrong latch the freeze and the CUSUM runs away (the S4 branch survived this thanks to its learned scale and 2 deg compass model; here the tighter LiDAR model is less forgiving). Not recommended; kept in the tables for completeness.
- `gps.lidar_course` (compass-free heading change) is weak (AUC 0.558): below 2 m/s it is silent and above it the GPS course noise is large.
- Slow drift (< 0.5 m/s within 30 s): untestable on KITTI test (supervisor decision S4); lid_z_1 detects 7% of the 14 runs inside the available window.

## Deviations from the written plan (all before any test number; details in notes/WP1_gps.md)
1. Standardised variant lid_z_W added to the candidates after the first look at clean residual quantiles (dev only); constants frozen.
2. Sequential layer (gps/lidar_dr.py) added after the first dev result showed the instantaneous residual below the C5 target; selection among all candidates nested in LODO as written.
3. Bug found on dev diagnostics: the first scan pair of each drive had no previous motion, the identity start converged to a wrong minimum at speed (first second 6 m instead of 14 m). Fixed with a multi-start for the first pair only; odometry recomputed for all 23 drives (dev and test) with the same code; the earlier numbers (translation 1.88% dev) were superseded. ALPHA_FIXES 5 -> 20 and the sigma constants updated from the corrected run (dev data only).
4. The "21 of 23 drives" premise was wrong: 23 of 23 have velodyne.

## Problems, surprises, open questions
- Question 1 (frame): `MotionEstimate.displacement` is in the body frame (forward, left) of the start of the second. The contract does not fix the frame; please confirm for WP6 or ask for east-north (then it needs a trusted heading).
- Question 2 (C5): the 75% target for Doppler spoof / meaconing is not reachable with a per-second test against a simulated receiver with 1 m AR(1) noise. Is the target to be kept for S8, or replaced by a delay-based statement?
- The receiver noise (1 m AR(1) on top of RTK) is the S1 simulation; a real civil receiver with Doppler-derived velocity would be less noisy in displacement over 1 s (velocity-based checks) than the position differencing used here. The check still uses position only.
- Odometry: no extrinsic velodyne-to-IMU calibration and no scan deskewing (both would likely reduce the 0.13 m 1 s error); both left out on purpose to stay within the step. KITTI GT is OXTS, not a separate ground truth.
- The harness combiner is refitted on the calibration drives each time; with LODO the combiner is fitted on pooled 16-drive scores, not out-of-fold (as in S4).

## Proposed next step
S6 L2e map matching on OSM drivable roads (S4 note: filter footways). Not started.
