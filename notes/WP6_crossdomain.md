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

## 2026-10-22 S2 start: "which domain lies" (plan + acceptance rule, written BEFORE any S2 result)

Binding (ORCHESTRATOR 2026-10-22): design R (R1 linear bias, R2 one-vehicle CAN scale, R4 forward speed)
+ per-sensor-setup sigma calibration fitted on TRAIN, judged on val; conservative sigmas OK, too narrow not.

### Witness graph (nodes = independent witnesses; domain in brackets)
KITTI: gps [gps, claim], lidar [lidar], can [can, SIMULATED 0x6e0 via frozen CanDomain], gyro [imu],
compass [imu] (the WP1 "gps" yaw is the compass heading column, not the receiver).
Edges (z from the S1 kitti_R SigmaModels, train-fitted; KITTI has one sensor setup):
gps-lidar speed (R4 fwd), gps-can speed, lidar-can speed, gps-lidar lateral, compass-lidar yaw,
compass-gyro yaw, gyro-lidar yaw.
comma2k19: gnss [gps], can (vehicle-speed message) [can], wheel (0xAA wheel-speed message) [can,
same bus], imu (gyro) [imu]. Edges: gnss-can speed (Doppler), gnss-wheel speed, can-wheel speed (new),
gnss-can pspeed and gnss-wheel pspeed (pspeed = |GNSS position change over (t-1, t]|: needed because a
position-only spoof leaves the Doppler speed true), gnss-imu yaw. Lags from S1 (train).
comma per-setup calibration: setup = route sensor regime from sample rates only (no labels): gyro
class g10 (<= 20 Hz) / g100, GNSS class n5 (<= 6.5 Hz) / n10. Two candidate definitions, chosen on
VAL: A = gyro class; B = gyro x gnss class with fallback to the gyro class when the cell has < 3
train routes. Models (SigmaModel bias="linear") fitted on TRAIN routes of the setup.
Choice: candidates passing AC1 on val; among them std closest to 1 (mean |std - 1| over edges);
if none passes, the one with fewest failing edges (reported as NOT MET).

### Sequential test and calibration
Per edge two-sided CUSUM on z: S+ = max(0, S+ + z - k), S- = max(0, S- - z - k), stat = max(S+, S-);
z NaN -> state held. Candidates k in {0.25, 0.5, 1.0} and "inst" (stat = |z|), chosen per data set on
VAL: max mean run-level detection over the SELECTION attacks (below) at the val 1% threshold.
Calibration on VAL clean rows: per-edge ECDF (common.calibration) of stat; layer statistic
L = max over observed edges of ECDF_e(stat_e); threshold tau = common.metrics.budget_threshold(L, 0.01)
(tie-safe). Edge alarm: ECDF_e >= tau. Layer alarm = any edge alarm.

### Blame logic (per second)
A = alarming edges (collapsed to node pairs). If A empty: no alarm. Blame node D iff {D} is the
UNIQUE minimum vertex cover of A, D has alarming edges to >= 2 distinct partners, and at least one
observed, NON-alarming edge joins two of those partners ("the others agree"). Otherwise "undecided"
(2 witnesses only, two liars, or no confirmed agreement). Blamed domain = domain of D. Emitted as
Evidence(domain "cross", layer "L2", name "cross.which_domain_lies", reason names D and the edges).

### Attacks (single-domain unless stated; onset index k0 ~ U{3..n-3} per run like WP1)
KITTI (val + test drives, 10 phases): GPS = WP1 runs of drift, accel_drift, doppler_spoof, meaconing
(the exact runs the frozen GPS domain was scored on). LiDAR odometry stream (what an attacker of the
point cloud can cause in ICP): lidar_scale (dx, dy x (1+s), |s| ~ U(0.02, 0.2), random sign),
lidar_bias (forward offset ramped at 0.4 m/s^2 to |b| ~ U(0.2, 2) m/s), lidar_yaw (yaw-rate bias
|w| ~ U(0.005, 0.05) rad/s). CAN wheel speed (masquerade of the speed signal; applied to the decoded
native CAN speed before gridding): can_scale (|s| ~ U(0.02, 0.2)), can_offset (ramped 0.4 m/s^2 to
|b| ~ U(0.2, 2) m/s, clipped >= 0), can_freeze (held at the onset value).
Coordinated: gps_can (along-track Doppler-consistent GPS spoof, w ramped at 0.4 m/s^2 to
|w| ~ U(0.2, 3) m/s, AND the CAN speed raised by the same w: GPS and CAN agree).
comma (val + test routes, 120 s windows, 2 draws per window and attack, onset 30-90 s into the
window): gnss drift / accel_drift / doppler_spoof / meaconing (same equations and severity ranges as
gps/stream.py, applied at native GNSS rate to position, Doppler velocity and bearing), can_scale /
can_offset / can_freeze on the vehicle-speed message. Coordinated: gnss_can (along-track Doppler spoof
+ same offset on the can message); extra: can_bus (BOTH CAN speed messages scaled together: one domain,
two messages on one bus).
SELECTION attacks for the val choices: drift, accel_drift, lidar_scale, lidar_bias, can_scale,
can_offset. HELD OUT of every choice: doppler_spoof, meaconing, lidar_yaw, can_freeze, coordinated.

### Metrics
Run level: detection = any layer alarm at t >= onset; blame of a detected run = first decided blame at
or after onset, else undecided; delay = first alarm - onset. FA: clean rows (row level) and clean runs.
Comparison: frozen GPSDomain (results/WP1/frozen_gps) on the same KITTI runs; union with cross.
The CAN domain (ROAD-specific models) cannot run on simulated KITTI CAN or on the comma car: stated,
M1-CAN numbers quoted as context only.

### Acceptance rule (S2)
AC1 sigma honesty, not too narrow, clean VAL, every edge of the chosen calibration:
    |mean z| <= 0.25, std z <= 1.25, p99 |z| <= 4.0 (std < 0.8 allowed = conservative).
AC2 FA on clean TEST rows <= 1.5% per data set (threshold from val at 1%).
AC3 mean run-level detection over the single-domain attack types on TEST >= 70% per data set.
AC4 among detected single-domain attack runs on TEST: correct blame >= 80% and wrong blame <= 5%,
    per data set (undecided is not correct).
AC5 KITTI test, doppler_spoof + meaconing pooled: GPS domain OR cross detects >= 10 points more runs
    than the GPS domain alone (union FA reported).
AC6 coordinated attacks (prediction, not pass/fail): KITTI gps_can -> LiDAR wrongly blamed in most
    detected runs; comma gnss_can -> wheel wrongly blamed; comma can_bus -> gnss wrongly blamed.
AC7 unit tests pass; Evidence contract emitted.
Test is run ONCE after every choice is frozen (s2_choices.json written before the test stage).

## 2026-10-22 S2 dev + test run 1 (verdict), then a bug in the comma setup classification

Dev (val, results/WP6/s2_dev_run1.json): AC1 KITTI fails on lidar-can (mean -0.33, as in S1); comma A and B pass.
Chosen (s2_choices_run1.json): comma setup B, KITTI k = inst (sel. 81.1% vs 80.0% for k = 1), comma k = 0.25.
Test run 1 (s2_test_run1.json, s2_acceptance_run1.json, s2_tables_run1.md): KITTI FA rows 4.42%, comma 9.90%
(full-route continuous CUSUM 49.5%): AC2 NOT MET on both. Details in the report.
BUG found after the test, when generating the tables: the route sensor rate used len(t) / duration; the old comma
routes have every gyro timestamp duplicated, so their 10 Hz gyro read as 20.0-20.1 Hz, above the 20 Hz class limit:
6 of 7 old routes went into the "g100" class. The per-setup calibration (binding) was therefore NOT done as written.
Decision (before re-running anything): fix rate() to count unique timestamps (S1 diag did this), rebuild the comma
cache, re-run dev on VAL (choices may change; KITTI is unaffected and deterministic), then run the comma test ONCE
more, labelled "SECOND EXPOSURE (bug fix)". Run 1 stays reported as the first verdict, side by side.

## 2026-10-22 S2 run 2 (after the bug fix) and verdict
Dev run 2 (s2_dev.json): comma setup A chosen (A and B both fail AC1 on 2 edges: gnss-can / gnss-wheel speed
mean -0.32 (A) / -0.41 (B); A has std closer to 1). With true per-setup models the speed noise is ~0.08 m/s
and a 0.1-0.2% route-to-route CAN scale shows as a bias. k: KITTI inst, comma 0.25 (unchanged).
Test run 2 = SECOND EXPOSURE (s2_test.json, s2_acceptance.json, s2_tables.md): comma FA rows 5.36% (speed edges
0.0%, gnss-imu yaw 4.69%), full-route continuous 35.7% (route 2018-08-17--12-07-08: 85%); detection 100% all
attacks; blame 96.9% correct / 0% wrong / 3.1% undecided; inst ablation FA 2.29%. KITTI identical to run 1:
FA 4.42% (drive 0039 9.8%; gyro-lidar yaw edge 2.4%), mean detection 74.4%, blame 48.9 / 6.1 / 44.9%.
GPS domain on the same KITTI test runs: FA 1.83% (= M1-GPS), Doppler 68.6 / meaconing 61.4 / gps_can 50.0%;
cross 62.9 / 64.3 / 81.4%; union Doppler+meaconing 70.7% (+5.7 pts, AC5 NOT MET; union FA 5.75%).
Coordinated: KITTI gps_can -> lidar 30 / undecided 26 / gps 1 of 57; comma gnss_can -> wheel ("can") 31/32;
can_bus -> gnss 32/32 (predicted).
Verdict: AC1 NOT MET (KITTI lidar-can; comma run 2), AC2 NOT MET (both), AC3 nominal only (FA over budget),
AC4 MET comma / NOT MET KITTI, AC5 NOT MET, AC6 confirmed, AC7 MET (18 crossdomain tests pass).
Pitfalls: (1) comma old routes duplicate every gyro timestamp: count unique timestamps for sample rates.
(2) low-k CUSUM + real sensor bias drift = runaway alarms; val with 4 routes / 19 windows cannot see it.
(3) KITTI val k choice by detection alone picked inst, which halves blame quality (val 56% vs 77% at k 0.5).
Report: reports/WP6_S2.md.

## 2026-10-22 S2b start (VALIDATION ONLY; no test scoring) - plan + acceptance rule, written before any S2b result
Supervisor (2026-10-22): S2 APPROVED with misses; comma run 2 official; comma's two CAN speed messages = ONE domain.
Data = DEV groups only: KITTI 16 drives (13 train + 3 val, WP1 split), comma 17 routes (13 train + 4 val). Test never read.
1. Out-of-fold z: for each dev group g, SigmaModels (bias "linear") fitted on the clean rows of the OTHER dev groups
   (KITTI: phase-0 clean runs; comma: clean whole routes of the same setup class A = gyro class from unique-timestamp
   rates). Disclosed leak: the calibration groups' own z use a model that includes the held-out group's clean rows.
2. Leave-one-group-out thresholds (like WP1 LODO): per-edge ECDF + tie-safe 1% tau fitted on the clean statistics of
   the other dev groups; scored on the held-out group; pooled over folds.
3. Domain-level blame (all data sets, one rule): nodes = witnesses, but blame is about DOMAINS (trust boundary: an
   attacker of a domain can spoof all its witnesses). Intra-domain edges (comma can-wheel, KITTI compass-gyro) mark the
   domain self-inconsistent. If exactly one domain D is self-inconsistent and every alarming cross-domain edge contains D:
   blame D. If none is: unique 1-domain minimum vertex cover of the alarming cross-domain pairs, >= 2 alarming partner
   domains, partners agree on an observed non-alarming edge -> blame D. Else "undecided".
   Expected consequence (stated now): comma GNSS spoofs become mostly "undecided" (speed has only 2 domains), comma
   single-message CAN spoofs are blamed on CAN, can_bus becomes undecided; KITTI lidar_yaw becomes undecided.
4. Sequential statistics (candidates): plain two-sided CUSUM k in {0.5, 1.0}; "inst" |z|; drift-compensated CUSUM
   (k in {0.5, 1.0}, bias time constant Tb in {60, 300} s): b <- b + (z - b) / Tb only while the edge's CUSUM stat < 2.0
   (frozen while suspicious), CUSUM on z - b, b = 0 at start.
5. Running mode: KITTI = each run (drives 5-90 s). comma = CONTINUOUS whole routes: clean FA on whole routes; an attack
   episode (S2 120 s window draws) is spliced into its route and the statistic continues from the clean state at the
   window start; detection counted from onset to the window end.
6. Choice (per data set, on the pooled held-out folds): among candidates with held-out FA rows <= 1.5%, max mean
   detection over the selection attacks (KITTI: drift, accel_drift, lidar_scale, lidar_bias, can_scale, can_offset;
   comma: drift, accel_drift, can_scale, can_offset). Held-out types reported, never used. Same folds choose and report:
   optimistic by the selection among 7 candidates (disclosed); the unbiased number comes from the S3 test.
Acceptance S2b:
 B1 chosen candidate: pooled held-out clean FA rows <= 1.5% on KITTI dev drives and on comma dev continuous routes;
    also reported per group, plus the worst group.
 B2 comma continuous: no dev route > 5% FA rows (the S2 test route had 85%).
 B3 mean detection over all single-domain attack types (held-out folds) >= 70% per data set.
 B4 blame among detected single-domain runs: wrong blame <= 5% per data set (correct and undecided reported; no
    correct-blame floor because the one-domain rule makes comma GNSS undecided by design).
 B5 unit tests pass (new tests for the drift-compensated statistic and domain-level blame).

## 2026-10-22 S2b round 1 (pre-registered candidates) - results (s2b_dev.json, s2b_choice.json)
Held-out-fold FA rows: KITTI plain/drift CUSUM 8.3-11.6% (drive 0070: 56-78%), inst 1.24%; comma 8.8-10.5%
(worst routes 50-98%), inst 1.10%. Choice by the rule: inst for both. Round-1 verdict: B1 MET (1.24 / 1.10%),
B2 NOT MET (comma worst route 12-02-42 11.6% with inst), B3 KITTI 57.5% NOT MET / comma 88.1% MET, B4 MET
(wrong blame KITTI 3.4%, comma 1.4%).
Why the drift compensation failed (dev diagnostics, scratch script, numbers in the round-2 json): the bias is frozen as
soon as the edge statistic reaches 2, i.e. within seconds when a route STARTS with a bias; it never adapts. Per-route
constant biases are real: comma speed edges -0.73..+0.55 sigma (route CAN scale), gnss-imu yaw -1.17..+0.89 (gyro
bias); KITTI drive 0070 (highway) lidar-can mean +1.16, gyro-lidar std 1.58 (ICP degenerate on a featureless road; the
LiDAR quality flag is not used by the SigmaModel); comma route 12-02-42 can-wheel glitches (z mean -31, std 119).

## 2026-10-22 S2b round 2 (POST-HOC, labelled; written before running it) - robust bias tracking
New statistic robust_cusum: warm-up of W samples (bias b = running mean of clip(z, +-3); no statistic emitted, edge
unobserved), then b <- b + clip(z - b, -c, c) / tb ALWAYS (no freeze: the clip bounds the absorption rate to c / tb
sigma per second, so a step or fast ramp is not absorbed, a constant route bias is), CUSUM on clip(z - b, +-6).
Candidates (c = 0.5): R2_wu60_k0.5_tb300, R2_wu60_k1_tb300 (warm-up 60 s, for continuous routes), R2_k1_tb120 and
R2_k0.5_tb120 (no warm-up, b = 0 at start). Same folds, same choice rule (round-1 + round-2 candidates together, FA <=
1.5% then max selection detection), same acceptance B1-B4. Optimism of choosing among 11 candidates on the same folds
is disclosed; the S3 test gives the unbiased number. Known limit: a bias present during the warm-up (an attack
already active at start-up) is learned as normal.

## 2026-10-22 S2b round 2 results and verdict (s2b_dev_r2.json, s2b_choice_r2.json, s2b_acceptance.json, s2b_tables.md)
comma: R2_wu60_k1_tb300 FA 1.85% (worst 12-02-42 17.8%, 08-34-47 8.8%), mean det 90.2%; R2_k1_tb120 4.3%; others
6-7%. KITTI: R2 no-warm-up 8.8-11.9% (0070); warm-up variants never emit (drives too short). comma VAL routes run
continuously (S2's 35.7% case): plain CUSUM k0.5 28.8%, inst 0.95%, R2_wu60_k1_tb300 0.11%.
Final choice over both rounds: inst for KITTI and comma (only candidates with FA <= 1.5%).
Verdict: B1 MET (KITTI 1.24%, comma 1.10%), B2 NOT MET (12-02-42 11.6%), B3 KITTI 57.5% NOT MET / comma 88.1% MET,
B4 MET (wrong blame 3.4% / 1.4%), B5 MET (328 tests pass). Report reports/WP6_S2b.md.
Domain-level blame: comma GNSS attacks 96-98% undecided (by design), CAN single-message 100% CAN, gnss_can 126/126
CAN, can_bus 67% undecided / 33% CAN; KITTI lidar_yaw undecided.
Next ideas (for S3, validation): LiDAR ICP quality flag in the sigma model (KITTI 0070); glitch filter for |z| > 20.

## 2026-10-22 S3 start: fusion v3 over 5 domains + cross-domain Evidence (plan + acceptance rule, written BEFORE any S3 result)
Inputs (frozen, read only): gps/domain.py (results/WP1/frozen_gps, per-layer calibrated scores + layer thresholds), can/domain.py
(results/WP2/s7_domain, per-layer L1 / L3c / L3d on the WP2 S7 window tables), V2X physics-only stack L1+L2+L3 (12 checks, recipe of
tools/WP5_S6_run.py without L4, refitted here on VeReMi val genuine without held-out types 6/12/17, same as WP5 / WP7), network stack H
(D10 S7 score tables + cal.pkl, max, threshold 0.99607 = results/WP4/s7_domain), cross-domain S2b frozen choice (inst |z|, out-of-fold
sigma models, LODO thresholds, domain-level blame) + the allowed val-only additions, LiDAR INTERIM = WP3 S1 v2-baseline XGB
(retrained_deployed.json, 1 - P(Normal)) + WP3 S2 L1 geometry union, max of the two val-normal ECDF scores (labelled interim).
Data construction (no dataset has all five domains): 1 Hz system clock; composite "drive" = one vehicle block plus same-length
segments of the other domains' own streams of the SAME split (val for development, test for the one test run; never train rows of a
domain for its attacks).
- Family K: vehicle block = one KITTI run (WP1 split, val 0011/0027/0035, test 7 drives, 8-45 s): GPS domain + cross_kitti on the same
  run; LiDAR scans of the same KITTI drive at a random offset (WP3 split = WP1 split; not time-synchronised with the run).
- Family C: vehicle block = one comma 120 s window (S2 route split): cross_comma only (no GPS domain: it needs KITTI-style wheel
  odometry / compass / LiDAR inputs; no LiDAR).
- CAN = ROAD 1 s windows (val clean = LOCO out-of-fold clean tables of WP2 S7 "folds", val attacks = attack_2 captures; test = the 4
  ambient test captures + attack_3 / coolant captures). Network = the D10 view of ONE host (192.168.10.50, id 49, the host the D10
  attacks target): tick value = per-layer max over the host's flows of the last CLOSED minute (D10 resolution is one minute; network
  Evidence is final when its minute closes), score 0 when the host has no flow; groups = (day, period) blocks. V2X = VeReMi, ego =
  a genuine sender, heard set = messages of other senders within 300 m of the ego's interpolated position (VeReMi has no receiver
  positions: a stated construction), class 12 messages dropped (artefact, never claimed), tick = max over the heard messages.
- Clean composites: every domain clean. Attack composites: exactly one domain attacked (vehicle-block families: GPS drift /
  accel_drift / doppler_spoof / meaconing; LiDAR-odometry lidar_scale / bias / yaw and CAN wheel-speed can_scale / offset / freeze seen
  by cross only (the GPS domain is scored on the clean run: approximation; the ROAD CAN domain sees a consistent speed rewrite as
  clean, M1-CAN); CAN families of ROAD; network families in the host view; V2X classes except 12; LiDAR PointDrop / IntensitySpoof
  (v2 generators, per-scan draws); GhostCluster box cloud ONLY as a labelled v2-comparison row (physically impossible on a
  single-return sensor); single-return phantoms NOT evaluated (no test rows exist; WP3 S9)). Coordinated scenarios: KITTI gps_can
  (GPS + CAN wheel odometry on the same car), comma gnss_can and can_bus (GNSS + CAN on the same car). Onset placed uniformly in the
  first half of the composite for non-vehicle-block attacks.
- Detected = a system alarm at a tick >= onset (for recorded-attack domains: while the attacked domain's label is active); delay =
  first such tick - onset. Attributed = that first alarm's explanation names the attacked domain (domain alarm) or, for vehicle-block
  attacks, a cross alarm. FA per tick on clean composites; FA per hour = alarm events (maximal runs of alarm ticks) per composite hour.
Fusion: per-domain tick score -> ECDF on clean ticks of validation half A -> zero-shot combiner max OR log-form noisy_or
(common.combiner) -> tie-safe 2% threshold on clean composite ticks of half B. Halves BY GROUP per domain (KITTI drive, ROAD capture,
D10 (day, period) block, VeReMi time block, comma route). Choice max vs noisy_or on half B: higher mean detection over the val attack
families (pooled K + C). Seen-attack row (labelled, never the headline): logistic on half-A composite ticks, threshold half B.
Cross additions (val only, S2b rule FA <= 1.5% then max selection detection, LODO dev groups): KITTI LiDAR ICP quality flag (z of
LiDAR edges / 3 when lid_ok is false), comma CAN glitch filter (an edge with |z| > 20 = sensor fault -> unobserved that second).
Ablation: each domain removed and each alone (threshold re-fitted on half B, combiner fixed). Test scored ONCE.
Acceptance (test, judged once):
 G1 FA on clean test composite ticks <= 3.0% for K and for C (2% val budget, 1.5x transfer allowance as in S2b).
 G2 K mean composite detection over the single-domain families (headline zero-shot combiner, v2-comparison rows excluded) >= 70%.
 G3 cross gain (K): all vehicle-block single-domain families, with cross vs without cross >= +10 points; GPS families alone >= +5.
 G4 every system alarm carries an explanation (100%); attributed detection >= 80% of detected single-domain composites.
 G5 no domain lost: per attacked domain, fused detection >= that domain alone (same composites, own 2% threshold) - 15 points.
 G6 unit tests pass. Reported, not judged: family C detection, coordinated scenarios, delays, v2 comparison (not like-for-like).
Exposure caveat: every domain test set was scored before (D10 6x per WP4 logs, ROAD 6x, VeReMi 2x, KITTI several); the fusion layer is
new and scored once; cross S2b choice gets its first test number here (labelled).

## 2026-10-22 S3 validation (before the test run; results/WP6/s3_crosschoice.json, s3_dev.json, s3_frozen.json)
- Cross additions (S2b LODO dev folds, inst): KITTI LiDAR quality flag changes NOTHING: the cached ICP quality (lid_ok) is True on 100% of
  dev scan pairs, even on drive 0070 (degenerate highway ICP is not flagged by the ICP quality test) -> base inst kept (FA 1.24%, sel 64.1%).
  comma glitch filter (|z| > 20 on a CAN / wheel edge -> unobserved): FA 1.10% -> 1.10%, worst route 12-02-42 11.6% -> 5.0%, selection
  detection 84.9 -> 85.7% -> CHOSEN by the rule. Side effect (not in the rule, flagged): correct domain blame 45.8% -> 18.0%, wrong 1.4 -> 3.4%,
  because large CAN spoofs (|z| > 20) are now read as sensor faults on that edge -> blame undecided. An attacker could hide behind the filter.
- Streams (tools/WP6_S3_streams.py, cache s3_*.pkl): V2X refit thresholds identical to WP5 S6 (max diff 0.0); network host view 84,269 val /
  114,429 test flows, flow FA on host benign 1.0% / 1.07%; LiDAR val-normal scan FA 0.91%.
- Fusion on validation half B (K: 400 clean + 60 per family; C likewise): max K FA tick 1.77%, mean det 65.6%; noisy_or K 1.99%, 73.8%;
  C max 91.9%, noisy_or 89.3%. Pooled: max 77.9%, noisy_or 81.0% -> noisy_or CHOSEN. Clean alarm EVENTS per hour 28-40 (2% of seconds).
- Smoke run of the test tool on validation packs (plumbing; temp folder): G5 fails by construction for weak domains (gps / lidar / cross alone
  get the whole 2% budget). Nothing changed after it.

## 2026-10-24 S3 TEST run (once) and verdict (s3_test.json, s3_acceptance.json, s3_tables.md, post-test diagnostic s3_diag.json)
- Headline noisy_or: K FA tick 6.36% [5.0, 7.7], 118.8 alarm events / clean hour, mean det 82.5% [75.2, 89.0] over 52 families;
  C FA 6.31%, 93.7 / h, 94.9%. max row 5.16% / 71.6%; seen-attack logistic (labelled) 5.83% / 81.3%.
- G1 NOT MET (both). G2 MET. G3 MET (+25.1 vehicle-block, +17.5 GPS). G4 MET (100% explained; attributed 93.4%). G5 NOT MET (LiDAR 62.7
  vs 100 alone [alone has 7.6% FA], cross 53.9 vs 79.3). Tests 364 passed.
- Diagnostic (no choice): every domain's clean tick scores are shifted up on test (CAN 3.0 -> 5.8%, V2X 1.4 -> 4.2%, cross 0.3 -> 1.3% above
  the 0.99 level); own-threshold tick FA on test: LiDAR 7.7% (155 ticks), V2X 6.1%, network 4.4%, CAN 3.4%; top contributor at clean
  alarms: network 38%. Causes: tick max over many samples depends on traffic density; network minute hold; small validation pools.
- Cross alone at own 1% threshold (first test number of the S2b choice): KITTI FA 1.07%, comma 1.82%.
- v2 view (not like-for-like): composite 50/50 accuracy K 68.8% (composite FA 44%), C 55.2% vs v2 95.23% at 1.06% FA (sample mix).
- Report reports/WP6_S3.md. Open: density-aware tick calibration + LOGO ECDFs + temporal correlator (S5, validation); glitch filter vs blame.

## 2026-10-24 S4 start: zero-day v3 (plan + acceptance rule, written BEFORE any S4 result)
Task: detection of attack types that no labelled step saw, with the v2 unseen-attack protocol, per domain and at system level (S3 composites,
label-free combiner, 2% budget), plus an evidence-novelty layer. Inputs: the S3 tick packs (cache s3_*.pkl), network S7 score tables (cal.pkl),
WP1 s8_raw.pkl (S7 GPS L3 column). Nothing of the frozen domains is changed.
**Held-out (unseen) types, fixed from earlier steps, never chosen by looking at results**
- GPS: doppler_spoof, meaconing (WP1 S8: combiner fitted without them), in K and C vehicle blocks.
- CAN: the masquerade families (WP2 S3): test has correlated_signal / max_speedometer / max_engine_coolant_temp / reverse_light_off /
  reverse_light_on "_masquerade" (5). Their non-masquerade siblings are "seen" families (no layer trained on either; the split is the WP2 one).
- Network (D10 host view): PortScan, Web-BruteForce, Web-XSS (WP4 S1 LOAO priority list: PortScan, WebAttack group; Bot is not in the host view;
  Bot LOAO = 0% from M1-NET is cited, not re-run). Honest caveat: net.scan / net.bruteforce are rules named after these classes of behaviour.
- V2X (VeReMi): class 6 ConstSpeedOffset and 17 DataReplaySybil (WP5; class 12 is an artefact, absent from the pack, never claimed).
- LiDAR: no held-out type was ever fixed. The interim XGB (v2 baseline) saw PointDrop / IntensitySpoof / GhostCluster labels, so the zero-day
  stack uses the label-free L1 geometry union only; the three families are reported as "label-free layer rows", not as unseen types.
- Cross-domain families (can_*, lidar_*, gps_can): not held out; the S2b choice (inst |z| among a handful of options) used their validation
  detection. Reported as a separate "choice-seen" group, never as unseen.
**Layer tiers (fixed a priori from the design, not from scores)**
- (b) physics / rule, never saw labels: GPS L1/L2 (max_speed, long_accel, lat_accel, jerk, yaw_rate, vel_pos_consistency, dr_resid_10, lidar_*);
  CAN can.l1_spec_rules; network tcp_flags, scan, trw, bruteforce (+ dos_rate in the tier table only); V2X L1+L2 (beacon_rate, field_ranges,
  pos_speed, pos_heading, speed_change, implied_speed, heading_rate, accel_consistency, overlap); LiDAR l1_union; cross-domain edges.
- (a) normal-only models ("L3"), fit on normal data only: GPS ekf_nis, cusum_ekf, cusum_dr and the WP1 S7 L3 (MCD) column (tier table only);
  CAN l3c, l3d; network l3_service, l3_ae (stack O, fit on the benign warm-up); V2X kf_nis, kf_cusum_hi, track_birth (per-sender CV Kalman).
- Supervised (saw labels): LiDAR v2_baseline_interim XGB -> excluded from the zero-day stack. Nothing else in the stack is supervised.
**What "removing the unseen types from everything that saw labels" means here**: the physics / L3 layers and their ECDF calibrations are label-free;
V2X was refit by WP5 / WP6 S3 without 6/12/17. What used labels in S3 and is redone here WITHOUT held-out families: the combiner choice (max vs
noisy_or), the network-variant choice, the novelty-detector choice; the 2% system threshold is label-free (clean composites). Domain owners'
frozen layer SELECTIONS (e.g. which rules are in stack H) used validation detection of the families visible to them; this cannot be undone here and is stated.
**Evidence-novelty layer**: per domain, features = the domain's calibrated per-layer tick scores (probit of the clipped score, zero-evidence ticks = 0),
detector fit on CLEAN validation half A ticks only; candidates (fixed now): robust Mahalanobis (sklearn MinCovDet, support 0.75, ridge 0.1 of mean
variance) and IsolationForest(200 trees, max_samples 256); the raw score is ECDF-calibrated on out-of-fold (5 contiguous-block folds) half-A clean ticks;
it enters the system as ONE extra noisy_or / max entry per domain (gps, can, network, v2x, cross; not LiDAR: one label-free layer). No system-level
novelty over the domain-score vector: composites mix independent segments, so cross-domain correlations of the clean vector do not exist.
**System configs chosen on validation half B using SEEN families only** (K + C pooled mean detection at the 2% tie-safe threshold of half-B clean
composites; held-out families and nothing else excluded): combiner {max, noisy_or} x network {H, H+L3(service, ae)} x novelty {none, mcd, iforest} = 12;
tie-break: simpler first (max, H, none). Composites: S3 construction; val seeds [SEED, 64, 1|2, ord], 400 clean + 60 per family; test seeds
[SEED, 64, 9, ord], 2000 / 1000 clean + 300 per family (K / C).
**Tier table (tick level, per domain)**: group score = max of the group's calibrated layers; threshold = tie-safe 1% of CLEAN validation half-B ticks;
test: tick detection of held-out families (TPR over attack ticks), AUC vs clean test ticks, FA on clean test ticks. Rows: (b) rules, (a) L3, union, novelty,
frozen domain score. Seen families alongside.
**Acceptance (test, judged once; the zero-day system and its tier table are scored on test ONCE, labelled)**
- Z1 K mean detection of the held-out families at the val 2% threshold >= 60%; C likewise (held-out in C: gps families, CAN, network, V2X).
- Z2 clean test composite tick FA <= 3.0% (the S3 G1 bound, K and C) and not more than 1.0 point above S3's 6.36% / 6.31%.
- Z3 zero-day gap: K mean detection of held-out families >= mean detection of the other label-free single-domain families (seen, lidar and
  choice-seen excluded: only domain families, same composites) minus 15 points.
- Z4 physics statement: in >= 3 of the 4 domains with both groups (gps, can, network, v2x), the (b) physics / rule group detects held-out types (tick
  level, 1% group threshold) at least as often as the (a) L3 group.
- Z5 novelty layer is kept only if on test it adds >= +3 points to the K held-out mean detection AND raises clean-tick FA by <= 0.5 points over the
  same system without it (matched config). Otherwise reported as "not useful".
- Z6 choices audited: no held-out family in any selection (assert in code, logged). Z7 unit tests pass.
Reported, not judged: C numbers, per-family detection and delay, equal-FA diagnostic (threshold at 2% of TEST clean composite ticks: test-informed,
labelled), cross-only / lidar rows, v2 side-by-side (v2: OCSVM on detector outputs, FA 2.92%, unseen Bot 5.27%, WebAttack 96.27%, Ghost 2.87%).
Exposure: every domain test set was scored before; the zero-day system, the tier table and the novelty layer are scored on test once here.

## 2026-10-24 S4 validation (before the test run; results/WP6/s4_dev.json, s4_frozen.pkl, logs/s4_dev.log)
- Extra material: tools/WP6_S4_streams.py (network pack with stack O layers: first four columns identical to the S3 pack, max diff 0.0; WP1 S7 L3 column aligned to
  the S3 GPS series, coverage 100% of non-gps_can ticks). fusion/novelty.py (+ 5 tests), tools/WP6_S4_lib.py (+ 4 tests in tests/fusion/test_zeroday.py).
- Halves (group counts A/B): gps 1/2 drives, can 9/10, network 15/15, v2x 4/5, cross_kitti 1/2, cross_comma 8/8. GPS / cross novelty is fitted on ONE drive (241 clean ticks).
- Grid on val half B, non-held-out families only, pooled K + C mean detection: noisy_or beats max everywhere (0.67-0.80 vs 0.07-0.68). Reason for the very low
  max rows: with max the 2% threshold lands in tie blocks of replicated outlier ticks (the clean pools are small and are re-sampled by the composites, network
  minutes are held 60 ticks); noisy_or is smooth. Novelty rows: noisy_or/H none 74.6, mcd 79.8, iforest 78.1; noisy_or/H+L3 none 67.3, mcd 78.2, iforest 76.4.
  H+L3 is worse than H (the two normal-only network layers add clean alarms faster than detection on seen families).
- CHOSEN (rule: highest pooled seen detection): noisy_or, network H, novelty mcd. Frozen with 28 variants (grid + matched ablations + rules-only / L3-only systems).
  Audit: the dev script asserts that no held-out family is in the selection set; held-out validation numbers are not stored.
- Smoke run of the test tool on the VALIDATION packs (plumbing, temp folder; it prints held-out numbers on validation): nothing changed after it.
  Performance fix before the real run: vectorised cluster bootstrap (fast_ci, same quantity as S3's cluster_ci).

## 2026-10-24 S4 TEST run (once) and verdict (s4_test.json, s4_acceptance.json, s4_tables.md; report reports/WP6_S4.md)
- Headline (noisy_or, network H, novelty mcd): K held-out 61.1% [48.6, 71.3], seen 84.8%, FA tick 2.73% [1.9, 3.8], 60 events/h; C held-out 86.2%, seen 97.3%, FA 4.78%, 87 events/h.
- Z1 MET (K, C). Z2 K MET / C NOT MET (4.78%, within S3 + 1). Z3 NOT MET (gap 23.7 pts). Z4 NOT MET (rules >= L3 only in network and V2X-AUC tie; CAN rules 0% on masquerade,
  GPS L3/EKF 72 vs rules 39). Z5 NOT MET (novelty: K held-out -8.0 pts, FA -0.85, seen +4.7; equal FA: held-out -2.1, seen +12.8). Z6 MET. Z7 MET (386 tests).
- System K held-out rules-only 36.9, L3-only 56.6, both no-novelty 69.1. FA improvement over S3 is mostly the removal of the supervised LiDAR XGB (7.7% own FA).
- v2 reference: WebAttack 96.3% (v2) vs 42.7 / 15.3% (v3 composites); Bot 0% (M1-NET); GhostCluster is a v2-comparison row (L1 tick 100% at 9.7% FA).
- Open: gated novelty (only above its own threshold) instead of an extra noisy_or entry; GPS EKF / S7 L3 into the system; LiDAR real zero-day layers (WP3 S9).
