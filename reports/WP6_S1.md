# WP6 S1: Motion witnesses (GPS/IMU, LiDAR odometry, CAN wheel speed, V2X), time alignment, sigma honesty

Date: 2026-10-22    Worker: opus (WP6, T4)

## Summary (verdict first)
- **A1 streams: MET.** KITTI (23 drives, WP1 split): gps (claim), imu (gyro yaw), lidar (ICP witness), can (SIMULATED
  0x6e0 frames decoded by the frozen `CanDomain.motion_estimates`). comma2k19 Chunk_1 (D22, real, one Toyota-style car,
  20 routes, 3.3 h, split by route 13/4/4): can (decoded speed), wheel (4-wheel mean), gnss (u-blox), imu (gyro).
  **V2X: no data set has the ego's own BSM/CAM next to GPS/LiDAR/CAN, so V2X gives other vehicles' motion only**; an
  adapter (`crossdomain/v2x_self.py`) is ready, no pair is evaluable. 10 pairs in total (tables: `results/WP6/s1_tables.md` s1).
- **A2 latency: MET** (cross-correlation of accelerations, bootstrap over drives/routes; unit test recovers 0.30 s within 0.05 s).
  KITTI OXTS-vs-LiDAR speed +0.004 s [-0.031, +0.035]; yaw rate -0.053 s [-0.062, -0.047] (LiDAR leads by about half a scan).
  comma: **GNSS speed lags CAN by 0.224 s [0.192, 0.290]**; IMU-vs-GNSS yaw -0.26 s, but correlation peak only 0.16 (low confidence).
- **A3 sigma honesty on clean VAL: NOT MET** (rule: |mean z| <= 0.25, 0.8 <= std <= 1.25, p99 |z| <= 4 after the train recalibration).
  - Honest: KITTI gps-lidar speed (val z mean +0.03, std 0.98), gps-lidar yaw, gps-lidar lateral, gps-imu yaw. These are already honest with the PUBLISHED sigmas
    (e.g. gps-lidar speed mean +0.22, std 1.02).
  - Not honest: KITTI gps-can (+0.86 / 1.15), lidar-can (+1.88 / 1.72), imu-lidar yaw (-0.23 / 0.72); comma gnss-can and gnss-wheel
    (std 0.70), gnss-imu yaw (0.74). Published comma sigmas are **too wide by about 10x** (z std 0.09; CAN floor 0.3 m/s, GPS 0.45 m/s vs real
    noise about 0.1 m/s) and biased (mean +0.27).
  - Causes, found on train + val only (`results/WP6/s1_diag.json`): (1) the CAN error is a RELATIVE scale (CAN = 0.990 x GNSS on every
    comma route), so a constant bias is the wrong model; (2) my KITTI CAN simulator drew an independent 2% tyre scale per drive
    (copied from the WP1 odometry model). Real data shows 0.15% route-to-route spread on one car. Val drive 0027 drew -4.8%;
    (3) the norm of a noisy GPS displacement has a Rayleigh bias at standstill; (4) gyro / GNSS sensor-rate regimes (old comma routes with a 10 Hz gyro
    have 2-4x the yaw residual).
  - Revised design R (written in the notes before it was run; validation once, labelled): R1 linear bias, R2 one-vehicle CAN scale, R4 forward-displacement
    speed. On val it makes KITTI gps-can honest. lidar-can (mean -0.33), imu-lidar (std 0.73) and all comma pairs (std 0.70-0.75: the train
    variance is inflated by the older, noisier routes, so the error is on the safe side) are still not honest. The verdict stays NOT MET.
  - Test (once, after every choice): comma CAN-vs-GNSS slope 0.9897; with R1 the speed bias disappears (test z mean +0.05, std 0.73;
    pre-registered model -0.58 / 1.00); comma yaw test mean -0.46 (gyro bias drift?); KITTI gps-lidar pairs stay honest.
- **A4 tests: MET**: 12 new tests (`tests/crossdomain/test_witness.py`); full suite 315 passed, 0 failed.
- **A5 API: MET**: `crossdomain/__init__.py` docstring and the API section below.
- **A6 CAN unit**: ROAD 0.01 km/h is **PLAUSIBLE, not confirmable** (highway p99 91.0 km/h, max p99 1 s accel 2.04 m/s^2; caveat:
  0.01 mph would also pass the range test). comma: the method works. Raw 0xAA counts regressed on GNSS give 0.01012 km/h/count, offset
  -68.7 km/h (comma's own decoding: exactly 0.01 and -67.67), i.e. the unit is recovered within the 1% CAN scale. CAN-vs-GNSS slope 0.9900
  [0.9894, 0.9906] is within 1 +- 0.05, but the val residual is not honest, so the relation is NOT "validated" by the A6 wording.
- **Main finding for S2**: on real data the CAN-vs-GNSS disagreement is about 0.1 m/s after a fixed 1% scale and a 0.22 s latency. That is about 10x
  tighter than the published combined sigma at highway speed (0.95 m/s), so S2 should use the train-fitted models (a 0.5 m/s CAN
  speed spoof is a few sigma there; to be tested in S2).
  The published CAN sigma (0.3 m/s floor) and GPS sigma (0.45 m/s) are honest only for KITTI's noisy simulated receiver.
- No attack verdict in S1 (by design).

## Goal of the step
Collect MotionEstimate streams from the frozen domain outputs, put them on a common time grid with documented interpolation, measure latency,
and compute per-pair residuals normalised by the published sigmas. Then check that the sigmas are honest, recalibrate on train if not, and document the API for S2.

## Acceptance rule (notes/WP6_crossdomain.md, "S1 start", 2026-10-22, written before any result)
A1 streams for every available source and pair, with counts per split. A2 latency per pair with a 95% bootstrap CI on clean train, plus a unit test
(0.30 s within 0.05 s). A3 on CLEAN VAL: |mean z| <= 0.25, 0.8 <= std z <= 1.25, p99 |z| <= 4.0. If the published sigmas fail, use a train-fitted SigmaModel
(constant bias + sqrt(a^2 + (b v)^2)). PASS if every pair is honest on val after recalibration. Test is run once at the end and reported.
A4 unit tests. A5 documented API. A6: ROAD unit plausible if highway p99 is in [60, 160] km/h and p99 |1 s accel| <= 4 m/s^2. comma: slope within 1 +- 0.05
and an honest val speed residual = "validated".

## What was done
- Code: `crossdomain/witness.py` (frames, 1 Hz interval-mean grid, latency, pair tables, SigmaModel, honesty), `crossdomain/kitti.py`,
  `crossdomain/can_sim.py`, `crossdomain/comma.py`, `crossdomain/v2x_self.py`, `crossdomain/__init__.py` (API).
- Tools: `tools/WP6_S1_comma_fetch.py` (HTTP range reads, python -I), `WP6_S1_road_wheel.py`, `WP6_S1_kitti.py` (build/dev/test), `WP6_S1_comma.py`
  (build/dev/test), `WP6_S1_diag.py` (train + val only), `WP6_S1_tables.py`.
- Tests: `tests/crossdomain/test_witness.py` (12).
- Data: KITTI D04 (WP1 stream cache, clean phase-0 runs; WP1 LiDAR odometry cache), ROAD D05 train ambient captures (wheel statistics only), comma2k19 D22
  Chunk_1 (processed logs only: 538 MB transferred, 1.31 GB on disk, MIT; DATASETS.md D22 row updated). Cache `../data_extra/cache_v3/WP6/` = 79 MB.
- Frozen producers were imported only, never modified.

## Alignment (documented)
1 Hz integer-second grid. Each quantity is compared as its mean over (t-1, t]. gps / lidar displacements already are means and are matched within 0.05 s.
Instantaneous sources (can held value, imu, gnss, v2x) are integrated piecewise-linearly (cumulative trapezoid); at 1 Hz this is the trapezoid of the samples at
t-1 and t, exact for constant acceleration. A grid point is dropped if a gap longer than 1.5 s touches the interval (no extrapolation). Latency is removed by shifting the
lagging stream before gridding (comma: CAN, wheel and imu shifted by the train lags). Yaw / lateral sigmas are not published by the contract. WP6 derives them from the
producers' noise models: compass 2 deg per fix gives gps yaw sigma 0.049 rad/s; gyro 0.005 rad/s gives imu 0.0035; LiDAR S5 median yaw error gives 0.0015.

## Results
Every number is in `results/WP6/s1_kitti_dev.json`, `s1_kitti_test.json`, `s1_comma_dev.json`, `s1_comma_test.json`, `s1_road_wheel.json`,
`s1_sigma_models.json`, `s1_acceptance.json`. All tables (counts, latency, z per pair / split / sigma, sigma models, ROAD per capture) are in
`results/WP6/s1_tables.md`, generated from the JSON.
Acceptance: A1 MET, A2 MET, A3 NOT MET, A4 MET, A5 MET, A6 ROAD plausible (not confirmable), comma relation not "validated" (A3 part).

## API for S2 ("which domain lies")
```
from crossdomain import witness as W
f = W.to_frame(estimates)                          # any MotionEstimate list (one source)
g = W.to_grid(f, grid, lag=L)                      # 1 Hz means over (t-1, t]; kind from W.SOURCE_KIND
tab = W.pair_table(ga, gb, "gps", "lidar", "speed")   # columns t, pair, quantity, a, b, r, s, z, v
m = W.SigmaModel.from_dict(json["kitti_R"]["models"]["gps-lidar speed"])   # results/WP6/s1_sigma_models.json
z = m.z(tab["r"], tab["v"])                        # train-calibrated z; W.honesty(z) for checks
lag = W.estimate_lag([W.lag_covariance(ta, a, tb, b) for each group])
```
Model sets in `s1_sigma_models.json`: `kitti`, `comma` (pre-registered), `kitti_R`, `comma_R` (R1 linear bias, recommended); comma lags and gyro
axis/sign are stored with them. Claims: gps, can, v2x. Witnesses (an attacker of another domain cannot move them): lidar, imu.
The suspect domain is the one shared by the pairs with large |z| and absent from the agreeing pairs.

## Ablation
Not applicable (no detection layer in S1).

## Problems, surprises, open questions
1. A3 NOT MET. Should S2 use the R models (honest on KITTI for every gps pair; comma conservative by about 30%), or should S2 first get a per-sensor-configuration
   calibration (comma routes with a 10 Hz vs a 100 Hz gyro)? I recommend R with the remaining deviations stated. Decision for the supervisor.
2. WP1's odometry model (independent N(0, 2%) scale per drive, `gps/stream.py`) is not realistic for one car (real: 0.15% route-to-route). This
   affects WP1's dead-reckoning layers only as a pessimistic assumption. Information for WP1, no request filed.
3. KITTI val is small (3 drives, 50-56 grid points per pair): the mean-z bound is sensitive to a single drive.
4. The published CAN / GPS speed sigmas are about 3-10x too wide for real sensors: S2 should use the calibrated models, not the published sigmas.
5. comma CAN is a Toyota-style 0xAA (16 bit, offset -67.67 km/h); ROAD 0x6e0 is 14 bit with no offset. comma demonstrates the calibration
   method, not the ROAD unit itself.
6. comma2k19 was fetched by range requests (processed logs only) instead of downloading the 10 GB chunk: same data, 6% of the transfer.

## Proposed next step
S2: "which domain lies". Inject single-domain attacks on the KITTI streams (GPS spoof incl. the WP1 attack set, LiDAR odometry corruption, CAN
speed spoof through `can_sim`) and on comma (CAN speed spoof, GNSS offset). Use the R sigma models, pairwise |z| CUSUM, and majority logic with a
1% budget per pair on validation.
