# WP6 S3: system fusion v3 over 5 domains + cross-domain Evidence

Date: 2026-10-24 (work 2026-10-22 to 2026-10-24)    Worker: opus (WP6, T4)

## Summary (verdict first)
- **Verdict: PARTIAL.** Met: G2 detection, G3 cross-domain gain, G4 explanations / attribution, G6 tests. **NOT MET: G1 false alarms (the main
  result) and G5 (no domain lost).** Numbers: `results/WP6/s3_test.json`, `s3_acceptance.json`, tables `results/WP6/s3_tables.md`.
- **Exposure caveat.** Every domain test set was scored before: ROAD 6x, D10 several times (WP4 S2-S7), VeReMi 2x, KITTI several times.
  The fusion layer is new and was scored on test ONCE. The S2b cross-domain choice gets its first test number here.
- **No dataset has all five domains.** Composite "drives": each domain's own test stream on a common 1 Hz clock. Family K = one KITTI run
  (GPS domain + cross-domain + LiDAR of the same drive) + ROAD CAN + D10 one-host network view + VeReMi ego view. Family C = one comma
  120 s window (cross-domain only) + the same CAN / network / V2X. One domain is attacked per composite, plus coordinated GPS+CAN.
  LiDAR is **INTERIM** (WP3 S1 v2 baseline + S2 L1). Fusion must be re-run when M1-LiDAR closes.
- Fusion: per-domain tick ECDF (validation half A), then a label-free combiner, then a tie-safe 2% threshold (half B). Halves are by
  group (drive / capture / block / route). **noisy_or was chosen** on validation over max (pooled half-B detection 81.0% vs 77.9%).
- **G1 FA per tick on clean test composites: K 6.36% [5.0, 7.7], C 6.31% [5.1, 7.5]; rule <= 3.0%: NOT MET** (validation half B:
  1.99% / 2.00%). Alarm events per clean hour: **K 119, C 94** (validation already 40 / 32). A system that alarms on 2% of seconds
  gives ~30-70 alarm events per hour. The temporal correlator (S5) must reduce this before any deployment claim.
- Cause (post-test diagnostic `s3_diag.json`, no choice made from it): every domain's clean tick scores are higher on test than on
  validation. Share of clean ticks above the 0.99 calibration level, val half B -> test: CAN 3.0 -> 5.8%, V2X 1.4 -> 4.2%,
  cross 0.3 -> 1.3%, network 2.7 -> 2.7%. Each domain at its own threshold on test ticks: LiDAR 7.7% (only 155 clean ticks),
  V2X 6.1%, network 4.4%, CAN 3.4%, GPS 1.8%, cross 1.1%. Strongest contributor at the clean alarm ticks: network 38%, CAN 20%,
  V2X 19%, GPS 17%.
  Two construction effects: (a) a tick takes the max over many samples, so it depends on traffic density (VeReMi test blocks are
  denser than val); (b) network minutes are held for 60 ticks. The validation pools are small (KITTI half A = 1 drive; ROAD has
  2 val ambient captures + LOCO folds).
- **G2 K mean detection over 52 single-domain families: 82.5% [75.2, 89.0] (>= 70%) MET**, but at the 6.4% FA above. Per attacked
  domain: V2X 95.2, CAN 93.0, network 75.7, GPS 66.2, LiDAR (interim) 62.7, cross-only families 53.9. C: 94.9%.
- **G3 cross-domain gain (K, without-cross row with its threshold re-fitted on validation): vehicle-block families +25.1 points
  (>= +10) MET; GPS families +17.5 (>= +5) MET.** Examples: drift 51 -> 74%, CAN wheel-speed spoofs 22-25 -> 56-59%.
  Coordinated gps_can 38 -> 61%. comma C: GNSS attacks 53-57 -> 89-99%.
- **G4: 119,952 / 119,952 alarms (K) and 544,813 / 544,813 (C) carry an explanation.** An explanation lists the domains that fired,
  their scores, the layers that fired, and the cross-domain blame. Attributed detection (the first alarm names the attacked domain)
  93.4% (>= 80%) MET. Weak spots: Web-XSS 0% (detected through other domains' noise), lidar_yaw 29%.
- **G5 no domain lost (fused >= alone - 15 points): NOT MET.** LiDAR 62.7 vs 100% alone (but LiDAR alone has 7.6% FA), cross
  53.9 vs 79.3%. GPS (-2.7), CAN (-7.0), V2X (-4.0) and network (+30) are within the rule. Sharing one 2% budget across 6 domains
  costs the weak-signal domains most.
- Combiner rows (test): max 5.16% FA / 71.6%; seen-attack logistic (labelled, never headline) 5.83% / 81.3%. **The learned combiner is
  not better than the label-free noisy_or.**
- **Cross-domain layer alone at its own 1% threshold (first test number of the S2b choice): KITTI FA 1.07%** (S2: 4.42%),
  detection 33-83% per attack. **comma FA 1.82%** (S2 run 2: 5.36%), detection 84-100%.
- S3 cross additions (validation only): the KITTI LiDAR quality flag changes nothing. The cached ICP quality is "ok" on 100% of scan
  pairs, including degenerate drive 0070, so the flag cannot help. The comma glitch filter was CHOSEN by the S2b rule (worst route
  11.6 -> 5.0%, selection detection +0.8). **Side effect: correct blame fell 45.8 -> 18.0%** (wrong blame 1.4 -> 3.4%), because large
  CAN spoofs now look like sensor faults. An attacker could hide behind the filter. Supervisor decision needed.
- **v2 comparison (NOT like-for-like):** v2 meta 95.23% accuracy at 1.06% FA. v2 drew one row per domain per sample, used a
  supervised meta-classifier on the tested classes, and random halves. v3 composite-level 50/50 accuracy: K 68.8%
  (composite FA 44%, detection 82%), C 55.2% (composite FA 84% over 120 s windows). **v3 is not better than v2 on this view.**
  The v3 view is far stricter: any alarm anywhere in a 20-120 s clean drive counts as a false composite.
- Tests: 7 new (`tests/fusion/test_fusion.py`); full suite: see the "Tests" section below.

## Goal of the step
Fuse the five frozen domains and the cross-domain Evidence into one explained system alert at a 2% system budget, using label-free
combiners for zero-shot. Evaluate on composite drives, with an ablation and a comparison to v2.

## Acceptance rule (notes/WP6_crossdomain.md "S3 start", written before any S3 result)
G1 clean test tick FA <= 3.0% (K and C). G2 K mean detection over the single-domain families >= 70%. G3 cross gain >= +10 points
(vehicle-block families) and >= +5 (GPS families). G4 100% explained, attributed >= 80%. G5 per attacked domain: fused >= alone - 15
points. G6 tests. Reported but not judged: C, coordinated scenarios, delays, v2.

## What was done
- `fusion/streams.py` (1 Hz tick series format, tick max, minute hold), `fusion/composite.py` (composite builder),
  `fusion/system.py` (SystemFusion, SystemAlert explanation, alarm events).
- Tools: `WP6_S3_crosschoice.py` (val-only cross additions), `WP6_S3_streams.py` (frozen domains -> tick series, cache
  `../data_extra/cache_v3/WP6/s3_*.pkl`), `WP6_S3_dev.py` (halves, choice, frozen `s3_frozen.pkl`), `WP6_S3_test.py` (the one test run;
  `WP6_S3_SMOKE=1` = plumbing on val), `WP6_S3_tables.py` (tables + post-test diagnostic).
- The V2X physics-only stack was rebuilt here from the WP5 recipe. Its layer thresholds equal WP5 S6 exactly (max diff 0.0).
- Network = view of host 192.168.10.50: Bot / Infiltration are not in this view. The GPS domain is scored on the clean run for
  the LiDAR-odometry / CAN-speed families (approximation). The GPS domain's validation scores are in-sample (it was calibrated
  on train + val).

## Results
`results/WP6/s3_tables.md`: combiner choice, headline and alternative rows, full ablation (each domain removed / alone, K and C),
detection / median delay / attribution / blame for all 52 (K) and 49 (C) families, cross alone, per-domain own FA, diagnostic, v2 view.
Ablation highlights (K test): without V2X 54.8%, without CAN 71.4%, without cross 76.8%, without LiDAR 78.8%, without GPS 80.9%,
without network 81.7% (network removal raises clean events per hour: 173 vs 119; the threshold moves).

## Problems, surprises, open questions
1. FA transfer is the main failure, as in S2 / S2b. Proposal for S5 (validation only): calibrate each domain's tick score per
   traffic density (messages / flows per second), use leave-one-group-out ECDFs over all validation groups instead of half A,
   and add the temporal correlator (event = k alarms in w seconds).
2. Glitch filter vs blame (above): keep it, or drop it because it lets large CAN spoofs pass as faults?
3. LiDAR interim: single-return phantoms are not evaluated (no test rows; WP3 S9). GhostCluster is shown only as a v2-comparison row.
4. G5 as written penalises budget sharing. Should later steps compare at equal test FA instead?

## Tests
Full suite: 364 passed, 0 failed (7 new in tests/fusion).
