# M1-GPS: GPS spoofing detection by physics and consistency (WP1, milestone report)

Date 2026-10-21. Status: **PARTIAL** (rule written before any result: notes/WP1_gps.md "S8"; verdicts: results/WP1/S8_acceptance.json). Self-contained; long tables: `results/WP1/S8_tables.md`; numbers: `S8_dev.json` (nested LODO), `S8_kitti.json` (test, one pass), `S8_external.json`, `S8_control.json`, `S8_freeze.json`.

**Protocol.** KITTI 2011_09_26, 23 drives, 1 Hz. Receiver error (AR(1) phi 0.9, sigma 1 m), odometry (2% scale, 0.05 m/s), compass (2 deg) are simulated on top of the OXTS truth (the OXTS is RTK: without added noise every detector looks perfect). 6 attacks, 10 phase offsets per drive: drift, accelerating drift, jump, freeze (v2), and two new physically consistent ones: Doppler-consistent trajectory spoof (the fake track and the reported velocity agree) and meaconing (replay with a growing delay). Development = 16 train+val drives (15 with runs) calibrated by leave-one-drive-out (LODO): inside each fold the CUSUM configuration, every layer's calibration and 1% threshold, and the combiner are fitted on the other 14 drives only. Test = 7 drives (490 runs, 70 per attack), scored once. Operating point: 1% false alarms (FA) of normal rows per layer and for the combination. Run-level detection = the run has at least one alarm at/after onset. Default stack: L1 kinematic rules (5) + Doppler-vs-position, B2 dead reckoning, L2a EKF NIS, L2b CUSUM (EKF innovation; dead-reckoning branch with L2c scale learning), L2d six GPS-vs-LiDAR-odometry checks (16 layers). Out of the default (ablation rows only): map matching, cusum_lidar, normal-only model L3, supervised L4. Combiner: `noisy_or_log` (parameter-free), chosen on nested dev; fitted WITHOUT the Doppler / meaconing rows, so those two attacks are zero-shot.

## 1. What each layer catches, and why (test, run-level, LODO calibration, own 1% threshold)

| layer | physics | FA | drift | accel | jump | freeze | Doppler | meacon |
|---|---|---|---|---|---|---|---|---|
| L1 jerk (also long_accel, max_speed) | physical limits of a car: only gross inconsistency | 0.95% | 23 | 7 | 100 | 70 | 16 | 9 |
| L1 Doppler vs position | receiver velocity must equal the position derivative; a naive spoof moves only the position | 1.52% | 71 | 59 | 100 | 84 | 16 | 17 |
| B2 dead reckoning (v2) | 10 s of odometry + compass vs GPS displacement; independent of the receiver | 1.58% | 39 | 43 | 100 | 89 | 41 | 49 |
| L2a EKF NIS | fuses IMU, odometry, heading, Doppler; once Doppler and position agree, odometry and IMU arbitrate | 0.44% | 26 | 36 | 100 | 76 | 80 | 66 |
| L2b CUSUM on EKF innovation | memory: small consistent innovations accumulate | 2.53% | 80 | 67 | 100 | 84 | 23 | 29 |
| L2b/L2c CUSUM on dead-reckoning branch | same, on a branch that stops trusting GPS once suspicious and learns the odometry scale only while GPS is trusted | 1.64% | 70 | 61 | 100 | 84 | 70 | 61 |
| L2d LiDAR odometry vs GPS (lidar_z_3) | ICP motion (1.58% translation error on test) is an exteroceptive witness the spoofer does not control | 1.45% | 67 | 61 | 100 | 84 | 71 | 63 |
| **combined (noisy_or_log, 16 layers)** | | **1.83%** | **76** | **63** | **100** | **89** | **69** | **61** |

Other rules (max_speed, lat_accel, yaw_rate, lidar_course) reach 7-39% mean detection; they only see jumps. A Doppler-consistent spoof or a meaconing replay is invisible to every check that uses only receiver data (16-17%): only the vehicle's own odometry/IMU/LiDAR can see it, and only once the offset exceeds the per-second noise (0.45 m per axis after differencing).

## 2. Final numbers (test, 95% bootstrap intervals over the 7 test drives; over the 70 runs per attack in brackets)

| attack | run-level | row-level | median delay (s) | detected within 10 s |
|---|---|---|---|---|
| drift 0.2-2 m/s | 75.7% [63, 89] ([66, 86]) | 49.1% | 2 | 76% |
| accelerating drift | 62.9% [34, 87] ([51, 73]) | 56.1% | 4 | 59% |
| jump 5-50 m | 100% [100, 100] | 100% | 0 | 100% |
| freeze | 88.6% [66, 100] ([80, 96]) | 87.2% | 1 | 89% |
| Doppler-consistent spoof (zero-shot) | 68.6% [51, 86] ([57, 79]) | 56.5% | 4 | 66% |
| meaconing (zero-shot) | 61.4% [29, 89] ([50, 73]) | 63.9% | 3 | 61% |
| mean of 6 | 76.2% [59, 90] ([72, 80]) | 68.8% | | |

Clean-run FA **1.83%** [0.78, 2.76] drives, [1.09, 2.61] runs (nested dev held-out 1.24%); per drive 0.2-1.5% except drive 0005 4.98% (short drive). AUC 0.895 [0.83, 0.93]. Calibrating on the 3 validation drives instead gives the same FA 1.83% (LODO fixes single layers, EKF NIS 2.59% -> 0.44%, but not the combination). Detection grows with severity (drift 50 / 79 / 100% in three bins; Doppler offset 0.2-1.1 m/s 43%, 1.1-3 m/s 75-85%); middle bins of accel and meaconing are non-monotone (n about 22 per bin).

**Against v2 (same runs).** B2 alone: 39 / 43 / 100 / 89 / 41 / 49 (mean 60.0%) at FA 1.58%; v2 C2 (XGBoost) FA 0.82%, drift 63%. v3 default stack: mean 76.2%, **+16.2 points [+10, +22]** over B2 (paired drive bootstrap), FA +0.25 point. Versus the best single layer (cusum_dr 74.5%): +1.7 points [-1, +4], not significant.

## 3. Ablation (test; nested dev in `S8_tables.md` section 4, same picture)

Each layer alone: table in section 1 / `S8_tables.md` 1. All-but-one (method fixed, refitted): no single removal costs more than 1.2 points of mean run-level detection (dr_resid_10, ekf_nis, cusum_dr: -1.2 each, AUC -0.002 / -0.008 / -0.009). Removing max_speed or long_accel gives +1.0: the stack is redundant and the weak kinematic rules dilute it. Removing any one L2d layer changes the mean by -0.5 to +0.7 points (they are interchangeable witnesses). Optional rows: + L3 +0.7, + L4 +1.0, + cusum_lidar +0.2 (FA 2.02%), + map matching +0.2 (nothing adds; cusum_lidar alone FA 10.1%, map_dist alone FA 4.1%, worst drive 25.7%). Combiners (nested dev / test mean run-level): noisy_or_log 74.9 / 76.2 at FA 1.24 / 1.83%; logistic 74.4 / 78.1 at 1.49 / 2.78%; max 76.4 / 74.3 at 4.32 / 1.26%; common `noisy_or` raises no alarm (float saturation, section 6). A logistic that also sees Doppler / meaconing rows reaches 89 / 70% on them (side row, not deployed: it is no longer zero-shot).

## 4. External tests

**UAV live spoofing flight (D06, PX4, one flight; benign flight = calibration flight; first spoofed fix 118.0 s).** Layers with inputs: L1 receiver rules (fix, satellites, HDOP, noise / jamming-indicator jumps, Doppler vs position), EKF NIS, EKF-CUSUM (no odometry: no B2 / dead-reckoning / LiDAR). Combined: first alarm **118.0003 s**, 100% of the 19 spoofed fixes flagged, **3 alarms before 117 s of 118 fixes = 2.54% (Wilson [0.9, 7.2]; bound 2%: NOT MET)** at 27, 29, 68 s. v2: residual alarm at 118.0 s, 0 false alarms; PX4 EKF never. EKF-CUSUM alone reproduces the v2 result (118.0 s, 0 pre-onset alarms); the combination adds false alarms from weak rules. Seven layers fire within 2 s (EKF-CUSUM, NIS, HDOP, noise, satellite jumps, Doppler-vs-position).
**AV-GPS (D03, test files 2-3: 3 normal, 3 spoofed sessions).** Nothing usable. The spoofed sessions are no-fix placeholders (0 satellites, HDOP 95-100): B2, rules and NIS have AUC 0.1-0.3 (placeholders look quieter than driving); only latching CUSUMs separate them (cusum_ekf AUC 0.98, FA 7.2%; cusum_dr FA 54%). Combined at the val-session threshold: FA 17.5%, detection 82%, AUC 0.883 = the 95th percentile of the session-label permutation null (0.12-0.88). KITTI thresholds: B2 FA 35.6%. No Doppler / IMU / LiDAR in the dataset. Any "detection" here is the placeholder artefact.

## 5. NOT met / NOT caught

- Test clean-run FA 1.83% > 1.5% rule (nested dev 1.24% met; the drive-level interval [0.78, 2.76] contains 1% and 1.5%).
- **Doppler-consistent spoof 69% and meaconing 61% < 75% target** (CIs [51, 86], [29, 89]); targets not lowered. Misses concentrate at small offsets (Doppler offset < 1.1 m/s: 43%).
- Slow drift 0.2-0.5 m/s within 30 s (target 60%): **untestable on KITTI** (no run has 30 s after onset; runs are not concatenated). 3 of 14 slow-drift runs were flagged in the window available. Physics: a 0.3 m/s drift moves 0.3 m per fix against 0.45 m per-step receiver noise and a 2% odometry scale error (0.2 m/s at 10 m/s); it needs about 10-30 s of accumulation.
- UAV pre-onset FA 2.54% > 2%. AV-GPS: nothing works (above). Road-following spoofs are invisible to map matching by construction (L2e dropped in S6).
- Attacks are synthetic and non-adaptive (the spoofer does not know the odometry, LiDAR or the thresholds).

## 6. Artefacts and pitfalls found (so nobody re-discovers them)

- **RTK OXTS needs noise** (a clean OXTS gives ~100% for everything). **3-drive validation does not transfer** (EKF NIS 2.6% FA on test at the validation 1% threshold; train drives 3.1%): thresholds by LODO over all development drives.
- **EKF absorption:** an ungated EKF absorbs 99% / 97% of a Doppler-consistent / meaconing offset within 30 s (its innovation vanishes, so it alarms only early); the dead-reckoning branch that freezes when suspicious absorbs 9% / 21%. CUSUM latches: false freezes make cusum_lidar run away (FA 10%).
- **Map centreline offsets:** OSM centrelines sit 4-5 m off on some drives, so distance to road has 4.1% FA (25.7% on drive 0028).
- **AV-GPS placeholder sessions** (0 satellites, HDOP 100): a satellite rule gets 99.6% (artefact); features that measure absolute motion (pos_step) encode platform speed (a KITTI-trained L4 flags 61% of AV-GPS normals).
- **common/combiner.py `noisy_or` saturates** at exactly 1.0 with 16 correlated layers (1.66% of normal rows tied > 1% budget): 0 alarms. Rank-equivalent `noisy_or_log` used; request in `reports/REQUEST_WP1_combiner_noisy_or.md`.
- **Combiner halves were by run id in the S4-S7 harness** (runs of one drive on both sides, selection only); S8 splits by drive. A combiner that sees the new attack types inflates them (+17 / +10 points on Doppler / meaconing on dev): the deployed one does not.
- Shuffled-label control of the only supervised row (L4): 5 seeds, mean test AUC 0.44 (max 0.52; bound 0.55 met; S7's single seed 0.553 reproduced). L3 and the deployed combiner are label-free: nothing to shuffle.
- Not nested, disclosed: LiDAR sigma constants (fitted on odometry error vs OXTS) and L1 physical limits; the receiver noise model (phi, sigma, q_acc) was re-estimated in all 15 folds and changes nothing (q_acc 0.1 in 15/15).

## 7. Data limits

Seven test drives (cluster size for the honest intervals; runs of one drive are 10 correlated phase offsets), 70 runs per attack; receiver noise, odometry error and every attack are simulated; one real attack flight (UAV, 118 pre-onset fixes, onset label approximate); AV-GPS has 6 test sessions and placeholder spoofing; no real spoofing of a car exists in the data. The KITTI test drives were scored once per step in S1-S7 and once here (combiner choice and ablation made on dev only).

## 8. Frozen deployable GPS domain output (for WP6 / WP7)

`gps/domain.py`; fitted object in `results/WP1/frozen_gps/` (`domain.json`, `calibrators.npz`, 1.9 MB; reload reproduces the evaluated statistic to 0.0 and 0 alarm differences on 11,074 test rows). Fixtures: `example_evidence_doppler_spoof_run.json`, `example_gps_motion_estimates.json`.
```
d  = GPSDomain.load("results/WP1/frozen_gps")           # 16 calibrated layers + combiner
df = prepare(stream)       # whole runs in time order, 1 Hz; stream columns of gps/stream.py + dr_resid_10, still, L1 columns, lid_* (LiDAR odometry)
S, score, alarm = d.score_arrays(df)                    # fast path
ev, per = d.score(df, with_layers=True)                 # ev: Evidence(domain="gps", layer="combined", name="gps.combined")
```
Evidence: `score` in [0, 1] = ECDF of the statistic S = -sum log(1 - s_i) on normal development rows (strictly increasing above the maximum); `alarm` = score >= 0.98997 (about 1% of normal rows; expect 1.2-1.8% on unseen drives); `reason` names the strongest alarming layers with their physics sentence; `details` = {statistic, method, layer_scores}; `sample_id` = "run/k". Causal, stateless between calls (re-run whole runs). MotionEstimate: `gps.lidar_odom.motion_estimates` (source "lidar", body frame, 1 Hz, sigma model; sample `S5_motion_estimates.json`) is the independent witness; `gps.domain.gps_motion_estimates` (source "gps", displacement from the reported position rotated by the compass heading, sigma 0.45 m/s) is the GPS CLAIM to compare against CAN wheel speed or LiDAR (a spoofer controls it). Needs wheel odometry, compass, IMU, LiDAR odometry; without odometry only the UAV subset (L1 receiver rules, EKF, EKF-CUSUM) applies.
