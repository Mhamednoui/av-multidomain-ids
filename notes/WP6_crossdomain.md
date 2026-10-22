# WP6 Cross-domain: working notes

Owner folders: crossdomain/, fusion/, tests/crossdomain/, tests/fusion/, results/WP6/, tools/WP6_*.
Caches: ../data_extra/cache_v3/WP6/ (<= 5 GB). Data download: ../data_extra/D22_comma2k19/.

## 2026-10-22 S1 start: motion witnesses (plan, written BEFORE any result)

### Inputs read
RULES, STATUS, WP6 file, ARCHITECTURE (Evidence, MotionEstimate: t, source, speed, yaw_rate,
displacement (dx fwd, dy left) over the last second in the BODY frame, sigma = 1-sigma of speed),
ORCHESTRATOR DECISION rows, M1_GPS s8, M1_CAN s9, M1_V2X s8/s10, WP1/WP2/WP5 briefs.

Frozen producers (never modified, imported only):
- gps.domain.gps_motion_estimates(run_df): source "gps", 1 Hz, displacement of the REPORTED position
  rotated by the compass heading, yaw_rate from compass heading change, sigma 0.45 m/s. A CLAIM.
- gps.lidar_odom.motion_estimates(t_fix, P, tp, quality_ok): source "lidar", 1 Hz, ICP odometry
  (cached per drive in results/WP1/cache/lidar_odom_<d>.npz), sigma = hypot(0.0821, 0.0046 v), x3 if
  ICP quality poor. Independent WITNESS (a GPS or CAN attacker cannot change it).
- can.domain.CanDomain.motion_estimates(t, ids, dlc, B): source "can", one per capture second,
  speed = mean of 4 wheel speeds of 0x6e0 (14-bit signals) HELD at the end of the second x 0.01 km/h
  (assumed unit), sigma = max(0.3, 3% v), no yaw / displacement. A CLAIM (CAN attacker controls it).
  Note: instantaneous value at t, while GPS / LiDAR give the MEAN speed over (t-1, t]: under an
  acceleration a the two differ by ~a/2 -> alignment must handle this (see below).
- V2X: the WP5 schema has received messages only (sender, x, y, speed, heading, yaw_rate). VeReMi
  here is the combined CSV (no receiver id, no own-GPS type-2 records); Tampa = RSU-heard BSMs.
  No dataset gives the ego's own BSM/CAM on a car that also has GPS / LiDAR / CAN logs. -> V2X
  provides OTHER vehicles' motion only; S1 gives an adapter (BSM track -> MotionEstimate "v2x")
  for a future ego self-report, no evaluable pair. An ego BSM is built from the ego GNSS, so even
  if logged it would not be independent of GPS (a GPS spoof propagates into it).

### Data plan
(a) KITTI (23 drives, WP1 split: TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; rest
    train). Streams from the WP1 stream generator (gps/stream.py build_kitti), CLEAN runs only
    (attack "none"), phase 0 grid for the distribution statistics (the 10 phases are the same
    seconds shifted by 0.1 s: using all would count each second 10 times).
    - gps (claim), imu (gyro yaw_rate column of the stream: N(0, 0.005 rad/s) on OXTS wz),
      lidar (witness), can_sim (SIMULATED wheel speed, below).
    - CAN simulation from full-rate OXTS forward speed vf (10 Hz) -> 0x6e0 frames at the ROAD
      message period, 4 wheels (left/right split by the OXTS yaw rate, track width 1.6 m),
      per-drive tyre-scale error N(0, 2%) (same as WP1 odometry), additive noise and 0.01 km/h
      quantisation with noise level measured on ROAD TRAIN ambient captures
      (tools/WP6_S1_road_wheel.py), encoded into payload bytes with the ROAD DBC layout and decoded
      by the FROZEN CanDomain.motion_estimates (so the real interface is exercised).
(b) comma2k19 Chunk_1 (D22, MIT): only processed_log (CAN speed / wheel_speed / raw_can, GNSS,
    IMU) and global_pose fetched by HTTP range reads (video and raw logs skipped).
    Split BY ROUTE (decided before looking at any residual): routes sorted by start time,
    train = first 60%, val = next 20%, test = last 20% (rounded, >= 1 route each).
    Pairs: can_speed (decoded) vs gnss (u-blox live velocity), wheel_speed vs gnss, imu gyro vs
    gnss course rate where available.

### Alignment (documented choice)
Common grid: 1 Hz (every frozen producer is 1 Hz). Each source is converted to the MEAN over
(t-1, t]: displacement-based sources (gps, lidar) already are; instantaneous samples (can held
value, imu gyro at the fix) use the trapezoid of the samples at t-1 and t (exact for a constant
acceleration). Grid points without both samples are dropped (no extrapolation). Latency: estimated
on clean TRAIN at native rate (10 Hz KITTI; comma CAN 100 Hz-ish vs GNSS 10 Hz resampled to 0.01 s)
by maximising the cross-correlation of the first differences (accelerations) over lags +-2 s;
95% CI by bootstrap over drives / routes. The measured latency is applied as a shift before the
1 Hz conversion.

### Residuals
Per pair (a, b) and quantity q in {speed, yaw_rate, displacement (dx, dy)}:
z = (q_a - q_b) / sqrt(sigma_a^2 + sigma_b^2) with the PUBLISHED sigmas. For yaw_rate and
displacement no sigma is published by the contract: WP6 derives them from the producers' documented
noise models (compass 2 deg per fix, gyro 0.005 rad/s, LiDAR rel error) and states this.

### ACCEPTANCE RULE (S1; written before results)
- A1 Streams: MotionEstimate streams exist for every available source on each dataset and every
  available pair is listed with its sample count per split (KITTI: gps, imu, lidar, can_sim;
  comma: can, wheel, gnss, imu; V2X: statement + adapter). PASS if all are produced.
- A2 Latency: per pair, a cross-correlation latency with a 95% bootstrap CI on clean train; a unit
  test recovers an injected lag of 0.30 s within 0.05 s. PASS if reported for every pair with
  native-rate data and the test passes.
- A3 Sigma honesty, per pair and quantity, on CLEAN VAL: honest if |mean z| <= 0.25,
  0.8 <= std z <= 1.25 and 99th pct of |z| <= 4.0. If NOT honest with the published sigmas, a
  per-pair recalibration is fitted on TRAIN only: sigma_pair(v) = sqrt(a^2 + (b v)^2) (two
  parameters, least squares on binned squared residuals) plus a constant bias (median train
  residual); then judged again on VAL. PASS if every pair is honest on VAL after recalibration;
  raw (published-sigma) results are reported next to it. Test is computed ONCE at the end, reported,
  not used for any choice.
- A4 Unit tests for every new module; full suite passes.
- A5 Documented API for S2 (crossdomain/__init__ docstring + report section).
- A6 CAN unit (ROAD 0.01 km/h): judged PLAUSIBLE if on ROAD train captures, with that unit,
  (i) the 99th pct of the highway drive speed lies in [60, 160] km/h and (ii) the 99th pct of
  |1 s speed change| <= 4 m/s^2 on all captures; CONFIRMED is impossible without an independent
  speed on the ROAD car (stated). comma2k19: the CAN-vs-GNSS scale (slope through the origin of
  CAN speed on GNSS speed, train routes, v > 5 m/s) is reported with a CI; the relation is
  "validated" if the slope is within 1 +- 0.05 and the val speed residual is honest after A3.
- No attack detection verdict in S1.

## 2026-10-22 S1 first results (dev: train + val; test NOT yet run)

Data fetched: comma2k19 Chunk_1 processed logs only (HTTP range reads from the HF mirror
commaai/comma2k19 raw_data/Chunk_1.zip, 8.73 GB chunk, 538 MB transferred, 1.31 GB on disk in
../data_extra/D22_comma2k19/Chunk_1; MIT). 20 routes, 189 one-minute segments, one car
(dongle b0c9d2329ad1606b; CAN 0xAA = Toyota-style wheel speeds). Split by route (sorted by date):
train 13, val 4, test 4. Cache ../data_extra/cache_v3/WP6 = 79 MB.

ROAD wheel statistics (results/WP6/s1_road_wheel.json, train ambient captures): 0x6e0 period
0.0100 s, quantum 1 raw unit, short-term noise 0.0149 m/s, wheel spread 0.7% of speed.
A6 with unit 0.01 km/h: highway p99 91.0 km/h (PASS), max p99 1 s accel 2.04 m/s^2 (PASS) ->
PLAUSIBLE. Caveat: 0.01 mph would give highway p99 146 km/h, also inside [60, 160]: the range test
alone does not discriminate well; the accel test (x1.61 -> 3.3 m/s^2) also passes. Not confirmable
on ROAD. Wheel / 0xd0.Unknown_5 (speedometer target) raw ratio 0.864-0.866 on every capture.

comma2k19 (results/WP6/s1_comma_dev.json): CAN speed = 0.9900 x GNSS speed [0.9894, 0.9906]
(train routes, v > 5), val 0.9902; per-route 0.988-0.993 -> relation VALIDATED (A6 slope rule).
Raw 0xAA counts vs comma's decoded speed: exactly 0.01 km/h/count, offset -67.67 km/h; vs GNSS
(the method that would calibrate ROAD if it had GNSS): 0.01012 km/h/count, offset -68.7 km/h, i.e.
the unit is recovered to 1.2% (= the 1% CAN-vs-GNSS scale).
Latency (train): GNSS speed lags CAN by 0.22 s [0.19, 0.29] (lag -0.224 = CAN leads); IMU yaw vs
GNSS bearing-rate -0.26 s but the correlation peak is only 0.16 (bearing differences are noisy):
low confidence. KITTI: OXTS vs LiDAR speed lag 0.004 s [-0.031, 0.035]; yaw rate -0.053 s
[-0.062, -0.047] (LiDAR yaw leads OXTS by ~half a scan period).
Gyro axis chosen on train: axis 2, sign -1 (corr -0.976).

A3 VERDICT on VAL (pre-registered model): NOT MET.
- KITTI honest with published sigmas: gps-lidar speed / yaw / lateral, gps-imu yaw. Not honest:
  gps-can (mean 0.60), lidar-can (mean 0.54, std 0.80), imu-lidar yaw (std 1.62, p99 5.3).
  After the train recalibration: still not honest for gps-can, lidar-can, imu-lidar.
- comma: published sigmas far too wide (z std 0.09) and biased (mean 0.27): recalibrated val
  std 0.70 (speed pairs), 0.74 (yaw): NOT honest.
Diagnosis (tools/WP6_S1_diag.py, results/WP6/s1_diag.json, train + val only):
 (1) comma: the CAN-vs-GNSS residual is a RELATIVE bias (rel. bias 0.8-1.1% on every route) plus
     ~0.1 m/s noise; the pre-registered constant bias (median r = 0.25 m/s) is wrong at low speed
     (routes at 6-9 m/s: bias 0.06-0.09) and inflates the train variance; val routes are all fast.
 (2) KITTI CAN sim: per-drive independent tyre scale N(0, 2%) (copied from WP1 odometry) is not
     realistic for ONE car: on the real comma car the per-route scale spread is 0.15% (std of 13
     train-route slopes = 0.00145). Val drive 0027 drew -4.8% and dominates the val CAN pairs.
 (3) KITTI gps speed = norm of a noisy displacement: Rayleigh bias at standstill (drives 0017,
     0060: +0.55..0.69 m/s at v ~ 0.3 m/s).
 (4) comma yaw / KITTI imu-lidar: heavy tails, sensor-rate regimes (comma train routes with 10 Hz
     gyro have 2-4x the residual of 100 Hz routes). NOT addressed (would need per-configuration
     calibration; left as finding).

REVISED DESIGN R (written before evaluating it; judged on VAL once, labelled "revised"; test run
once afterwards for BOTH the pre-registered model and R; the A3 verdict stays NOT MET whatever R gives):
- R1 SigmaModel(bias="linear"): bias(v) = c0 + c1 v (least squares on train), variance as before on
  the de-biased residuals.
- R2 CAN simulator: one VEHICLE scale draw N(0, 2%) for all KITTI drives (one car) + per-drive
  N(0, 0.15%) (comma train per-route spread); everything else unchanged.
- R4 speed of displacement sources (gps, lidar) = forward displacement dx over 1 s (signed,
  unbiased at standstill) instead of |displacement|; sigma unchanged.

## 2026-10-22 S1 revised design R on val, then test (once)

Val, revised R (s1_kitti_dev.json revised_R, s1_comma_dev.json revised_R): KITTI gps-can honest
(mean -0.18, std 1.05); lidar-can still not (mean -0.33, std 0.93); imu-lidar not (std 0.73);
comma speed pairs std 0.70 / 0.75 (mean -0.08 / -0.07: bias fixed, variance conservative),
yaw 0.74. A3 verdict stays NOT MET.
Test (once; s1_kitti_test.json, s1_comma_test.json): KITTI gps-lidar speed / yaw / lateral and
gps-imu honest (published and recalibrated); imu-lidar std 2.87 published, 1.28 recalibrated, p99
4.05 (not honest); lidar-can not honest in both designs (pre-registered mean +0.52, R +0.39).
comma test slope 0.9897 [0.9890, 0.9909]; gnss-can recalibrated pre-registered mean -0.58 /
std 1.00, R mean +0.05 / std 0.73; gnss-imu yaw R mean -0.47 / std 1.28.
Latency test: OXTS-LiDAR speed -0.015 s [-0.059, +0.026], yaw -0.059 s [-0.063, -0.054].
Unit tests: tests/crossdomain/test_witness.py 12 pass; full suite 315 passed, 0 failed.
Acceptance file: results/WP6/s1_acceptance.json; tables results/WP6/s1_tables.md; report
reports/WP6_S1.md.
Pitfalls: Windows forbids "|" in file names (comma route ids): replaced by "_"; the WP1 KITTI
stream comes from the WP1 temp pickle (wp1_s4_kitti.pkl in the temp folder, rebuilt identically
by gps.stream.build_kitti if missing); comma gyro has duplicated timestamps (harmless for the
trapezoid); comma has two sensor regimes (old routes: GNSS 5 Hz and gyro 10 Hz; newer: gyro ~100 Hz).
