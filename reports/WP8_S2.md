# WP8 S2: fusion false alarms on clean driving, events per hour, SAFE_STOP; system detection (v3.1)

Date: 2026-11-04    Worker: opus (WP8 S2, T3)

## Summary (<= 40 lines)
- **Verdict on V31_val: MET** (every S0 rule S2 row; one pre-registered round, results/WP8/S2/r1_eval.json "acceptance"). Rule and grid were committed (8bf6910)
  before any fused number; a second run of the same code reproduces every number. No H31 file was opened.
- Material: V31_val only, v3.1 frozen domain outputs: GPS v3, LiDAR frozen_lidar31 (leave-one-drive-out scan scores, because the frozen references contain the
  val drives), CAN IncrementalCan, V2X EgoStream view (per-ego heard table), network F1, cross = v3 recipe fitted on train (S6), blame A1. Composites: WP7 S2
  construction; K 1,769 attack composites (53 single-domain types, 11 held out), C 1,191 (44 / 11), 19 + 19 clean timelines (7.07 h per family).
- Protocol: entry ECDFs leave-one-group-out (drive / route / capture / VeReMi block / D10 day), system threshold leave-one-timeline-out for clean metrics.
- Chosen by the registered rule: **MX|L100|b2|m2w5|g15|d0|k1** = equal per-domain split of the 2 % system budget (= max combiner) instead of noisy_or; v3
  persistence (2 of 5), gap 15, v3 SAFE_STOP corroboration; tick_blame31 + A1 (S6 fallback fix). 644 / 648 candidates feasible; 24 within 0.5 points of the best
  detection; tie-break = fewest settings changed from v3.

| row (V31_val, out-of-fold, 95 % CI) | chosen K | chosen C | R0 = v3 recipe K / C | rule | verdict |
|---|---|---|---|---|---|
| clean tick FA | 1.92 % [1.38, 3.45] | 1.85 % [1.17, 3.63] | 1.97 / 1.91 % | <= 2.5 % | MET |
| alert events per clean hour | 5.09 [3.35, 6.41] | 4.95 [3.11, 7.04] | 8.35 / 7.08 | <= 8 | MET |
| SAFE_STOP per clean hour | 0.00 [0, 0] | 0.00 [0, 0] | 0.00 / 0.00 | <= 0.8 | MET (not informative) |
| K mean event detection, single-domain types | 78.2 % [76.1, 80.0] | (88.1 %) | 53.3 % [50.9, 55.9] | >= 70 % | MET |
| K held-out types | 82.4 % [76.1, 88.5] | (76.0 %) | 57.2 % | >= 60 % | MET |
| blame correct / wrong (equal weight per type) | 79.9 / 7.0 % | 95.6 / 0.3 % | 79.8 / 6.0 % | >= 75 / <= 10 | MET |
| events explained | 1,447 / 1,447 | 1,382 / 1,382 | | 100 % | MET |
| time-to-visible, persistent types (median) | 5 s | 4 s | 7 / 6 s | <= R0 + 5 s | MET |

- What moved the numbers: the noisy_or of 6 entries dilutes one strong domain (K detection +24.9 points with the equal split, events/h 8.35 -> 5.09).
  Persistence m3w5 / m3w10 would cut events to 0.28 / 0.71 per hour but costs 9-12 points of detection; gap 60 lowers events to 4.39/h but creates
  SAFE_STOP 0.42/h unless de-dup + k 3 (0.00); b 1.5 % gives FA 1.42 %, 3.11 events/h, 73.5 %. L125 equals L100 at system level (entry re-calibrated).
- Blame fix (S6 decision): comma GNSS spoofs at system level drift 73 % correct / 10 % wrong, meaconing 64 / 0, doppler 94 / 0 (v3 tick blame on the same events:
  0 % correct, 34-54 % wrong). KITTI gps_can still wrong 76 % (S6 B1 limit). Labelled variants: blame v3 K 79.2 / 7.4, C 90.0 / 4.7; A3 K 80.3 / 8.3;
  network RC5 K detection 79.3 %; motion-critical SAFE_STOP identical (no clean SAFE_STOP to remove).
- Budget split: equal share per entry of the 2 % tick budget (K: gps, lidar, can, network, v2x, cross; C: can, network, v2x, cross); thresholds of the frozen
  system K 0.99545, C 0.99405 (max of the per-entry ECDF scores).
- Frozen: results/WP8/S2/frozen_system31/system31.pkl, sha256 a8994883b00405896043e76c2d07102de61bbb1471eac7cdae4ec207d11aaa2f (fusion.system31.load_system31()).
- Regression: load_system(2) reproduces the S6 fixture exactly; fusion/system.py, correlator.py, fusion_runner.py unchanged since v3.0 (tests/v31/test_s2_regression.py);
  SystemV31 configured as v3 reproduces SystemV2 on the fixture (test_s2_system31.py).
- Honest limits: (1) LiDAR stays weak in the system: lidar_scan types 13.3 %, PointDrop per-scan composites 5 / 10, PointDrop 3 s episodes 0 / 30 (one strong
  onset scan never makes the 2 alarm ticks of the persistence rule): M4-8 "in-system PointDrop >= 60 %" is expected NOT met in S7. (2) FA CI upper ends
  3.45 / 3.63 % exceed the M4 bound 3 %: LOTO thresholds on timelines that share chained sources understate drift (S5b: 2.1 -> 3.5 %). (3) SAFE_STOP is 0 on
  every V31_val clean timeline for every candidate, so the SAFE_STOP bound is not exercised (M3 test had 0.38 / 1.64 per hour). (4) Small pools: 9 CAN episodes,
  CAN clean pool 491 ticks; V2X capped (40 egos per block, 30 episodes per class). (5) R0 is the v3 fusion recipe on v3.1 domain inputs, not the v3 system.

## Goal of the step
Cut clean-driving false alarms, events per clean hour and SAFE_STOP per clean hour on the V31_val timelines with persistence / hysteresis, cross-domain
de-duplication and a per-domain budget split inside 2 %, label-free; keep or raise mean event detection; fix the tick_blame fallback (S6 decision).

## Acceptance rule (as written in the notes BEFORE the result)
notes/WP8_v31.md, S0 rule "S2" (2026-11-03) and "2026-11-04 S2 round 1: pre-registration" (commit 8bf6910, journal 2026-11-04): feasible = FA <= 2.5 %,
events <= 8/h, SAFE_STOP <= 0.8/h (K and C); maximise K mean single-domain detection, G8 tie rule; accept = constraints AND detection >= 70 % AND held-out >= 60 %
AND blame >= 75 / <= 10 AND 100 % explained AND time-to-visible <= R0 + 5 s.

## What was done
- New: fusion/system31.py (SystemV31, Correlator31, tick_blame31, load_system31), tools/WP8_S2_build.py (V31_val tick sources), tools/WP8_S2_sim.py (composites,
  LOGO / LOTO calibration, grid, selection, full re-run, scores), tools/WP8_S2_freeze.py, tests/v31/test_s2_system31.py, test_s2_regression.py. Changed:
  tests/v31/test_s6_regression.py (git diff check limited to modified / deleted v3 files, so that the new fusion/system31.py does not fail it).
- Sources: ../data_extra/cache_v3/WP8/S2/*.pkl (rebuild 1 min: tools/WP8_S2_build.py). Logs results/WP8/logs/S2_{build,sim_r1,sim_r1chk,freeze,tests}.log.

## Results
results/WP8/S2/r1_eval.json (runs chosen, R0, R0b, variants; per type and per attacked domain), r1_grid.json (648 candidates), r1chk_eval.json (identical re-run),
frozen_system31/system31.json. Per attacked domain (K, chosen / R0 event detection): V2X 98.3 / 58.0, CAN 100 / 33.3, GPS 82.3 / 75.5, cross-only 69.0 / 43.2,
network 65.0 / 85.0 (FTP / SSH-Patator, one composite each, are detected by R0's noisy_or but not by the max), LiDAR 13.3 / 11.7.

## Scores (rule 6)
results/WP8/scores/S2/{K,C}_{attack,clean}_val_r1_{chosen,R0}.npz (per tick fused score, alarm, label, composite id, group, threshold; committed, 1.2 MB total).

## Problems, surprises, open questions
- For S7: M4-8 (in-system PointDrop) is a structural miss of the 2-of-5 persistence rule with one-scan evidence; a LiDAR-only confirmation rule would be a new
  mechanism (not in the S2 grid) and is not proposed without a new round.
- Supervisor option: b = 1.5 % (FA 1.42 %, 3.11 events/h, detection 73.5 %) buys drift margin at -4.7 points; the registered rule chose b = 2 %.
- The S0 text "16 K + 16 C clean timelines" became 19 + 19 (D10 val has 19 clean host blocks); written in the round-1 notes before the run.

## Proposed next step
Supervisor review; S7 runners feed SystemV31 (inputs listed in frozen_system31/system31.json "meta.inputs").
