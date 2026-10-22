# WP6 S2: "Which domain lies": pairwise consistency, CUSUM, blame logic

Date: 2026-10-22    Worker: opus (WP6, T4)

## Summary (verdict first)
- **Verdict: NOT MET** (AC2 FA on both data sets, AC4 blame on KITTI, AC5 gain over the GPS domain). What works: the comma blame
  logic, and the coordinated GPS+CAN attack is caught where the frozen GPS domain misses it. All numbers: `results/WP6/s2_test.json`
  (run 2), `s2_test_run1.json` (run 1), verdicts `s2_acceptance.json` / `s2_acceptance_run1.json`, tables `s2_tables.md` / `s2_tables_run1.md`.
- **Test exposure: TWO runs.** Run 1 was the pre-registered verdict. Afterwards I found a bug: the comma setup classification counted the
  duplicated gyro timestamps of the old routes (10 Hz read as 20.0-20.1 Hz). So the binding per-setup calibration was NOT done in run 1.
  Fixed, dev re-run on val, comma test re-run once, labelled "SECOND EXPOSURE". KITTI is unaffected (identical numbers).
- Layer: 7 edges on KITTI (gps / lidar / simulated can / gyro / compass), 6 on comma (gnss / can message / wheel message / imu). Train-fitted
  z (design R, per setup on comma), then two-sided CUSUM per edge, then per-edge ECDF on clean val, then one tie-safe 1% threshold on the max.
  Blame = the witness that is the unique minimum vertex cover of the alarming edges, has >= 2 alarming partners, and whose partners
  agree on an observed edge. Otherwise the output is "undecided". Evidence(domain "cross", name "cross.which_domain_lies").
- AC1 sigma not too narrow on val: **NOT MET**. KITTI lidar-can mean -0.33 (as in S1). comma with the real per-setup models (run 2):
  gnss-can / gnss-wheel speed mean -0.32. With per-setup sigmas the noise is ~0.08 m/s, so a 0.1-0.2% route-to-route CAN scale
  difference already shows as a bias. Run 1 (pooled by the bug) passed, but only because its sigmas were inflated by the old routes.
- AC2 FA on clean test rows (1.5%): **NOT MET**. KITTI 4.42% [1.5, 8.0] (drive 0039: 9.8%; gyro-lidar yaw edge alone 2.4%).
  comma 9.90% (run 1) / 5.36% (run 2). In run 2 the speed edges have 0.0% and the gnss-imu yaw edge has 4.7%.
  **Continuous CUSUM over whole comma test routes: 35.7%, 85% on route 12-07-08.** Cause: the k = 0.25 CUSUM integrates a slow
  gyro bias drift (S1 already saw test yaw mean -0.47). Val calibration (19 windows) cannot see this. Instantaneous |z|: comma test FA 2.3%.
- AC3 mean run-level detection (>= 70%): nominally MET (KITTI 74.4%, comma 100%), **but at the over-budget FA above**: not a valid claim.
- AC4 blame (correct >= 80%, wrong <= 5% of detected single-domain runs): comma **MET** (run 2: 96.9% correct, 0.0% wrong, 3.1% undecided).
  KITTI **NOT MET**: 48.9% correct, 6.1% wrong, 44.9% undecided. KITTI chose k = "inst" on val (81.1% vs 80.0% selection detection, the
  pre-registered criterion). On val, k = 0.5 had 77% correct blame vs 56% for inst. Short KITTI drives (5-90 s) leave little time for
  three-way agreement. lidar_yaw is mostly undecided (70%); doppler_spoof has 20% wrong blame (IMU / LiDAR).
- AC5 vs the frozen GPS domain (KITTI test, same 70 runs per attack): Doppler + meaconing pooled: GPS domain 65.0%, union 70.7% (+5.7 points,
  rule +10): **NOT MET**; union FA 5.8% vs 1.8%. Cross alone: Doppler 62.9% (GPS domain 68.6%), meaconing 64.3% (61.4%). The GPS domain
  already contains the LiDAR / odometry witnesses (L2d, B2), so cross adds little on GPS-only attacks.
- **Coordinated gps_can (KITTI): GPS domain 50.0%, cross 81.4%.** Cross catches 22 of the 35 runs the GPS domain misses: the spoofed wheel
  odometry fools the GPS domain, but LiDAR still disagrees.
- AC6 coordinated attacks: the predicted break is confirmed. **Two agreeing liars make the honest witness look guilty.** KITTI gps_can: LiDAR blamed in
  30 of 57 detected runs (26 undecided, 1 gps). comma gnss_can: the honest wheel message blamed (domain "can") in 31/32. comma can_bus (both CAN speed
  messages scaled; one domain, two messages on one bus): GNSS blamed in 32/32. Majority logic cannot handle collusion, and two messages on one bus
  are not independent witnesses.
- CAN domain comparison: not possible. The frozen CanDomain is ROAD-vehicle specific and the simulated KITTI bus has one ID. M1-CAN says a
  consistent rewrite of all speed signals is invisible to it by construction; our can_* attacks are that case and cross detects 76-90% (KITTI) at 4.4% FA.
- Delays (test, median): KITTI 0-4 s; comma 0.9-7.9 s (accel_drift slowest).
- Tests: 6 new (`tests/crossdomain/test_consistency.py`); full suite 325 passed, 0 failed.

## Goal of the step
Pairwise consistency between the motion witnesses, sequential tests, and "which domain lies" logic. Evaluated with single-domain attacks
injected on clean witness streams (GPS spoof, LiDAR odometry corruption, CAN speed spoof) and one coordinated two-domain attack. Compared with the domain detectors.

## Acceptance rule (notes/WP6_crossdomain.md, "S2 start", 2026-10-22, written before any S2 result)
AC1 val honesty, not too narrow: |mean z| <= 0.25, std <= 1.25, p99 |z| <= 4 (std < 0.8 allowed). AC2 test FA rows <= 1.5% per data set.
AC3 mean run-level detection over single-domain attacks >= 70% per data set. AC4 correct blame >= 80%, wrong <= 5% of detected runs.
AC5 KITTI Doppler + meaconing: union with the GPS domain >= GPS domain + 10 points. AC6 coordinated: predicted wrong blame (LiDAR / wheel / GNSS).
AC7 tests + Evidence. Choices on val only: comma setup definition (A gyro class, B gyro x GNSS class with fallback), CUSUM k in {0.25, 0.5, 1, inst}
(selection attacks: drift, accel_drift, lidar_scale, lidar_bias, can_scale, can_offset; held out: doppler_spoof, meaconing, lidar_yaw, can_freeze, coordinated).

## What was done
- Code: `crossdomain/consistency.py` (Edge, CUSUM, Calibration, minimum vertex cover blame, WhichDomainLies layer, Evidence, run outcome),
  `crossdomain/attacks.py` (GNSS attacks with the WP1 equations on a time axis, LiDAR odometry / CAN speed attacks, along-track coordinated).
- Tools: `tools/WP6_S2_kitti.py` (build), `WP6_S2_comma.py` (build), `WP6_S2_gpsdomain.py` (frozen GPS domain on the same runs; reproduces M1-GPS
  test FA 1.83%), `WP6_S2_eval.py` (dev / test), `WP6_S2_tables.py`.
- Data: KITTI val (3) + test (7) drives x 10 phases: WP1 GPS attack runs + injected attacks (70 test runs per attack). comma2k19 val (4) / test (4)
  routes in 120 s windows, 2 draws per window and attack (32 test runs per attack, 16 clean test windows). Cache 95 MB.
- Tests: `tests/crossdomain/test_consistency.py` (6). Full suite 325 passed, 0 failed (`results/WP6/logs/s2_tests.log`).

## Results
Tables: `results/WP6/s2_tables.md` (run 2; KITTI identical to run 1), `s2_tables_run1.md`. Sections: honesty per edge and setup, k on val, test per
attack (detection, delay, blame), instantaneous ablation, GPS-domain comparison, continuous comma FA.
Ablation (test): KITTI inst = chosen. comma inst: FA 2.29%, mean detection 97.3%, correct blame 97.7%. Edge-level FA in the tables.
Each edge alone was not evaluated as a detector; the edge-level FA is reported.

## Problems, surprises, open questions
1. **The CUSUM needs a bias-tolerant design.** Real sensors drift (gyro bias, small route-to-route CAN scale). A low-k CUSUM turns a 0.3-0.5 sigma bias
   into a permanent alarm. Proposal for a revised design (val only, or S3): an online bias tracker per edge (slow EWMA of r subtracted before the
   CUSUM, time constant >> attack ramp), or a leave-one-route/drive-out calibration of tau and k (like WP1 LODO / WP2 LOCO) instead of 3-4 val groups.
2. Second test exposure (bug fix) on comma; labelled. Do you accept run 2 as the comma numbers of record, with run 1 kept?
3. KITTI blame is limited by short drives and by k = inst. Changing k after the test would be a test-driven choice, so I did not change it.
4. Coordinated attacks: blame by majority is wrong by construction when two witnesses collude. Detection (81%) still works. S3 fusion should report
   "inconsistent" without naming a culprit when the blamed witness is an exteroceptive one (LiDAR) and the claims agree? (Design question.)
5. comma can + wheel share one bus: treat them as ONE domain in the blame graph (then comma speed has only 2 domains, so always undecided), or keep the
   per-message graph with the documented can_bus failure? I kept per-message.

## Proposed next step
S3 fusion over 5 domains + this cross-domain Evidence. Before S3, a small S2b (validation only) for the bias-tolerant CUSUM and LODO/LORO calibration,
if the supervisor agrees.
