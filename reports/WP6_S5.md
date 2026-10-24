# WP6 S5: density-aware calibration, LOGO system threshold, temporal correlator + response, M2 test run

Date: 2026-10-24    Worker: opus (WP6, T4)

## Summary (verdict first)
- **Verdict: NOT MET (1 of 7 test rules met: A7 explanations; A8 tests pass).** Numbers: `results/WP6/s5_test.json`, `s5_acceptance.json`, tables
  `results/WP6/s5_tables.md`, validation `s5_dev.json`, post-test diagnostic `s5_diag.json`. M2 system frozen: `results/WP6/m2_system.pkl` / `.json`
  (`fusion.system.load_m2()`).
- **Exposure.** Every domain test set was scored before. The fusion test composites are the S4 ones (same seeds): this is the third fusion-level exposure (S3, S4, S5).
  The M2 calibration, the correlator and the response policy are scored on test once here.
- **Validation fixes (3 group folds, nested held-out, no test data).** S3-style halves + noisy_or: K held-out FA 2.71% (fails the 2.5% bound). LOGO threshold: 2.17%.
  Density transform q = G(M)^(k^alpha): alpha_v2x = 1 gives +1.8 points. alpha_net > 0 costs 2-8 points: the flows of one minute share host features, so they are not
  independent samples. **Chosen: LOGO, noisy_or, alpha_v2x 1, alpha_net 0.** Validation held-out FA: K 2.15%, C 2.04%.
- **Correlator (chosen on validation): 2 alarms in 5 s, or 2 domains with their own alarm in the same tick (corroboration); alarms within 15 s merge.**
  Validation: 8.2 alert events per clean hour (K and C), against 48.8 / 37.5 with the S3 alarm runs. Event detection 67.8%, against 77.5% at tick level.
- **Test (once):**
  - **A1 raw clean tick FA: K 2.08% [1.28, 3.30] MET; C 6.70% [5.95, 7.66] NOT MET.** S3: 6.36 / 6.31%; S4: 2.73 / 4.78%.
  - **A2 alert events per clean hour: K 25.4 [13.0, 45.6], C 31.0 [28.6, 33.3]; rule <= 10: NOT MET.** Without the correlator: 54.1 / 119.9.
  - **A3 K mean event detection (single-domain families) 60.2% [45.4, 72.6]; rule >= 70%: NOT MET.** Tick level: 68.7%.
  - **A4 K held-out (zero-day) types 58.8% [44.1, 70.9]; rule >= 60%: NOT MET.**
  - **A5 K blame: 86.7% correct, 13.2% wrong; rule: wrong <= 10%: NOT MET.**
  - **A6 safe-stop recommendations per clean hour: K 0.0, C 1.23; rule <= 1: NOT MET.**
  - **A7: 10,467 / 10,467 (K) and 18,454 / 18,454 (C) events explained: MET.**
- **What cross-domain adds** (ablation; the threshold without cross is re-fitted on validation): K vehicle-block families 43.6% vs 19.0% (+24.7 points). GPS families gain
  19-32 points; LiDAR-odometry and CAN wheel-speed spoofs gain 22-33 points (lidar_yaw: +6). C: +51.4 points. The overall K mean does not change (60.2 vs 60.4%),
  because without cross the other domains get the budget. Coordinated gps_can: 55% vs 25%.
- **Why FA does not transfer (post-test diagnostic, no choice made from it).** Every entry's clean test ticks sit higher than on validation. Share of clean ticks above
  the 0.99 calibration level, validation -> test: v2x 1.2 -> 2.6% (K), can 1.0 -> 3.6% (C), cross 0.7 -> 2.1% (K). In C, 69% of the 120 s clean composites contain
  an alert event (K: 16% of the 16 s composites). **So the C detection numbers (96%) are not informative.** The 41 C safe-stops come from ROAD CAN false alarms that
  last >= 30 s.
- **Blame weakness found.** The event rule (most frequent DECIDED tick blame) lets one noisy decided tick decide the event. Two results follow. comma GNSS attacks are blamed
  on can / v2x (0% correct: S2b domain-level blame leaves them undecided). KITTI cross-only families are only 4-50% correct. Domain families: V2X 96-100%, CAN 92-99%
  (max_speedometer_masquerade 33%), GPS 92-98%, network 0-79%.
- Response per scenario (test, share of detected composites; `s5_tables.md` section 5):
  - V2X attacks mostly reach DEGRADE (80-92%), CAN signal attacks 56-89%.
  - KITTI LiDAR and cross-only families mostly stay at WARN.
  - SAFE_STOP happens on coordinated attacks: gps_can 17.6% (K), gnss_can 83% (C). It also happens on comma CAN wheel-speed spoofs (76-85%) and on max_speedometer
    in C (98%).
  - Median first-alert delay (event): V2X 2 s, CAN 1-4 s, GPS 2-5 s (K), cross-only 3-5 s, network 2-11 s (Web-XSS 11 / 33 s). The tick level is about 1 s faster.
  - **Network evidence is up to ~5 min late in the streaming runtime** (WP7 S1b). The composites show it only 1 min late, so the network delays are optimistic.
- **v2 side-by-side (NOT like-for-like):** v2 live simulation (supervised meta + temporal correlator): 1.90% FA per row, 84.2% recall per row. v3 M2 K: 2.08% of clean
  ticks, 25 alert events per clean hour, 26% tick recall, 60% composite event detection. v2 used a supervised meta-classifier on the tested classes, long attack
  blocks, random halves and no clean-hour metric; v3 uses label-free fusion with held-out types and group-aware thresholds.

## Goal of the step
Validation-only fixes for the S3 FA miss (density-aware calibration, LOGO system threshold). Temporal correlator + response module (alert events, persistence /
corroboration, response policy). One labelled test run of the final M2 system. M2 report. Freeze the M2 system for WP7.

## Acceptance rule (notes/WP6_crossdomain.md "S5 start", written before any S5 result)
A1 raw clean tick FA <= 3.0% (K and C). A2 alert events per clean hour <= 10 (K and C). A3 K mean event detection, single-domain families, >= 70%. A4 K held-out types
>= 60%. A5 K blame: correct >= 75% and wrong <= 10%. A6 safe-stops per clean hour <= 1. A7 100% of events explained. A8 tests pass. One refinement was made before any
result: a cross-only alarm with undecided blame stays undecided (tick blame rule 3).

## What was done
- `fusion/correlator.py`:
  - TemporalCorrelator (episodes, m-of-w persistence, corroboration, gap merge, LOG ticks) and AlertEvent.
  - tick_blame and respond (LOG / WARN / DEGRADE / SAFE_STOP with actions).
  - The v2 temporal correlator / response logic was re-written; v2 `windowing/` is retired.
- `fusion/system.py`: DensityTransform, M2System (density -> ECDF -> noisy_or -> threshold -> correlator -> response, with explanations) and load_m2.
- `fusion/composite.py`: segments carry `count` and `grp`.
- `tools/WP6_S3_streams.py`:
  - PREFIX.
  - Glitch override.
  - Per-tick counts and clean per-sample scores for v2x / network. The S3 scores are unchanged: max diff 0.0, asserted.
- `tools/WP6_S5_{streams,lib,dev,test,diag,tables}.py`.
- Tests: `tests/fusion/test_correlator.py` (8) and `test_m2.py` (2).
- Packs: s5_cross_comma (no glitch filter, ORCHESTRATOR decision), s5_network / s5_v2x (+ counts), s5_lidar (L1 union only). Cache 167 MB in total.
- Disclosure: the pack check printed the cross_comma clean own-alarm rate on test (1.25% vs 1.82% with the filter). No choice depends on it.

## Results
- `results/WP6/s5_tables.md`:
  1. acceptance
  2. calibration grid (36)
  3. correlator grid (18)
  4. headline with CIs
  5. per family: event / tick detection, delays, blame, response
  6. ablation (each domain removed; correlator off)
  6b. cross-domain gain
  7. equal-FA G5 (test-informed)
  8. diagnostic
  9. v2
- Ablation (K, test, event detection):
  - without v2x 32.1%, without can 50.3%, without gps 64.5%, without network 63.6%, without lidar 68.5% (+8.3: the interim L1 costs budget), without cross 60.4%.
  - correlator off: 68.7% at 54 events / h.
- Equal-FA G5 (test-informed, labelled). Fused vs alone at the same tick FA:
  - Fused loses for can (81 vs 100), v2x (87 vs 99), gps (61 vs 74) and cross (39 vs 69).
  - Fused gains for network (53 vs 19) and lidar (16 vs 0).

## Problems, surprises, open questions
1. FA transfer is still the main failure. LOGO fixed the validation estimate, but C FA on test is 6.7% (CAN and V2X scores are higher on test). The validation pools are
   small (ROAD: 10 clean captures; comma: 17 routes; KITTI: 3 val drives), and 4 comma test routes / 7 KITTI drives give wide CIs.
2. Event blame should require a decided majority over the event's alarm ticks, not just the most frequent decided tick. This is a fix for validation only (addendum),
   not applied after the test.
3. The response policy turns long CAN false alarms into SAFE_STOP (C 1.23 per clean hour). A safe-stop probably needs corroboration by a second domain. This is a
   policy question for the supervisor.
4. LiDAR is INTERIM: the label-free L1 detects 8-33% of the LiDAR families and costs detection elsewhere. The M2 addendum re-runs fusion when M1-LiDAR closes.
5. The composite construction makes C detection uninformative at this FA. A composite-level FA is reported in the diagnostic.

## Proposed next step
Supervisor review of M2 (reports/M2.md). M2 addendum when M1-LiDAR closes: re-run with the frozen LiDAR domain, plus the blame-majority fix chosen on validation.
WP7 S2 can consume `fusion.system.load_m2()`.

## Tests
Full suite: 406 passed, 0 failed (10 new in tests/fusion).
