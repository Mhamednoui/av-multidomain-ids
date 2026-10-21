# WP1 GPS notes

## 2026-10-19 S0 (download D15 OSM)
Acceptance rule (written before any result):
- Extract covers the lat/lon bbox of all 23 KITTI 2011_09_26 drives (OXTS) + ~1 km margin:
  100% of OXTS fixes of every drive fall inside the extract bbox (and inside bbox minus 500 m).
- File loads with python -I; contains > 0 highway ways and their nodes; every drive has road
  ways within 50 m of >= 95% of its fixes (sanity: map is the right place).
- Size < 100 MB; >= 15 GB disk free after download; licence ODbL recorded with attribution.
Done (tools/WP1_osm_bbox.py -> results/WP1/osm_bbox.json; tools/WP1_osm_verify.py -> results/WP1/osm_verify.json):
- 23 KITTI drives, OXTS bbox lat 48.94231..49.06758, lon 8.33725..8.47829; +1 km margin
  lat 48.93333..49.07656, lon 8.32356..8.49199.
- Overpass query (all highway=* ways + nodes) -> ../data_extra/D15_osm/karlsruhe_highways.json,
  36,924,973 bytes (35.2 MB), 57,018 ways, 193,170 nodes, OSM timestamp 2026-10-19T21:54:50Z.
  Contains footways/paths/service etc. (map matching in S6 should filter to drivable classes).
- All 23 drives: 100% of fixes inside bbox+margin; 100% of fixes (min over drives) within 50 m of a road.
- Disk free after: 52 GB. Licence ODbL 1.0, attribution (c) OpenStreetMap contributors.
- Untrusted data read with python -I, JSON only; nothing executed.
Acceptance: MET (all criteria above).

## 2026-10-19 S1 (data layer: unified stream + attack generator)
Acceptance rule (written before any result):
1. Unit tests in tests/gps/ pass, and `python tests/run_tests.py` passes (whole suite).
2. B2 (dead-reckoning rule) run on the NEW stream (v2 attacks only, same rng order, same split)
   reproduces the WP0 S3 numbers exactly: rows test/train/val 7910/23859/2850, runs 350/1080/150;
   false alarms on clean test runs 0.015803; row and run-level detection per attack identical to
   1e-4; tp/fp/fn/tn 1770/67/1151/4922; raw-equivalent threshold 6.658872 (WP0 v3 definition).
   (v2's interpolated 6.657975 differs by 0.0009 m with no decision changed, see WP0_S3.md.)
3. Extended stream (v2 attacks unchanged + two new attacks per run structure) keeps the v2 runs
   bit-identical (same lat/lon/odo speed as the v2-only build).
4. Doppler-consistent spoof: exact discrete identity (offset step/dt = mean of the velocity
   offset of the two fixes) and, on the built KITTI stream, the median |reported velocity -
   central difference of reported track| on spoofed rows <= 1.5 x the same median on clean
   rows (naive drift of v2 must be clearly larger: >= 2 x).
5. Meaconing: reported track equals the true track at t - tau(t) (exact on synthetic truth),
   reported velocity = V(t - tau)(1 - dtau/dt) = derivative of the reported track (synthetic
   circular truth, error < 1% of speed), reported acceleration never exceeds the clean maximum
   by more than the ramp's contribution (tau' <= 0.25), clock offset column = -tau.
6. Severity ranges explicit in module constants and in the report.
7. Splits by group (drive / session / flight), stored in results/WP1/splits.json; no group in two parts.
Amendment (still before any result): meaconing delay growth tau' rises linearly 0 -> 0.2 s/s over 2 s
(smooth onset, no acceleration impulse); criterion 5 becomes: reported speed change per second on attacked
rows <= max(99.9th percentile on clean test rows, 3 m/s^2); velocity = derivative of reported track on
synthetic circular truth within 2% of speed.
Amendment 2 (before any result; unit tests only so far): the delay profile is a smoothstep tau = tau_max(3u^2 - 2u^3),
u = min(tr/T,1), T = 1.5 tau_max / 0.2 (tau' zero at both ends, peak 0.2 s/s) because the capped linear ramp
left a step in the apparent speed when the cap was reached (caught by the unit test). Criteria 5 unchanged otherwise.
Done (S1): gps/stream.py, tools/WP1_S1_b2.py, tests/gps/test_stream.py (10 tests; suite 29 pass), results/WP1/S1_*.json, splits.json, reports/WP1_S1.md.
- B2 from the new stream = WP0 S3 exactly (every comparison OK, threshold 6.658872); extended stream keeps v2 runs identical.
- Extended test (B2 calibrated train+val): run-level detected doppler_spoof 0.414, meaconing 0.471; val-only calibration: AUC 0.847, FA 0.70%.
- Physics: median |v_rep - track derivative| ratio to clean: doppler 1.03, meaconing 1.03, drift 2.53, accel_drift 3.95, freeze 19.4.
- Pitfalls: capped linear delay ramp left a speed step (test caught it); AV-GPS time = row counter; UAV onset 117 s approximate.
Acceptance: MET. S1 -> REVIEW.

## 2026-10-19 S2 (L1 receiver sanity rules)
Acceptance rule (written before any S2 result was computed; I had only looked at column names / value ranges
of the UAV and AV-GPS receiver fields and at the AV-GPS step sizes, no rule has been scored yet):
Coverage (stated before results, from the data layer): KITTI has no receiver fields (fix_type / hdop are constants
written by the simulator, numsats is the real OXTS count but the attack simulator never touches it, clock_offset is
produced by our own meaconing generator) -> on KITTI ONLY the kinematic rules and the receiver self-consistency rule
(Doppler vs position) are evaluated. Fix-type, satellite, DOP, noise/jamming-indicator, clock rules are not evaluated
on KITTI (no invented fields). AV-GPS (1 Hz confirmed: median step / odometry speed ~ 1): kinematic rules from
position only (no Doppler, no IMU accel); hdop = 100 and numsats = 0 mark the no-fix placeholder of the spoofed
sessions (artefact), so receiver-field rules there are reported as artefact only, never as detection. UAV: fix type,
satellites, HDOP, noise_per_ms, jamming_indicator (the PX4 stand-in for AGC; AGC itself is absent), Doppler vs position.
Clock rule: time_utc_usec is 0 in the spoofing and jamming flights, so the clock rule is implemented and unit-tested but
evaluated nowhere.
A1 unit tests tests/gps/test_l1.py pass; whole suite passes.
A2 Physical limits (max speed, longitudinal / lateral acceleration, jerk, minimum turn radius, min satellites, HDOP,
clock rate) are constants in gps/l1.py with a written source each, fixed before any run and not changed afterwards.
A3 At the physical operating point (alarm iff the quantity exceeds its limit; no fitted threshold) the UNION of the
kinematic rules has false alarms <= 1.0% on KITTI clean test runs, and each rule alone <= 1.0%. Detection is NOT a pass
criterion: a rule that detects little and never false-alarms is kept.
A4 Data-driven thresholds (Doppler-vs-position consistency; satellite / HDOP / noise / jamming-indicator jumps) are set
on validation normal rows only (KITTI val drives; UAV: the benign flight, see decision below), 1% budget, tie-safe,
test scored once.
A5 AV-GPS: false alarms of the kinematic physical union <= 1.0% of test normal rows (report what fires, incl. glitches).
A6 UAV spoofing flight: at least one L1 rule alarms within 2 s of the first spoofed fix (118.0 s); L1 union false alarms
<= 2% on the spoofing flight before 117 s (out-of-sample), benign flight false alarms reported (in-sample for the
calibrated rules).
A7 Harness ablation on KITTI at the 1% budget: B2 alone vs L1 alone vs B2+L1 vs all-but-one. "L1 adds" is judged
only as: the B2+L1 combination does not lose more than 1 point of AUC against B2 alone and the test false alarms stay <= 1.5%;
which attacks it adds detection for is reported, including "nothing".
Decision (documented, flagged to the supervisor): all UAV flights are test in splits.json (case study). The receiver-jump
rules need normal data from that receiver and no other data exists, so the BENIGN flight is used as their calibration
set and is excluded from their out-of-sample claims; their false alarms are then measured on the pre-onset part of the
spoofing flight (117 fixes). The jamming flight has no onset label and stays unlabeled (alarm timeline only).
Done (S2): gps/l1.py, tests/gps/test_l1.py (12 tests, suite 41 pass), tools/WP1_S2_l1.py, tools/WP1_S2_tables.py, results/WP1/S2_*.{json,md}, reports/WP1_S2.md.
- KITTI physical kinematic rules: 0.00% FA on clean test runs (each and union); detect jump 86% of runs, freeze 14%, everything else 0% (they never fire on drift, Doppler spoof, meaconing). Margins: yaw 0.77-0.87 of limit, others < 0.33.
- Doppler-vs-position (val 1% budget): FA 1.26% clean test runs; run-level drift 70%, accel_drift 56%, freeze 84%, jump 100%, Doppler spoof 16%, meaconing 17%.
- Harness: B2 alone AUC 0.847 FA 0.70%; B2+all L1 AUC 0.860 FA 1.39%; B2+kinematic 0.855 / 0.99%; without B2 0.709.
- AV-GPS kinematic union FA 0.61%, detection 13.7% (placeholder coordinates); sat/HDOP rules = artefact.
- UAV spoofing: sat_jump, hdop_jump, noise_jump, vel_pos fire at 118.0 s; union FA before 117 s 2.54% (3/118) -> A6 FA part NOT MET (not retuned); benign flight used as calibration set (decision flagged).
Acceptance: A1-A5, A7 MET; A6 detection MET, A6 FA NOT MET. S2 -> REVIEW.

## 2026-10-19 S3 (L2a error-state/standard EKF, NIS chi-square per fix)
Acceptance rule (written before any S3 result; nothing of S3 computed yet):
Model: state [e, n, ve, vn, we, wn] (position, velocity, Gauss-Markov receiver error). Process driven by IMU acceleration;
measurements per fix: GPS position (pos + w + white), GPS Doppler velocity, odometry speed, compass heading. Layer score =
-log chi2-survival of the per-fix NIS (dimension varies with active measurements). Noise: physical/sensor specs, plus ONE
process-noise scale q_scale and the Gauss-Markov (phi, sigma) tuned on KITTI TRAIN clean runs only (UAV: on the benign flight;
AV-GPS: train sessions). Two variants: ungated, and gated (once NIS exceeds a chi2 level the GPS block is excluded from the update,
dead-reckoning prediction held; release after n consecutive consistent fixes). Gate level chosen on VAL (grid 0.99/0.999/0.9999).
A1 unit tests pass, suite passes.
A2 Consistency on clean KITTI VAL runs (ungated, params tuned on TRAIN only): mean NIS / mean dim in [0.8, 1.25] and fraction
above chi2 95% in [2%, 10%]. Reported as met/not met, no retuning on val.
A3 False alarms on KITTI clean TEST runs at the val 1% tie-safe budget <= 1.5% (both variants).
A4 Beat-or-not vs B2 (same protocol: B2 calibrated on val 1%): per attack, L2a "beats" B2 iff run-level detection is >= 5 points
higher with clean-run FA not more than 0.5 point above B2's; within 5 points = "no difference"; lower = "worse". Stated plainly per attack.
Target: drift 0.2-0.5 m/s detected within 30 s in >= 60% of runs at <= 1% FA (KITTI test).
A5 Absorption: for every attack, position-estimate error vs truth (and ratio to the reported-position error) 30 s after onset,
ungated vs gated; gated "helps" iff it lowers the absorption and does not raise val-calibrated FA.
A6 Primary variant chosen on VAL: the one with higher mean run-level detection over the 6 attacks at the val 1% budget.
A7 AV-GPS (position, speed, heading only; no Doppler, no IMU accel): FA on test normal rows <= 2%; detection reported incl. artefact caveat.
A8 UAV spoofing flight: noise and threshold from the benign flight; alarm within 5 s of 118.0 s and FA before 117 s <= 2%.
A9 Harness: "L2a adds on top of B2 + L1" iff AUC(all) - AUC(all-but-L2a) >= 0.01, or some attack row-level detection +5 points, with
combined FA <= 1.5%. Otherwise "adds nothing".
Deviation (before any test number): AV-GPS tuning criterion switched from mean NIS/dim to fraction above chi2 95% closest to 5% (train sessions; glitches dominate the mean). Parse bug in the tuning script fixed and re-run (train/val only).
Done (S3): gps/ekf.py, tests/gps/test_ekf.py (6 tests; suite 72 pass), tools/WP1_S3_{tune,ekf,isofa,tables}.py, results/WP1/S3_*.{json,md}, reports/WP1_S3.md.
- Tuning (train): GM phi 0.897 sigma 0.981 m, q_acc 0.1; gate level 0.99; primary = ungated (val 0.833 vs 0.828).
- Consistency: val clean ratio 0.85, 5.4% above chi2 95% (A2 MET); test clean 1.12 / 10.6%.
- KITTI test at val 1% budget: EKF clean-run FA 2.59% (gated 6.32%) vs B2 0.38% -> A3 NOT MET. Run-level: drift 54%, accel 56%, jump 100%, freeze 81%, Doppler 97%, meaconing 79% (B2 34/41/100/89/39/40).
- Equal-FA diagnostic (oracle, not an operating point): EKF beats B2 on Doppler spoof 87 vs 40% and meaconing 71 vs 46%; same on drift/accel/jump; worse on freeze 79 vs 89. Slow drift <0.5 m/s within 30 s: 14% (B2 14% at equal FA, 7% at its val point): target 60% NOT MET.
- Absorption at +30 s: ungated 99% (Doppler spoof), 97% (meaconing), 43% drift; gated 5-18%.
- Harness: all AUC 0.896 FA 1.90% vs all-but-L2a 0.860 / 1.39%: A9 NOT MET on FA (> 1.5%).
- AV-GPS FA 3.97% (A7 NOT MET), AUC 0.30. UAV: alarm at 118.000 s, FA before 117 s 0.85% (A8 MET).
Acceptance: A1, A2, A6, A8 MET; A3, A4 (as written), A7, A9 (FA clause), slow-drift target NOT MET. S3 -> REVIEW.

## 2026-10-19 S4 (L2b CUSUM / SPRT on innovations, L2c online odometry-scale calibration; new LODO calibration policy)
Acceptance rule (written before any S4 result; nothing of S4 computed yet; only gps/ekf.py got extra output columns nu_x, nu_y, s_x, s_y, behaviour unchanged).
Policy (supervisor, binding): thresholds by leave-one-drive-out (LODO) over the 16 train+val KITTI drives: pooled clean (label 0) scores -> tie-safe 1% budget threshold;
anything tuned on data is tuned on the 16 drives only (small pre-registered grid) or frozen beforehand; test drives untouched until the single final pass. Every table gives
val-only calibration (3 val drives, as S2/S3) and LODO calibration (16 drives) side by side, for the new layers and also for B2 and L2a (so we see if LODO fixes the FA transfer).
LODO helper (generic) lives in gps/lodo.py (own code; proposed for common/ in the report). The score functions have no fitted parameters apart from frozen ones, so the
"out-of-fold" scores equal the plain scores; LODO therefore also reports, per held-out drive, the FA at the threshold computed from the other 15 drives (honest transfer estimate).
Layers: SPRT note: Page's CUSUM with allowance kappa = delta/2 IS Wald's SPRT restarted at 0 for a Gaussian mean shift delta (in sigma units), so CUSUM covers SPRT; kappa grid.
 - gps.cusum_nis: CUSUM on the standardised EKF (S3 ungated) NIS excess (NIS - m)/sqrt(2m).
 - gps.cusum_axis: bank of 8 directional one-sided CUSUMs (0,45,90,135 deg and opposites) on the standardised EKF position innovation (nu/sqrt(S)); score = max over the bank.
 - gps.cusum_dr_axis / gps.cusum_dr_nis: same two statistics on the innovation of a DEAD-RECKONING BRANCH (odometry + compass heading only; no Doppler, no IMU) whose state is [position, receiver error (Gauss-Markov), odometry scale s] and that does not take GPS updates while suspicious (frozen).
 - L2c = the scale state s of that branch: prior N(1, 0.02^2), learned only through GPS position updates, which are skipped while frozen (frozen when its own freeze-CUSUM >= h_f, or the ungated EKF NIS is above chi2_m(0.999), the other layer).
Frozen beforehand (not tuned): receiver GM phi 0.897 sigma 0.981 m, r_pos 0.3, heading 2 deg, odo 0.05 m/s, scale prior 2%, scale random-walk 2e-4/fix, EKF q_acc 0.1 (all S3 values from TRAIN), freeze-CUSUM allowance 0.5.
Grid (16 drives, LODO pooled threshold): kappa in {0.25, 0.5, 1.0}; freeze in {never, self h_f=4, self h_f=4 + EKF NIS}; scale in {learn, none (2% as noise)}. Selection criterion J = mean of 7 numbers
(run-level detection of drift, accel_drift, jump, freeze, doppler_spoof, meaconing, and slow drift <0.5 m/s within 30 s) at the LODO 1% threshold on the 16 drives. Choice is not nested per fold (disclosed).
Test = ONE pass, KITTI test drives, thresholds from LODO (primary) and val-only (side by side).
B1 unit tests pass.
B2 L2c convergence on clean data: median |s_hat - s*|/s* (s* = sum odo / sum true distance of the run) at 30 s <= 0.7% and at 60 s <= 0.5% (runs long enough), better than the 2% prior.
B3 L2c freeze protection: over drift, accel_drift, doppler_spoof, meaconing (test attack runs): median |s_hat - s*| at onset+30 s with freezing <= 0.5 x without freezing, and <= 1.0%.
B4 LODO vs val-only: the new layers' clean-run FA on test with LODO calibration <= 1.5% (policy goal); also report |LODO-estimated FA - actual test FA|.
B5 slow drift (0.2-0.5 m/s): detected within 30 s in >= 60% of test slow-drift runs at clean-run test FA <= 1.5%. Met/not met stated plainly.
B6 beats B2 (both LODO-calibrated): per attack run-level detection >= 5 points higher AND clean-run FA <= B2 + 0.5 point.
B7 harness on top of B2 + L1 + L2a: "L2b/L2c adds" iff AUC +0.01 or some attack +5 points row-level, combined FA <= 1.5% (LODO primary, val-only side by side).
B8 absorption: the frozen DR branch's position-estimate error at +30 s as a fraction of the reported error <= 0.3 for doppler_spoof and meaconing (ungated EKF: 0.99 / 0.97).
B9 UAV (EKF-based CUSUM only; the drone has no odometry): alarm within 5 s of 118.0 s, FA before 117 s <= 2% (threshold from the benign flight, in-sample). AV-GPS not run (S3: placeholder attacks, not meaningful).
Edit before any real-data S4 result (made after a synthetic unit test showed that a false freeze at level 4 latches: while frozen the innovations are strongly autocorrelated and the CUSUM runs away): freeze levels in the grid are {never, self h_f=8, self h_f=8 + EKF NIS chi2(0.999)} instead of 4. Everything else as written above.
First dev pass (16 drives, S4_dev.json, before the final selection): best kappa at the grid edge 1.0 for the axis/NIS CUSUMs, so the kappa grid was extended to {0.25, 0.5, 1.0, 1.5, 2.0} (dev data only; disclosed). Scale diagnostics: runs with < 50 m odometry path (stationary) excluded (s* undefined; they made the prior RMS 125%); clean convergence is reported at 10/20/30/60 s where runs are long enough (KITTI drives are short: 0 clean runs reach 60 s in dev).
Done (S4, 2026-10-20): gps/cusum.py, gps/lodo.py, gps/ekf.py (extra output columns only), tests/gps/test_cusum.py (6 tests; suite 116 pass), tools/WP1_S4_{lib,dev,test,tables,report}.py, results/WP1/S4_*.{json,md}, reports/WP1_S4.md.
- Dev (16 train+val drives): EKF NIS with val-only threshold gives 3.10% FA on the 13 train drives, LODO 1.11%; worst held-out drive 19.5% for NIS vs 1.8-2.0% for CUSUMs. Selected (criterion J): DR branch NIS-CUSUM kappa 2.0, scale learned, freeze self8+EKF-NIS (J 0.699); EKF axis CUSUM kappa 1.5 (J 0.624). Kappa grid extended once (1.5, 2.0), plateau.
- Test (one pass; the dry run on val rows only found code bugs): clean-run FA LODO / val-only: B2 1.58 / 0.38, EKF NIS 0.44 / 2.59, cusum_ekf 2.53 / 2.65, cusum_dr 1.64 / 1.58 (%). LODO fixes EKF NIS, not cusum_ekf; B2 gets worse.
- Run-level (LODO): cusum_dr drift 70, accel 61, jump 100, freeze 84, Doppler 70, meaconing 61 (B2 39/43/100/89/41/49); cusum_ekf 80/67/100/84/23/29. Slow drift <0.5 m/s: cusum_ekf 43% (6/14), cusum_dr 14%, B2 14%: target NOT MET; no test slow-drift run has a full 30 s window.
- L2c: scale error 0.24% at 30 s (prior 1.33% median); without freezing the attacker drags it to 7-8% (87.6% under the freeze attack), with freezing it stays at the onset value. Absorption at +30 s: ungated EKF 0.99 / 0.97 (Doppler / meaconing), frozen DR 0.09 / 0.21.
- Harness (B2 + L1 + L2a base): LODO AUC 0.900 -> 0.922, FA 1.29 -> 1.14% (adds); val-only 0.896 -> 0.903, FA 1.90 -> 2.20% (does not add).
- UAV: alarm at 118.000 s, 0/118 false alarms before 117 s (all EKF-CUSUM variants).
Acceptance: B1, B2(30 s), B7(LODO), B8, B9 MET; B3 factor met / absolute bound not on 1 run; B4, B5 NOT MET. LODO helper proposed for common/ (not edited). S4 -> REVIEW.

## 2026-10-20 S5 (L2d LiDAR odometry: point-to-plane ICP; GPS displacement vs LiDAR displacement; MotionEstimate)
Acceptance rule (written before any S5 detection result; seen so far: a 40-scan smoke test of the ICP on drive 0002 to check it runs: median 1-step error 1.2 cm; nothing else).
Data facts: velodyne exists for ALL 23 drives (21 in ../data_extra/kitti_raw, 0001 and 0015 in ../codes/data/Depth; the "21 of 23" in the assignment counted only data_extra). No drive is without LiDAR. Cache of per-drive odometry: results/WP1/cache/ (gitignored).
Method (frozen before results, no tuned parameter): voxel 0.5 m, range 2.5-60 m, normals from 8 neighbours, 6-DOF point-to-plane Gauss-Newton, gates 2.0/1.0/0.7/0.5 m, trim 20%, constant-velocity initial guess. Planar (x, y, yaw) kept.
Layers: gps.lidar_resid_W (W = 1, 3, 10 s): |GPS displacement over the last W fixes - LiDAR displacement over the same interval| (metres), LiDAR rotated to east-north by the compass offset averaged over the window (compass = vehicle's own sensor). gps.lidar_course: lateral-metre equivalent of |change of GPS course - change of LiDAR direction| (compass-free; 0 below 2 m/s). Window shortened at run start (as B2). W chosen by criterion J (S4: mean of 6 run-level detections + slow-drift) at the LODO pooled 1% threshold, NESTED inside each LODO fold (choice on the 15 other drives; chosen W and held-out FA of the nested procedure reported); the W used on test = the choice on all 16 drives.
C1 unit tests pass, suite passes.
C2 Odometry vs OXTS ground truth on the 16 train+val drives (no parameter tuned; test drives reported too, separately): KITTI-style error over path segments of 10, 25, 50, 100 m (drives are short, <= 1.2 km): mean translation error <= 2.0% and rotation <= 0.02 deg/m; and median 1 s displacement error <= 0.10 m on windows with speed > 1 m/s.
C3 sigma model sqrt(sigma0^2 + (rel*speed)^2) fitted on the 16 drives (robust: MAD of the 1 s speed error vs OXTS in speed bins); coverage of |speed error| <= 2 sigma >= 90% on the test drives.
C4 Clean-run FA on test with LODO calibration <= 1.5% for the selected L2d layer, and nested-LODO held-out FA <= 1.5%. Val-only reported side by side.
C5 Run-level detection (LODO) of doppler_spoof and of meaconing >= 75% each (the attacks that fool velocity checks: S4 cusum_dr 70 / 61%, B2 41 / 49%). Per attack run / row detection and delay quantiles for all 6 attacks. Stated plainly met / not met per attack.
C6 Harness on top of B2 + L1 + L2a + L2b (S4 "all" stack): "L2d adds" iff AUC +0.01 or some attack +5 points row level, with combined FA <= 1.5% (LODO primary, val-only side by side). Also L2d alone, and each W.
C7 Slow drift (<0.5 m/s within 30 s) reported as untestable on KITTI test (no run has 30 s after onset), per supervisor decision S4.
C8 MotionEstimate published per second with sigma; format documented in the report and the module; tests cover it.
Pre-registered limitation to check: the LiDAR and the compass are the only non-GPS inputs, so an attacker who also spoofs LiDAR/compass is out of scope; an attack equal to the true motion is undetectable by construction.
Amendment to the S5 rule (made before any detection result; only dev-drive feature quantiles of the clean raw residual had been looked at: 99th percentile 1.2-3.9 m for W=1, up to 9 m for W=10, i.e. the noise grows with path): candidate layers = {raw metres, standardised z} x W in {1,3,10} + course. The standardised score lid_z_W divides the residual by its modelled std per axis (receiver AR(1) difference with the S3 phi 0.897 / sigma 0.981 m, LiDAR relative error 1.9% x path, compass 2 deg/sqrt(n) x path, floor 0.05 m): all constants frozen, none tuned on detection. Selection of (form, W) by J nested in LODO as written.
Odometry validation (tools/WP1_S5_odom_run.py then WP1_S5_odometry.py; results/WP1/S5_odometry.json; 23/23 drives, ICP ~0.12 s per scan pair, 4 workers ~7 min total): dev translation error 1.88%, rotation 0.0079 deg/m (C2 translation and rotation MET); median 1 s displacement error 0.130 m > 0.10 m (C2 third clause NOT MET); sigma model s0 0.083 m/s, rel 0.46% (fitted on dev); sigma coverage (2 sigma) dev 92.0%, test 88.6% (C3 NOT MET, narrowly). Test drives: translation 2.28%, rotation 0.0076 deg/m. Drives 0017, 0060 (stationary, path 0.1 m) have no segments.
Dev result of the instantaneous layers (tools/WP1_S5_dev.py, 16 drives; results/WP1/S5_dev.json): best lid_z_1 J 0.511 (S4 cusum_dr 0.699); run-level doppler 40%, meaconing 47%; nested choice lid_z_1 in 15/15 folds, held-out FA 1.03%. A single 1 s residual is noise-limited (receiver noise 0.45 m per axis after differencing) and does not accumulate: C5 (>= 75%) looks unreachable for it.
Amendment 2 (made after seeing those dev numbers, before any test number; disclosed): add a SEQUENTIAL L2d layer = the S4 dead-reckoning branch with the LiDAR displacement as odometry (gps/lidar_dr.py: state position + Gauss-Markov error, no scale state, freeze self CUSUM h=8 + ungated-EKF NIS 0.999, exactly the S4 constants) + CUSUM on its innovations (NIS statistic or 8-direction bank). Statistic x kappa in {0.5, 1.0, 1.5, 2.0}, selected by J nested in LODO like the others. Branch output does not depend on kappa, so the nested selection is exact. Primary L2d for C4-C6 = the better of {best instantaneous, sequential} by nested-LODO J on the 16 drives (not on test).
Deviation log (before any test number): (1) bug found in the dev diagnostics of the sequential layer: the first scan pair of every drive has no previous motion for the ICP start; at 14 m/s the identity start converged to a wrong minimum (first second displacement 6 m instead of 14 m, drive 0019). Fix: multi-start (forward 0-2 m) for the first pair only, odometry cache recomputed for all 23 drives (dev and test, no tuning, same code for all). Effect: dev J of lid_z_1 0.511 -> 0.687; odometry dev translation error 1.88% -> 1.73%, test 2.28% -> 1.58%. The first S5_odometry/S5_dev numbers above were from the buggy cache and are superseded (the JSON files are overwritten). (2) ALPHA_FIXES 5 -> 20 (compass offset averaged over more fixes) for lid_dE/lid_dN; dev only. (3) sigma constants 0.0832 -> 0.0821 after the re-run.
Dev (16 drives, fixed cache): lid_z_1 J 0.687 (run-level drift 73, accel 58, jump 100, freeze 80, Doppler 64, meaconing 59 %), lid_z_3 0.675, lid_resid_3 0.638, lid_course 0.295, sequential cusum_lidar (nis, k 2.0) 0.518 with held-out FA 1.9%: the CUSUM on the LiDAR branch is WORSE than the one-second residual (lidar-error runs latch the freeze; 0019 99th percentile 175). Nested selection: lid_z_1 chosen in 15/15 folds, held-out FA 1.01%. Primary L2d for C4-C6 = lid_z_1 (instantaneous beats sequential by nested J). Test pass launched with tools/WP1_S5_test.py (dry run on val rows passed first).
Test pass done (tools/WP1_S5_test.py, one pass; results/WP1/S5_kitti.json, S5_tables.md, S5_acceptance.json; report reports/WP1_S5.md). Numbers:
- Odometry (23/23 drives have velodyne; ~0.12 s per pair, cache results/WP1/cache): dev translation 1.73%, rotation 0.0078 deg/m, median 1 s displacement error 0.129 m; test 1.58% / 0.0069 / 0.135 m. Sigma model 0.0821 m/s + 0.46% of speed; 2-sigma coverage dev 92.6%, test 89.4%.
- Primary L2d gps.lidar_z_1 (nested choice 15/15 folds): test clean-run FA 1.64% LODO (1.33% val-only), nested dev held-out 1.01%; run-level LODO: drift 61, accel 59, jump 100, freeze 84, Doppler 60, meaconing 61 % (B2 39/43/100/89/41/49; cusum_dr 70/61/100/84/70/61). Beats B2 on drift/accel/Doppler/meaconing, does not beat cusum_dr. lid_z_3 Doppler 71%, FA 1.45%.
- gps.cusum_lidar: clean-run FA 10.1% LODO / 13.3% val-only on test (dev held-out estimate 1.92%): failure, latching freeze on ICP glitches. lid_course AUC 0.558.
- Harness (S4 stack AUC 0.922, FA 1.14% LODO): + primary AUC +0.00005 (adds nothing); + all L2d AUC 0.927, drift +7.1 pts row level, FA 1.23% (adds under LODO via +5 clause); val-only: no (FA 8.8%).
- Post-hoc severity diagnostic: Doppler spoofs with final offset < 1 m/s are seen in 28% of runs, >= 1 m/s in ~71%: the per-second test is limited by the simulated receiver noise (0.45 m per axis after differencing), not by the LiDAR (0.13 m).
Acceptance: C1, C2a, C2b, C8 MET; C2c, C3 (89.4% vs 90%), C4 (1.64% vs 1.5%), C5 (60/61% vs 75%) NOT MET; C6 primary adds nothing, family adds under LODO only; C7 untestable. S5 -> REVIEW.

## 2026-10-21 S6 (L2e map matching on the D15 OSM extract)
Acceptance rule (written before any S6 result; seen so far: only the OSM way/highway-tag counts of S0 (osm_verify.json) and the S5 notes; no map score computed yet).
Map: ../data_extra/D15_osm/karlsruhe_highways.json, FILTERED to drivable classes fixed now: motorway, trunk, primary, secondary, tertiary, unclassified, residential, service, living_street and their *_link variants. Excluded: footway, path, cycleway, steps, pedestrian, track, bridleway, corridor, proposed, construction, raceway etc. (a car cannot be on them; `service` kept because it contains the streets/driveways a car really uses, at the price of a denser map: a sensitivity run WITHOUT service is reported as a diagnostic on dev only, not selectable). One-way: oneway in {yes,1,true} or junction=roundabout (direction = node order), oneway=-1 (reversed); other ways two-way. Local frame: equirectangular around (48.99 N, 8.40 E), same for map and fixes.
Index: scipy cKDTree on points of every segment densified every 3 m; for the 8 nearest dense points the exact point-to-segment distance is computed, so no 1.5 m discretisation error.
Scores (all parameters frozen now): gps.map_dist = distance (m) from the REPORTED fix (noisy, attack-aware) to the nearest drivable segment. gps.map_heading = angular deviation (deg, 0..180) between the receiver course and the direction of the best-matching segment among those within d_min + 10 m of the fix (two-way: mod 180; one-way: mod 360 against the allowed direction); 0 when the odometry speed < 3 m/s (course undefined; odometry = vehicle's own sensor). gps.map_comb = max(dist / q_d, heading / q_h) with q = 95th percentile of each score on clean rows of the 16 train+val drives (scale only, no attack label used, disclosed). Primary = best of the 3 by J (S4 definition: mean of 6 run-level detections + slow drift) NESTED in LODO as in S5 (choice made on the other 15 drives, held-out FA reported); choice for test = best J on all 16 drives.
Calibration: LODO over the 16 drives, pooled clean scores, tie-safe 1% budget; val-only side by side. No fitted parameter, so out-of-fold scores = plain scores.
D1 unit tests pass, suite passes.
D2 Map sanity on the 16 dev drives (no attack): >= 95% of clean fixes within 10 m of a drivable segment, median distance <= 4 m; median heading deviation <= 10 deg (speed > 3 m/s). If not met the map is judged unsuitable and said so.
D3 Clean-run FA on test with LODO calibration <= 1.5% for the primary and nested held-out FA <= 1.5%.
D4 "L2e adds" on top of the S5 stack (B2 + L1 + L2a + L2b cusum_ekf + cusum_dr + L2d lid_z_1 primary): iff AUC +0.01 or some attack row-level detection +5 points with combined FA <= 1.5% (LODO primary, val-only side by side). Also: L2e alone, B2 + L2e, and on top of base + all L2d.
D5 Physics expectation (pre-registered, to be checked): map matching sees only spoofed tracks that leave the drivable network; spoofs that stay on a road (drift/accel drift along or parallel to a road within the clean distance band, Doppler/meaconing replays of a plausible track, freeze (stays on the last road)) are invisible by construction; jump may be seen when it lands off-network (in the dense town network many jumps land on another road). Quantified by the "spoofed track on-road fraction": fraction of attacked rows whose reported fix is within q_d99 of a drivable segment (clean 99th percentile of map_dist). Run-level detection (6 attacks), row-level, delay quantiles and clean-run FA reported. Slow drift: untestable on KITTI test (S4/S5 decision).
Not claimed: the check needs the map and does not protect against an attacker who keeps the fake track on roads (a route-aware spoofer, e.g. Zeng et al. 2018 "all your GPS are belong to us" style road-following spoof).
Done (S6, 2026-10-21): gps/map_match.py, tests/gps/test_map_match.py (6 tests; suite 154 pass), tools/WP1_S6_{dev,test,tables,diag}.py, results/WP1/S6_*.{json,md}, reports/WP1_S6.md, notes/WP1_brief.md.
- Dev (16 drives): D2 MET (100% within 10 m, median 1.71 m, p99 5.62 m, heading median 1.5 deg). Candidates J: map_dist 0.299, map_comb 0.241, map_heading 0.206; nested choice map_dist 14 / comb 1, held-out FA 2.63% (worst drive 0027 27.7%). Diagnostic maps (dev): no service J 0.301 (same), all highway classes J 0.255 (footways/paths hurt).
- Test (one pass, LODO): map_dist clean-run FA 4.11% (val-only 0.57%); run-level drift 33, accel 39, jump 87, freeze 9, Doppler 40, meaconing 11 %. AUC 0.652; map_comb 0.667 FA 0.63%; map_heading 0.586.
- Post-hoc diagnostic (S6_diag.json): FA at the LODO threshold comes from drives with a constant 4-5 m offset (test 0028 25.7%, 0001 7.3%; dev 0027 21.7%, 0017 3.0%); per-road OSM bias, not noise. Not retuned.
- Harness: on top of the S5 stack (AUC 0.922 FA 1.15%) + map_dist AUC 0.920 FA 1.27%, max row-level gain +1.9 pts: L2e adds nothing (LODO and val-only; also on base, base + all L2d, all 3 map layers).
- On-road fraction of attacked test rows (within 5.62 m of a drivable road): drift 77, accel 61, jump 40, freeze 82, Doppler 59, meaconing 92 %: a map cannot see on-road spoofs.
Acceptance: D1, D2, D5 MET; D3 NOT MET (4.11% vs 1.5%); D4 adds nothing. S6 -> REVIEW.
