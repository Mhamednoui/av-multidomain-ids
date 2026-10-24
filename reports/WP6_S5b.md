# WP6 S5b: M2 addendum with the frozen LiDAR domain (system v2)

Date: 2026-10-25    Worker: opus (WP6, T4)

## Summary (verdict first)
- **Verdict: NOT MET.** Met: 3 of 7 test rules (A4 held-out, A5 blame, A7 explanations) plus A8 (tests pass).
  - Numbers: `results/WP6/s5b_test.json` and `s5b_acceptance.json` (this file fills the make_report "M2 addendum" slot).
  - Tables: `results/WP6/s5b_tables.md`. Validation: `s5b_dev.json` (round 1 = `s5b_dev_round1.json`).
  - Re-frozen system: `results/WP6/system_v2.pkl` / `.json`, loaded with `fusion.system.load_system(2)`.
- **Exposure.** This is the 4th scoring of fusion test data (S3, S4 and S5 before).
  - The test composites are NEW: a new random pairing of the domain test streams, seed [42, 66, 5, ord(family)], written in the notes before they were built.
  - The KITTI LiDAR test drives are seen for the 8th time.
  - One test run.
- **Test (once), with M2 alongside:**

| rule | S5b | M2 | bound | verdict |
|---|---|---|---|---|
| A1 raw clean tick FA, K / C | 3.50% [2.2, 4.5] / 7.41% [6.6, 9.2] | 2.08 / 6.70% | <= 3% | NOT MET |
| A2 alert events per clean hour, K / C | 17.5 [7.8, 25.3] / 28.7 [26.5, 32.3] | 25.4 / 31.0 | <= 10 | NOT MET |
| A3 K mean event detection, single-domain families | 57.6% [45.1, 69.5] | 60.2% | >= 70% | NOT MET |
| A4 K held-out (zero-day) types | 60.5% [48.0, 72.6] | 58.8% | >= 60% | MET |
| A5 K blame correct / wrong | 88.0 / 6.2% (5.8% undecided) | 86.7 / 13.2% | >= 75 / <= 10% | MET |
| A6 SAFE_STOP per clean hour, K / C | 0.08 / 1.05 | 0.0 / 1.23 | <= 1 | NOT MET (C) |
| A7 events explained | 10,725 / 10,725 and 17,862 / 17,862 | 100% | 100% | MET |

- **What changed and why:**
  1. **LiDAR = frozen domain** (lidar/domain.py, max of L1, L2a, L2c, L2d at the 1% scan budget). This replaces the interim L1-only input.
     - LiDAR families at event level, K, single-return set, every 3rd scan attacked: IntensitySpoof 44.3%, near replace 27.7%, PointDrop 17.3%; far / budget phantoms
       5.7-10.3%, which is near chance (10.4% of clean K composites contain an event).
     - LiDAR-domain mean: 18.6% vs 9.8% in M2. M2 used different (v2) LiDAR generators, so this is not like-for-like.
     - Persistent 3 s phantom episodes: 1-8% (world-fixed ones are invisible after the first scan, as in M1-LiDAR).
     - Removing LiDAR (threshold from validation) gives K detection 62.3% at FA 4.1%. LiDAR still costs detection on the other families under the shared budget,
       but less than in M2 (there: +8.3 points without LiDAR; here +4.7).
  2. **Event blame by decided majority** (majority_decided, chosen on validation): wrong blame drops from 13.2% (M2) to 6.2%; 5.8% of events become undecided.
     - On the same test alarms, the M2 plurality rule gives 90.1 / 9.8%. The rule alone removes about 3.6 points of wrong blame. The rest comes from the new
       pairing and LiDAR.
  3. **SAFE_STOP only with >= 2 corroborating domains** (a priori): C drops from 1.17 to 1.05 per clean hour on the same alarms. It is still just above 1.
     - The 35 remaining clean C SAFE_STOPs are all blamed on CAN (median duration 44 s). Each co-occurs with another domain's own alarm: v2x in 29, cross in 18.
       The V2X own alarm fires in 7.5% of clean C ticks, so "2 domains" is easy to meet by chance (post-test diagnostic `results/WP6/s5b_diag.json`, no choice).
  4. **Budget allocation** chosen on validation, label-free: noisy_or stays. max and the weighted split cannot use the short KITTI pools (see problem 2).
  5. **Correlator re-chosen** with the M2 rule: 2 alarms in 5 s, gap 15 s, corroboration OFF.
     - This lowers K events from 29.0 to 17.5 per clean hour on the same alarms, against 25.4 in M2. C stays 28.7, against 31.0 in M2.
- **K detection on the 49 families shared with M2** (LiDAR excluded): 62.4%, against 62.3% in M2. The non-LiDAR part of the system behaves the same on the new pairing.
  A3 falls because the 6 single-return LiDAR families are weak by physics.
- **FA got worse on K (2.08 -> 3.50%).** The intervals overlap ([1.3, 3.3] vs [2.2, 4.5]), and the threshold, the domains and the S5 calibration are unchanged.
  - The new pairing of clean segments (7 KITTI vehicle groups) moves the estimate by about 1.4 points.
  - It is not LiDAR: without LiDAR the K FA is 4.1%.
  - FA still does not transfer from validation (2.12% held-out) to test.
- **Coupling test (GPS attack -> OXTS pose -> L2c / L2d):** worst case, the INS position follows the spoofed GNSS 1:1. All 350 test GPS runs.
  - **The coupling is real at sensor level.** Per-scan LiDAR alarm rate after onset, true pose -> coupled pose:
    - accel_drift: 1.6% -> 13.6%. L2d tracking goes from 0.3% to 13.7%: a pose that drifts quadratically makes static surfaces look like they move in free space.
    - doppler_spoof: 1.4% -> 2.7%. drift: 1.4% -> 2.2%. meaconing and gps_can: about unchanged.
  - **At system level it does not move the blame.** Composites of the GPS families, control vs coupled:
    - LiDAR own alarm on post-onset ticks: 5.1% -> 9.7% (mean of the 4 GPS families; accel_drift 6.2% -> 20.0%).
    - Events blamed on LiDAR: 0.0% -> 0.0%. Correct blame 88-93% in both. SAFE_STOP share: about unchanged (accel_drift 10.2% -> 10.1%).
    - Why: the GPS domain's own alarms and the cross-domain blame decide the event first; LiDAR alarms only add corroboration.
  - Caveats: the test drives are 8-45 s long, so a slow drift has little time to grow. A long attack could let the induced L2d alarms dominate.
  - Mitigation (future option): feed L2c / L2d with the LiDAR-odometry pose instead of OXTS.
- **Coordinated gps_can:** 55% of the detected events are blamed on LiDAR in BOTH variants, so this is not coupling.
  - The cross layer sees GPS and CAN agree and blames the honest LiDAR odometry. This break was predicted in S2.
  - SAFE_STOP is reached in 17%.

## Goal of the step
M2 addendum: replace the interim LiDAR with the frozen M1-LiDAR domain. Apply the post-M2 decisions:
- decided-majority blame;
- SAFE_STOP corroboration;
- label-free budget allocation;
- V2X on-deployment variant where real V2X is the source;
- coupling test.

Then score new test composites once, and re-freeze the final system (config version 2) for WP7 S2.

## Acceptance rule (notes/WP6_crossdomain.md "S5b start", written before any S5b result)
The rules are the M2 bounds A1-A8:
- A3 = single-domain families, with comparison rows and LiDAR episode families excluded; the 6 single-return per-scan LiDAR families included.
- A5 is judged with the decided-majority event blame.
- A6 is judged with the SAFE_STOP corroboration rule.

The coupling test, the A3 value on the M2-shared families and the ablations are reported, not judged.

Validation round 2 (written in the notes before it was run) is post-hoc and labelled. It added the train-drive clean LiDAR ticks to the LiDAR calibration pool.

## What was done
- `tools/WP6_S5b_lidar.py`: LiDAR tick pack built from the WP3 S9 stored raw layer scores, pushed through the frozen Stack and the per-layer calibrators.
  - Replay of raw test scans through `LidarDomain.stream()`: max difference 0.0.
  - Contents: per-scan attacks (every 3rd scan), persistent episodes (ep_ / epW_), and calibration-only clean series of the 13 train drives.
- `tools/WP6_S5b_coupling.py`: the exact WP1 GPS offsets are regenerated (asserted equal to the WP1 stream; receiver noise removed) and added to the OXTS pose.
  L2c / L2d are recomputed from the raw scans of the 7 test drives (Pool(4)). A zero-offset recompute equals the stored scores.
- `tools/WP6_S5b_lib.py`, `WP6_S5b_dev.py`, `WP6_S5b_test.py`, `WP6_S5b_tables.py`.
- `fusion/correlator.py`:
  - `event_blame` (plurality / majority_all / majority_decided);
  - `TemporalCorrelator(blame_rule, safe_stop_min_domains)`;
  - `respond(..., n_domains, min_domains)`.
  - The defaults reproduce M2 exactly, and old pickles still load: `load_system(1)` gives plurality, 1.
- `fusion/system.py`:
  - `wsplit_score` (weighted budget split) and `entry_domain` / `entry_part` (per-layer LiDAR entries);
  - `SystemV2` (config version 2: blame, corroboration and response on DOMAINS, so the LiDAR layers count as one domain);
  - `load_system(version)`. `M2System` / `load_m2` are unchanged.
- Tests: `tests/fusion/test_m2b.py` (8 tests).
- Caches: `../data_extra/cache_v3/WP6/s5b_lidar.pkl` and `s5b_coupling/`. The WP6 cache totals about 0.17 GB.

## Results
### Validation choices (3 S5 group folds, nested held-out; `s5b_tables.md` section 2)
- Calibration grid (12 configs: LiDAR entry x calibration pool x allocation):
  - Chosen: **combined LiDAR entry, train+val pool (round 2), noisy_or**, with held-out FA K 2.12% / C 2.04% and pooled detection 79.6%.
  - Round 1 (val pool): 79.1%. Per-layer entries: 78.0%.
  - max: 59.4%, the same for every variant (LiDAR never reaches the threshold).
  - Weighted split: C FA 3.26%, fails the bound.
- Correlator: m2w5_g15_c0, with 8.42 / 7.50 events per clean hour on validation.
- Blame: majority_decided, with wrong blame 4.4% (K) / 4.3% (C). Plurality (reference): 5.6% / 5.3%.

### Test headline (`s5b_tables.md` section 3)
| | K S5b | K M2 | C S5b | C M2 |
|---|---|---|---|---|
| WARN / DEGRADE / SAFE_STOP per clean hour | 10.33 / 7.13 / 0.08 | 21.59 / 3.81 / 0.00 | 10.59 / 17.04 / 1.05 | 13.41 / 16.32 / 1.23 |
| events per clean hour, correlator off | 83.3 | 54.1 | 125.5 | 119.9 |
| mean tick detection, single-domain | 72.2% | 68.7% | 98.3% | 98.5% |
| blame on coordinated scenarios (correct / wrong / undecided) | 17.4 / 56.9 / 25.7 | 35.8 / 63.6 / 0.6 | 60.7 / 27.7 / 11.6 | 67.9 / 28.9 / 3.2 |

**Event detection by attacked domain, K** (S5b vs M2):

| attacked domain | S5b | M2 |
|---|---|---|
| V2X | 84.0% | 79.1% |
| CAN | 72.5% | 69.4% |
| GPS | 50.1% | 56.4% |
| network | 38.1% | 44.1% |
| cross-only | 27.9% | 33.2% |
| LiDAR | 18.6% | 9.8% |

C is not informative at this FA: 65.5% of the 120 s clean C composites contain an alert event.

Median first-alert delays per family are in section 5 of the tables. They are about as in M2: V2X 1-2 s, CAN 1-7 s, GPS 3-5 s, LiDAR 4-7 s (episodes 1-2 s), network 2-11 s (K).
Network Evidence is up to ~5 min late in streaming (WP7 S1b), so the network delays are optimistic.

### Ablation (test; thresholds from validation; `s5b_tables.md` sections 6-7)
**K event detection with one domain removed:**

| removed | S5b | M2 |
|---|---|---|
| v2x | 27.7% | 32.1% |
| can | 46.2% | 50.3% |
| cross | 57.0% | 60.4% |
| lidar | 62.3% (FA 4.1%) | 68.5% |
| gps | 62.6% | 64.5% |
| network | 63.4% | 63.6% |

**Correlator off:** 72.2% at 83.3 events per hour.

**Rules on the same alarms:**
- M2 plurality blame: K wrong 9.8%, C wrong 13.3%.
- M2 one-domain SAFE_STOP: C 1.17 per hour.
- Both M2 rules: C 1.20 per hour.
- Corroboration-on correlator: K 29.0 events per hour, wrong blame 6.1%.

### LiDAR rows and coupling
`s5b_tables.md` sections 8 and 9 (see Summary).

## Problems, surprises, open questions
1. **FA does not transfer, and the alert rate stays far from deployable** (17.5 / 28.7 events per clean hour against <= 10). Nothing in S5b addresses the root cause:
   small validation pools (3 KITTI drives, 10 ROAD clean captures), and ROAD CAN / V2X clean ticks that score higher on test.
2. **ECDF resolution of short KITTI pools:** the LiDAR entry (and also gps / cross_kitti, unchanged) is calibrated on about 30-50 clean ticks, so its score tops out
   near 0.97.
   - Round 2 (labelled post-hoc) added the train-drive LiDAR ticks for LiDAR only.
   - gps / cross_kitti have the same limit. Fixing them would need train-drive clean ticks for those domains: an open option, not done.
3. SAFE_STOP is still 1.05 per clean hour on C: the corroboration rule is necessary, but not sufficient against long ROAD CAN false alarms.
   The noisy V2X own alarm (7.5% of clean ticks) supplies the second domain.
   - Options for the supervisor: require corroboration by a motion-critical domain other than the blamed one, or require a minimum share of corroborated ticks.
4. **Coupling:** induced L2d alarms are real (accel_drift 13.6% of scans) but do not reach the blame on 8-45 s drives.
   - For WP7 S2 (longer simulated attacks), feed LiDAR with the LiDAR-odometry pose, or report the coupling explicitly.
5. The S5 test composites and these new ones differ in pairing AND LiDAR. The non-LiDAR shared-family mean (62.4 vs 62.3%) shows the pairing itself changes
   little for detection. It changes FA by about 1.4 points on K.
6. `RESULTS_v3.md` is now stale: make_report fills the M2-addendum slot from `s5b_acceptance.json`, and the test-suite check skips until it is regenerated
   (orchestrator task).

## For WP7 S2: what to load
- `fusion.system.load_system(2)` returns {"K": SystemV2, "C": SystemV2}. Config: `results/WP6/system_v2.json`.
- The pickle is git-ignored (like m2_system.pkl). It is regenerated deterministically by `tools/WP6_S5b_lidar.py build`, then `tools/WP6_S5b_dev.py`.
- `SystemV2.run(parts)`: parts per DOMAIN carry score, count, layers, layer_alarm, dom_alarm, and blame (for cross).
- LiDAR part:
  - from `LidarDomain.load('results/WP3/S9/frozen_lidar').stream().push(points, pose, t)` per scan;
  - tick = floor(scan time); value = max over the second of the combined score, and of each of the 4 per-layer scores (L1, L2a, L2c, L2d);
  - own alarm = any scan alarm in the second;
  - real cost 1.84 s per scan (not real time).
- V2X: VeReMi view -> the frozen VeReMi stack. On real CAM traffic (V2AIX), use the WP5 S3b on-deployment variant (thresholds from the deployment's genuine
  validation + freshness) and re-fit the v2x entry ECDF on that deployment's clean ticks.
- Correlator: m2w5_g15_c0, blame majority_decided, SAFE_STOP needs >= 2 domains. Network Evidence arrives up to ~5 min late.

## Proposed next step
Supervisor review of S5b and of the M2 addendum (reports/M2.md, "Addendum 2026-10-25"). Then WP7 S2 on system v2. RESULTS_v3.md must be regenerated by the
orchestrator.

## Tests
Full suite: 476 passed, 0 failed, 1 skipped (the RESULTS_v3.md staleness check: the new acceptance JSON exists, so the orchestrator must regenerate RESULTS_v3.md).
8 new tests in tests/fusion/test_m2b.py.
