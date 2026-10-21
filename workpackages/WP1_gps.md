# WP1 GPS

Goal: a GPS spoofing detector built on physics and consistency (it must work on a vehicle it
was not trained on), with the learned model as one layer among several.

Owns: `gps/`, `tests/gps/`, `results/WP1/`, `notes/WP1_gps.md`, `reports/WP1_*`, `tools/WP1_*`.
Data: D03 AV-GPS, D04 KITTI OXTS (+ velodyne for S5), D06 UAV, D15 OSM (S0), optional D22.

## Baseline (v2, `../codes_v2/results/gps_kitti_external.json`, `gps_uav_case_study.json`)
KITTI unseen drives, 1% FA target: B2 dead-reckoning rule FA 1.58%, runs detected drift 39%,
accel 43%, jump 100%, freeze 89%; C2 (trained on KITTI) FA 0.82%, drift 63% of runs; drift
< 0.5 m/s: 0-11% of rows for every detector. AV-GPS model used on KITTI: 63% FA. UAV live
spoofing: GPS-vs-IMU residual alarm at 118.0 s (first spoofed fix), 0 false alarms; PX4 EKF never.
Target (fixed): slow drift 0.2-0.5 m/s detected within 30 s in >= 60% of runs at <= 1% FA on
unseen KITTI drives; UAV not worse.

## Steps
- S0 Data: download D15 (OSM extract covering the KITTI drives' bounding box; Geofabrik
  Karlsruhe region or Overpass query) after the user approves; record in DATASETS.md.
- S1 Data layer: unified stream `gps/stream.py` (t, lat, lon, reported velocity, course,
  odometry speed, IMU accel / gyro, receiver fields when present, label, onset, group). Adapters:
  KITTI OXTS (copy `resample_1hz`, receiver noise AR(1) phi 0.9 sigma 1 m, odometry 2% scale +
  0.05 m/s from v2 and document them), AV-GPS (sessions), UAV (PX4 csv). Attack generator:
  drift, accelerating drift, jump, freeze (v2) + Doppler-consistent trajectory spoof (reported
  velocity follows the fake track) + meaconing delay; physically consistent, documented.
  Split: the v2 LiDAR drive split (TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027).
  Acceptance: unit tests; v2 B2 numbers reproduced from the new stream (same as WP0 S3).
- S2 L1 receiver sanity rules (fix type, satellites / DOP jumps, noise / AGC jumps, impossible
  speed / acceleration for a car, clock jumps when available).
- S3 L2a error-state Kalman filter (IMU + odometry + GPS), NIS chi-square test per fix.
- S4 L2b CUSUM / SPRT on innovations + L2c online odometry-scale calibration (learned while
  GPS is trusted, frozen when suspicious).
- S5 L2d LiDAR odometry: point-to-plane ICP between consecutive KITTI scans (scipy cKDTree),
  1 s displacement vs GPS displacement; publish MotionEstimate (WP6 uses it).
- S6 L2e map matching on OSM roads: distance to road, heading vs road direction.
- S7 L3 normal-only model of residuals; L4 retrain the v2 C2 model inside the harness.
- S8 Combiner + full ablation + external tests (KITTI unseen drives, UAV flights, AV-GPS
  sessions) -> milestone M1-GPS report.
Each step: acceptance rule written before results; ablation row for the new layer.

## Pitfalls from v2
- KITTI frames ~0.1032 s apart: resample on real timestamps (every 10th frame is 1.032 s).
- KITTI OXTS is RTK: add receiver noise or every detector looks perfect.
- AV-GPS spoofed sessions mostly show 0-1 satellites: a satellite rule gets 99.6% (artefact);
  features measuring absolute motion (pos_step) encode the platform's speed, not spoofing.
- Below ~0.2 m/s a drift equals the odometry scale error x speed: needs S4 calibration.

## Progress
(worker updates this section)
- S4 (2026-10-20): L2b CUSUM (EKF and dead-reckoning branch), L2c scale + freeze, LODO helper: REVIEW. See reports/WP1_S4.md.
- S5 (2026-10-20): L2d LiDAR odometry (point-to-plane ICP, 23/23 drives), lid_z_W layers, sequential variant, MotionEstimate: REVIEW. See reports/WP1_S5.md.
- S6 (2026-10-21): L2e map matching on drivable OSM roads (map_dist, map_heading, map_comb): REVIEW. Adds nothing on the S5 stack; test FA 4.11% (per-road OSM offset). See reports/WP1_S6.md.
- S7 (2026-10-21): L3 normal-only residual model (isolation forest) and L4 retrained v2 C2 in the harness: REVIEW. Neither adds to the physics stack (AUC +0.001 / +0.005); L4 fails transfer to AV-GPS; shuffled-label AUC 0.553. See reports/WP1_S7.md.
- S8 (2026-10-21): combiner (noisy_or_log, parameter-free, zero-shot on Doppler / meaconing), full ablation, nested LODO, UAV + AV-GPS external tests, frozen GPSDomain output, milestone report: REVIEW (M1-GPS PARTIAL). Test FA 1.83% (rule 1.5% not met), Doppler / meaconing 69 / 61% (75% not met), +16.2 points over B2; UAV alarm 118.0 s but pre-onset FA 2.54%; AV-GPS nothing usable. See reports/M1_GPS.md, reports/WP1_S8.md.
