# WP6 S2b: bias-tolerant sequential test, leave-one-group-out calibration, domain-level blame (VALIDATION ONLY)

Date: 2026-10-22    Worker: opus (WP6, T4)

## Summary (verdict first)
- **No test data was read.** Everything below uses the dev groups only: KITTI 15 drives with runs (train + val), comma 17 routes (train + val).
  Out-of-fold sigma models, leave-one-group-out thresholds, numbers pooled over the held-out folds. The test number comes once, in S3.
- **Verdict: PARTIAL.** B1 MET (FA). B2 NOT MET (one comma route). B3 MET on comma only. B4 MET (wrong blame). The chosen statistic is
  **instantaneous |z| for both data sets**, not a CUSUM: none of the 11 sequential candidates kept the held-out FA <= 1.5%.
- B1 held-out clean FA rows: **KITTI 1.24%** (worst drive 0070: 3.0%), **comma continuous whole routes 1.10%**. MET.
- B2 no comma route above 5%: **NOT MET**. Route 2018-07-29--12-02-42 has 11.6%: its can-wheel residual has glitches (z mean -31, std 119;
  a data artefact of that low-speed route).
- B3 mean detection over the single-domain attacks: **KITTI 57.5% NOT MET**, comma 88.1% MET. KITTI per attack: drift 61, accel_drift 50,
  doppler_spoof 52, meaconing 52, lidar_scale 63, lidar_bias 80, lidar_yaw 19, can_scale 56, can_offset 75, can_freeze 67%. With LODO the
  thresholds are higher than with the 3 val drives of S2, so detection falls (S2 val: 81% selection detection at 0.9% val FA).
- B4 wrong blame <= 5%: **MET** (KITTI 3.4%, comma 1.4%). Correct / undecided: KITTI 55% / 41%, comma 46% / 53%.
- **Domain-level blame** (supervisor decision: comma's two CAN messages = one domain), applied to every data set: comma GNSS attacks are now
  96-98% "undecided" (speed has only GNSS vs CAN; the IMU sees only yaw). Single-message CAN spoofs: CAN blamed 100%. gnss_can: CAN blamed in
  all 126 detections (correct: one CAN message is spoofed). can_bus: 67% undecided, 33% CAN (never GNSS). The S2 wrong blame on can_bus is gone.
  KITTI lidar_yaw: undecided (LiDAR vs IMU only), as predicted.
- **The bias-tolerant CUSUM:**
  - Round 1 (pre-registered drift compensation, bias frozen while suspicious): it failed. The bias freezes within seconds when a route
    starts with a bias, so it never adapts. Comma FA 8.8-10.5%.
  - Round 2 (post-hoc, labelled; written in the notes before running): 60 s warm-up, then clip-bounded bias tracking. Best candidate
    `R2_wu60_k1_tb300`: **comma FA 1.85%**, mean detection 90.2%.
  - On the 4 comma val routes run continuously (the S2 35.7% case), FA is 28.8% with plain CUSUM, 0.95% with inst and **0.11% with
    R2_wu60_k1_tb300**: the bias tracking fixes the gyro / CAN-scale bias problem. Its pooled FA misses 1.5% only because of two train
    routes (12-02-42 glitches 17.8%, 08-34-47 8.8%).
  - On KITTI no CUSUM works (8-12% FA): drive 0070 (highway, ICP degenerate) has a lidar-can mean of +1.16 and gyro-lidar std 1.58.
    That is a witness-quality problem, not a slow bias. The LiDAR quality flag (sigma x3) is not used by the sigma model.
- What S3 will test (frozen in `results/WP6/s2b_choice_r2.json`): inst |z|, LODO thresholds, domain-level blame. The optimism of choosing among
  11 candidates on the same folds is small here, because the rule picked the simplest candidate.

## Goal of the step
Supervisor 2026-10-22: a bias-tolerant sequential test, leave-one-drive/route-out thresholds on train + val, the one-domain rule for comma CAN,
and continuous whole-route evaluation. Target: FA <= 1.5% on held-out folds, with detection and blame reported. Validation only.

## Acceptance rule (notes/WP6_crossdomain.md "S2b start", written before results)
B1 pooled held-out FA rows <= 1.5% (KITTI and comma continuous). B2 no comma dev route > 5%. B3 mean single-domain detection >= 70% per data set.
B4 wrong blame <= 5%. B5 tests. Choice: FA <= 1.5%, then max selection detection.
Round 2 was added after round 1, labelled post-hoc, with the same rule and the choice made over both rounds.

## What was done
- `crossdomain/consistency.py`: `drift_cusum` (round 1), `robust_cusum` (round 2), `blame_domain_pattern`, layer options `tb`, `freeze`,
  `domain_level`; calibration tolerates never-observed edges.
- Tools: `WP6_S2_kitti.py build_dev`, `WP6_S2_comma.py build_dev` (dev episodes), `WP6_S2b_eval.py [1|2]`, `WP6_S2b_tables.py`.
- Results: `results/WP6/s2b_dev.json`, `s2b_choice.json` (round 1), `s2b_dev_r2.json`, `s2b_choice_r2.json` (final), `s2b_acceptance.json`, `s2b_tables.md`.
- Tests: 3 new (drift CUSUM continuation, robust CUSUM bias vs step, domain-level blame); 21 crossdomain tests pass; full suite 328 passed, 0 failed.

## Results
`results/WP6/s2b_tables.md`: every candidate (FA, worst group, detection, blame), per-attack table and per-group FA for the chosen statistic.

## Problems, surprises, open questions
1. KITTI detection at an honest (LODO) FA is 57.5%: short drives and one degenerate-LiDAR drive. Using the LiDAR ICP quality flag in the sigma model
   (sigma x3 when poor) is the obvious next fix (S3, validation).
2. For comma, `R2_wu60_k1_tb300` is the better deployment design (whole-route val FA 0.11%). It missed the pooled rule only because of 2 train routes, one with
   a data glitch. Should S3 add a glitch filter (e.g. reject |z| > 20 as sensor fault, not attack) and re-run the choice on validation?
3. Domain-level blame makes comma GNSS attacks "undecided" by design. A third speed witness (e.g. visual odometry from the comma video) would be needed to blame GNSS.
4. Warm-up limit: an attack already active at start-up is learned as bias.

## Proposed next step
S3 fusion with this cross-domain Evidence (inst |z|, LODO tau, domain blame). The single test run of the S2b design is in S3, labelled.
