# WP5 S3: L2 plausibility (consecutive-beacon, kinematic, overlap, map)

Date: 2026-10-19    Worker: sonnet (medium)

## Goal of the step
F2MD-style plausibility per sender (Kamel et al.): position / speed / heading consistency between consecutive beacons, kinematic consistency, overlapping vehicles, map plausibility (Tampa only). Supervisor decisions applied: no receiver-position approximation; acceptance-range and sudden appearance are NOT in S3 (deferred to S3b, need real receiver positions); map check skipped on VeReMi (no Luxembourg map).

## Acceptance rule (notes/WP5_v2x.md, 'S3 L2 plausibility: acceptance rule', written before any S3 result)
1 nine Layers + unit tests; 2 no threshold fitted on test or attack data, limits cited, OSM recorded; 3 false alarms: every check and the union <= 1.5% (VeReMi) / <= 2% (Tampa), physical limits <= 0.1% on genuine val and test; 4 per-check, union and combined detection for all 19 classes (+S20), false alarms on genuine messages and senders, delay per attacker, harness ablation on top of L1, Tampa bootstrap CIs. Pre-registered expectations P1-P6 (below). Held-out attack types 6, 12, 17 (marked *) stayed out of calibration and of the combiner's validation set.

## What was done
- `v2x/l2.py`: nine Layers (domain v2x, layer L2, kind physics, causal): `pos_speed`, `pos_heading`, `speed_change`, `implied_speed`, `heading_rate`, `accel_consistency`, `yaw_consistency`, `overlap`, `map_road` (definitions, constants and sources in the module docstring). Thresholds from validation genuine messages only (1% budget, tie-safe, `calibrate_masked`: the whole validation frame is scored so neighbours exist, the fit uses genuine rows only); physical operating point (raw >= 1) for `speed_change`, `implied_speed`, `heading_rate`.
- `tests/v2x/test_l2.py` (15 tests: every check on synthetic data, causality, row-order independence, receiver separation, map distance, masked calibration). Full suite: 116 passed.
- `tools/WP5_S3_l2.py` (one dev run on validation, one dry run with validation as a stand-in test, one final run on test: `results/WP5/logs/s3_run1.log`), `tools/WP5_S3_diag.py` (post-hoc diagnostics, not used for any choice), `tools/WP5_S3_report.py` (this file).
- Data: VeReMi D12 (val/test as in S1, 7 evaluable L2 layers: no yaw rate, no map) and Tampa D14 with injected attacks (all 9 layers). Each Tampa scenario is scored together with the genuine rest of its split (neighbours for overlap), only attacker messages are evaluated. New dataset **D27 OSM Tampa** (Overpass, ODbL 1.0, drivable classes only, 1,782 ways, 1.4 MB) recorded in DATASETS.md and the notes.
- Operating points: each check at the 1% budget; the three limit checks also at the physical limit; `L2_union` = max of the calibrated L2 scores at ONE 1% budget (an OR of nine 1% checks would break the budget); `L1_and_L2_union` = L1 union (beacon rate budget OR field ranges physical OR freshness budget) OR `L2_union`; `combined_*` = harness combiner (chosen on validation) of the L1, the L2 and all layers.

### Not done, on purpose
- Acceptance-range threshold and sudden appearance (S3b: need real receiver positions). Map check on VeReMi (no Luxembourg map). No Tampa RSU centroid was used as receiver position.

## Results (generated from results/WP5/s3_*.json; full tables in results/WP5/s3_tables.md)

### What each class looks like, in one table (L2 union at the 1% budget; * = held-out type)

verdict: caught >= 80% of messages, partly 30-80%, not caught < 30% (message level). 'attackers >= 3 alarms' = share of attackers with at least 3 alarmed messages (sender-level view; genuine senders with >= 3 alarms: VeReMi 10.7%, Tampa 26.7%).

| class | VeReMi msgs (union L2) | VeReMi attackers >= 3 alarms | Tampa msgs (union L2) | Tampa attackers >= 3 alarms | verdict VeReMi / Tampa |
|---|---|---|---|---|---|
| 01_ConstPos | 86.4% | 98.9% | 15.0% | 100.0% | caught / not caught |
| 02_ConstPosOffset | 1.3% | 16.7% | 37.2% | 90.0% | not caught / partly |
| 03_RandomPos | 99.1% | 98.9% | 99.8% | 100.0% | caught / caught |
| 04_RandomPosOffset | 97.4% | 100.0% | 99.7% | 100.0% | caught / caught |
| 05_ConstSpeed | 96.1% | 98.8% | 54.3% | 100.0% | caught / partly |
| 06_ConstSpeedOffset * | 85.6% | 100.0% | 28.7% | 100.0% | caught / not caught |
| 07_RandomSpeed | 98.9% | 98.9% | 97.6% | 100.0% | caught / caught |
| 08_RandomSpeedOffset | 94.9% | 100.0% | 90.3% | 100.0% | caught / caught |
| 09_EventualStop | 1.1% | 8.0% | 3.1% | 10.0% | not caught / not caught |
| 10_Disruptive | 97.0% | 98.9% | 94.4% | 100.0% | caught / caught |
| 11_DataReplay | 68.4% | 98.8% | 11.4% | 90.0% | partly / not caught |
| 12_DelayedMessages * | 1.4% | 14.9% | 10.4% | 90.0% | not caught / not caught |
| 13_DoS | 73.8% | 100.0% | 2.5% | 60.0% | partly / not caught |
| 14_DoSRandom | 99.7% | 100.0% | 99.8% | 100.0% | caught / caught |
| 15_DoSDisruptive | 98.4% | 100.0% | 95.2% | 100.0% | caught / caught |
| 16_GridSybil | 60.9% | 98.9% | 5.1% | 90.0% | partly / not caught |
| 17_DataReplaySybil * | 17.4% | 92.9% | 39.6% | 100.0% | not caught / partly |
| 18_DoSRandomSybil | 0.0% | 0.0% | 71.0% | 100.0% | not caught / partly |
| 19_DoSDisruptiveSybil | 1.4% | 36.0% | 64.0% | 100.0% | not caught / partly |
| S20_StaleReplay | - | - | 78.9% | 100.0% | - / partly |

Caveat: the Tampa union includes the map check, whose false alarms do not transfer (union false alarms on genuine Tampa test messages 6.3%, acceptance bound 2%); read the Tampa columns together with the per-check tables, where the non-map checks keep their budget.

### VeReMi (D12) test

**VeReMi test: message-level detection per class, each L2 check at the 1% validation budget**

* = attack type held out of calibration and combiner. Physical limits below.

| class | v2x.pos_speed | v2x.pos_heading | v2x.speed_change | v2x.implied_speed | v2x.heading_rate | v2x.accel_consistency | v2x.overlap |
|---|---|---|---|---|---|---|---|
| 01_ConstPos | 88.2% | 0.0% | 1.0% | 0.0% | 0.9% | 1.2% | 1.5% |
| 02_ConstPosOffset | 1.1% | 1.2% | 1.0% | 1.4% | 1.1% | 0.9% | 0.3% |
| 03_RandomPos | 99.1% | 67.2% | 1.1% | 99.1% | 1.1% | 0.9% | 0.0% |
| 04_RandomPosOffset | 97.0% | 60.2% | 1.0% | 86.5% | 0.7% | 0.9% | 0.2% |
| 05_ConstSpeed | 97.4% | 1.1% | 0.0% | 0.4% | 0.2% | 19.9% | 0.2% |
| 06_ConstSpeedOffset * | 91.2% | 1.2% | 2.3% | 0.6% | 0.2% | 11.2% | 0.4% |
| 07_RandomSpeed | 98.0% | 1.1% | 77.8% | 0.5% | 0.0% | 90.1% | 0.3% |
| 08_RandomSpeedOffset | 86.0% | 0.8% | 53.3% | 0.3% | 0.2% | 77.0% | 0.4% |
| 09_EventualStop | 0.9% | 0.2% | 0.6% | 0.0% | 0.1% | 0.9% | 6.9% |
| 10_Disruptive | 96.2% | 56.0% | 58.4% | 91.0% | 22.1% | 75.4% | 7.9% |
| 11_DataReplay | 67.6% | 29.5% | 31.3% | 49.3% | 15.1% | 48.6% | 27.4% |
| 12_DelayedMessages * | 1.2% | 0.4% | 0.1% | 1.3% | 0.4% | 0.4% | 3.7% |
| 13_DoS | 83.7% | 0.4% | 7.3% | 25.8% | 2.0% | 25.0% | 1.3% |
| 14_DoSRandom | 99.7% | 93.0% | 92.1% | 99.7% | 54.9% | 96.4% | 0.0% |
| 15_DoSDisruptive | 98.5% | 57.9% | 75.1% | 95.1% | 44.6% | 85.2% | 6.7% |
| 16_GridSybil | 64.8% | 1.5% | 1.1% | 27.7% | 0.2% | 19.2% | 2.1% |
| 17_DataReplaySybil * | 17.0% | 1.7% | 1.7% | 3.3% | 0.7% | 7.8% | 25.9% |
| 18_DoSRandomSybil | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 19_DoSDisruptiveSybil | 0.3% | 0.0% | 0.0% | 0.1% | 0.0% | 0.1% | 11.0% |

**VeReMi test: message-level detection at the physical limits (no fitted threshold)**



| class | v2x.speed_change@physical | v2x.implied_speed@physical | v2x.heading_rate@physical | L2_physical_union |
|---|---|---|---|---|
| 01_ConstPos | 0.0% | 0.0% | 0.0% | 0.0% |
| 02_ConstPosOffset | 0.0% | 0.0% | 0.0% | 0.0% |
| 03_RandomPos | 0.0% | 98.5% | 0.0% | 98.5% |
| 04_RandomPosOffset | 0.0% | 4.4% | 0.0% | 4.4% |
| 05_ConstSpeed | 0.0% | 0.0% | 0.0% | 0.0% |
| 06_ConstSpeedOffset * | 0.1% | 0.0% | 0.0% | 0.1% |
| 07_RandomSpeed | 43.7% | 0.0% | 0.0% | 43.7% |
| 08_RandomSpeedOffset | 15.2% | 0.0% | 0.0% | 15.2% |
| 09_EventualStop | 0.2% | 0.0% | 0.0% | 0.2% |
| 10_Disruptive | 26.4% | 81.0% | 8.9% | 84.0% |
| 11_DataReplay | 10.7% | 39.8% | 5.8% | 43.5% |
| 12_DelayedMessages * | 0.0% | 0.7% | 0.0% | 0.8% |
| 13_DoS | 0.5% | 0.0% | 1.0% | 1.5% |
| 14_DoSRandom | 78.1% | 99.6% | 26.6% | 99.7% |
| 15_DoSDisruptive | 55.0% | 88.7% | 34.6% | 91.6% |
| 16_GridSybil | 0.1% | 9.9% | 0.1% | 9.9% |
| 17_DataReplaySybil * | 0.3% | 1.1% | 0.1% | 1.4% |
| 18_DoSRandomSybil | 0.0% | 0.0% | 0.0% | 0.0% |
| 19_DoSDisruptiveSybil | 0.0% | 0.0% | 0.0% | 0.0% |

**VeReMi test: message-level detection, unions and harness combinations**

L2_union = max of the calibrated L2 scores at one 1% budget; L1_union = beacon rate (budget) OR field ranges (physical) [OR freshness (budget) on Tampa]; L1_and_L2_union = L1_union OR L2_union; combined_* = harness combiner (chosen on validation) of the L1 / L2 / all layers.

| class | L2_union | L1_union_at_operating_points | L1_and_L2_union | combined_L1 | combined_L2 | combined_L1+L2 | combined_all |
|---|---|---|---|---|---|---|---|
| 01_ConstPos | 86.4% | 0.0% | 86.4% | 1.0% | 89.2% | 86.3% | 86.3% |
| 02_ConstPosOffset | 1.3% | 0.0% | 1.3% | 0.9% | 0.8% | 1.1% | 1.1% |
| 03_RandomPos | 99.1% | 0.0% | 99.1% | 1.4% | 99.1% | 99.1% | 99.1% |
| 04_RandomPosOffset | 97.4% | 0.0% | 97.4% | 1.1% | 97.0% | 97.3% | 97.3% |
| 05_ConstSpeed | 96.1% | 0.0% | 96.1% | 71.3% | 98.4% | 96.7% | 96.7% |
| 06_ConstSpeedOffset * | 85.6% | 0.0% | 85.6% | 9.5% | 93.0% | 85.2% | 85.2% |
| 07_RandomSpeed | 98.9% | 0.0% | 98.9% | 70.5% | 98.6% | 99.4% | 99.4% |
| 08_RandomSpeedOffset | 94.9% | 0.0% | 94.9% | 5.3% | 91.9% | 94.8% | 94.8% |
| 09_EventualStop | 1.1% | 0.0% | 1.1% | 0.2% | 1.2% | 1.1% | 1.1% |
| 10_Disruptive | 97.0% | 0.0% | 97.0% | 15.2% | 96.3% | 97.0% | 97.0% |
| 11_DataReplay | 68.4% | 0.0% | 68.4% | 6.0% | 72.2% | 68.3% | 68.3% |
| 12_DelayedMessages * | 1.4% | 0.0% | 1.4% | 0.1% | 1.9% | 1.4% | 1.4% |
| 13_DoS | 73.8% | 99.7% | 99.7% | 99.7% | 88.8% | 99.7% | 99.7% |
| 14_DoSRandom | 99.7% | 99.7% | 99.7% | 99.9% | 99.7% | 99.9% | 99.9% |
| 15_DoSDisruptive | 98.4% | 99.7% | 99.7% | 99.7% | 99.0% | 99.7% | 99.7% |
| 16_GridSybil | 60.9% | 22.0% | 61.5% | 23.5% | 68.8% | 61.4% | 61.4% |
| 17_DataReplaySybil * | 17.4% | 0.0% | 17.4% | 7.9% | 21.5% | 20.8% | 20.8% |
| 18_DoSRandomSybil | 0.0% | 0.0% | 0.0% | 70.2% | 0.0% | 70.0% | 70.0% |
| 19_DoSDisruptiveSybil | 1.4% | 0.3% | 1.5% | 13.7% | 0.3% | 13.1% | 13.1% |

**VeReMi test: sender-level detection (>= 1 alarm among the attacker's falsified messages / >= 3 alarms) and median delay (s)**

>= 3 alarms in the next table.

| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | 98.9% / 2.0 s | 98.9% / 2.0 s |
| 02_ConstPosOffset | 51.1% / 54.5 s | 51.1% / 54.5 s |
| 03_RandomPos | 98.9% / 1.0 s | 98.9% / 1.0 s |
| 04_RandomPosOffset | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 05_ConstSpeed | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 06_ConstSpeedOffset * | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 07_RandomSpeed | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 08_RandomSpeedOffset | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 09_EventualStop | 85.1% / 13.0 s | 85.1% / 13.0 s |
| 10_Disruptive | 98.9% / 1.0 s | 98.9% / 1.0 s |
| 11_DataReplay | 98.8% / 2.0 s | 98.8% / 2.0 s |
| 12_DelayedMessages * | 80.5% / 61.0 s | 80.5% / 61.0 s |
| 13_DoS | 100.0% / 0.9 s | 100.0% / 0.4 s |
| 14_DoSRandom | 100.0% / 0.5 s | 100.0% / 0.5 s |
| 15_DoSDisruptive | 100.0% / 0.5 s | 100.0% / 0.5 s |
| 16_GridSybil | 98.9% / 1.4 s | 100.0% / 1.3 s |
| 17_DataReplaySybil * | 97.6% / 8.0 s | 97.6% / 8.0 s |
| 18_DoSRandomSybil | 5.6% / 64.5 s | 5.6% / 64.5 s |
| 19_DoSDisruptiveSybil | 61.6% / 33.0 s | 62.8% / 32.5 s |

| class | L2_union >= 3 alarms | L1_and_L2_union >= 3 alarms |
|---|---|---|
| 01_ConstPos | 98.9% | 98.9% |
| 02_ConstPosOffset | 16.7% | 16.7% |
| 03_RandomPos | 98.9% | 98.9% |
| 04_RandomPosOffset | 100.0% | 100.0% |
| 05_ConstSpeed | 98.8% | 98.8% |
| 06_ConstSpeedOffset | 100.0% | 100.0% |
| 07_RandomSpeed | 98.9% | 98.9% |
| 08_RandomSpeedOffset | 100.0% | 100.0% |
| 09_EventualStop | 8.0% | 8.0% |
| 10_Disruptive | 98.9% | 98.9% |
| 11_DataReplay | 98.8% | 98.8% |
| 12_DelayedMessages | 14.9% | 14.9% |
| 13_DoS | 100.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% |
| 16_GridSybil | 98.9% | 98.9% |
| 17_DataReplaySybil | 92.9% | 92.9% |
| 18_DoSRandomSybil | 0.0% | 0.0% |
| 19_DoSDisruptiveSybil | 36.0% | 37.2% |
| genuine senders with >= 3 alarms | 10.7% | 10.7% |

**VeReMi test: false alarms on genuine test messages and senders**

| operating point | genuine messages | genuine senders with >= 1 alarm |
|---|---|---|
| v2x.beacon_rate | 0.0% | 0.0% |
| v2x.field_ranges | 1.0% | 49.2% |
| v2x.pos_speed | 0.9% | 58.0% |
| v2x.pos_heading | 1.0% | 49.9% |
| v2x.speed_change | 1.0% | 75.4% |
| v2x.implied_speed | 1.1% | 6.6% |
| v2x.heading_rate | 1.0% | 55.8% |
| v2x.accel_consistency | 1.0% | 61.2% |
| v2x.overlap | 1.5% | 39.8% |
| v2x.field_ranges@physical | 0.0% | 0.0% |
| v2x.speed_change@physical | 0.0% | 0.0% |
| v2x.implied_speed@physical | 0.0% | 0.0% |
| v2x.heading_rate@physical | 0.0% | 0.3% |
| L2_physical_union | 0.0% | 0.3% |
| L2_union | 1.0% | 54.0% |
| L1_union_at_operating_points | 0.0% | 0.0% |
| L1_and_L2_union | 1.0% | 54.0% |
| combined_L1 | 1.0% | 49.2% |
| combined_L2 | 1.2% | 59.2% |
| combined_L1+L2 | 1.0% | 54.4% |
| combined_all | 1.0% | 54.4% |

Budget 1.0% false alarms on validation normal data. Domain: s3_veremi.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.845 | 72.4% | 0.98% | 86.3% | 1.1% | 99.1% | 97.3% | 96.7% | 85.2% | 99.4% | 94.8% | 1.1% | 97.0% | 68.3% | 1.4% | 99.7% | 99.9% | 99.7% | 61.4% | 20.8% | 70.0% | 13.1% | 0.0 |
| only_v2x.accel_consistency | 0.605 | 34.3% | 1.00% | 1.2% | 0.9% | 0.9% | 0.9% | 19.9% | 11.2% | 90.1% | 77.0% | 0.9% | 75.4% | 48.6% | 0.4% | 25.0% | 96.4% | 85.2% | 19.2% | 7.8% | 0.0% | 0.1% | 0.0 |
| only_v2x.beacon_rate | 0.628 | 32.8% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 99.7% | 99.7% | 99.7% | 22.0% | 0.0% | 0.0% | 0.3% | 0.0 |
| only_v2x.field_ranges | 0.574 | 20.8% | 0.99% | 1.0% | 0.9% | 1.4% | 1.1% | 71.3% | 9.5% | 70.5% | 5.3% | 0.2% | 15.2% | 6.0% | 0.1% | 0.9% | 70.7% | 13.7% | 1.6% | 7.9% | 70.2% | 13.4% | 0.0 |
| only_v2x.heading_rate | 0.439 | 11.4% | 0.98% | 0.9% | 1.1% | 1.1% | 0.7% | 0.2% | 0.2% | 0.0% | 0.2% | 0.1% | 22.1% | 15.1% | 0.4% | 2.0% | 54.9% | 44.6% | 0.2% | 0.7% | 0.0% | 0.0% | 0.0 |
| only_v2x.implied_speed | 0.519 | 36.7% | 1.06% | 0.0% | 1.4% | 99.1% | 86.5% | 0.4% | 0.6% | 0.5% | 0.3% | 0.0% | 91.0% | 49.3% | 1.3% | 25.8% | 99.7% | 95.1% | 27.7% | 3.3% | 0.0% | 0.1% | 0.0 |
| only_v2x.overlap | 0.521 | 4.2% | 1.47% | 1.5% | 0.3% | 0.0% | 0.2% | 0.2% | 0.4% | 0.3% | 0.4% | 6.9% | 7.9% | 27.4% | 3.7% | 1.3% | 0.0% | 6.7% | 2.1% | 25.9% | 0.0% | 11.0% | 0.0 |
| only_v2x.pos_heading | 0.437 | 22.5% | 0.97% | 0.0% | 1.2% | 67.2% | 60.2% | 1.1% | 1.2% | 1.1% | 0.8% | 0.2% | 56.0% | 29.5% | 0.4% | 0.4% | 93.0% | 57.9% | 1.5% | 1.7% | 0.0% | 0.0% | 0.0 |
| only_v2x.pos_speed | 0.737 | 65.3% | 0.92% | 88.2% | 1.1% | 99.1% | 97.0% | 97.4% | 91.2% | 98.0% | 86.0% | 0.9% | 96.2% | 67.6% | 1.2% | 83.7% | 99.7% | 98.5% | 64.8% | 17.0% | 0.0% | 0.3% | 0.0 |
| only_v2x.speed_change | 0.498 | 25.1% | 0.98% | 1.0% | 1.0% | 1.1% | 1.0% | 0.0% | 2.3% | 77.8% | 53.3% | 0.6% | 58.4% | 31.3% | 0.1% | 7.3% | 92.1% | 75.1% | 1.1% | 1.7% | 0.0% | 0.0% | 0.0 |
| all_but_v2x.accel_consistency | 0.846 | 72.1% | 0.98% | 86.4% | 1.3% | 99.1% | 97.4% | 96.6% | 83.9% | 99.1% | 92.1% | 1.1% | 96.8% | 67.4% | 1.4% | 99.7% | 99.9% | 99.7% | 60.6% | 20.0% | 70.0% | 13.4% | 0.0 |
| all_but_v2x.beacon_rate | 0.835 | 69.4% | 0.98% | 86.3% | 1.1% | 99.1% | 97.3% | 96.7% | 85.2% | 99.4% | 94.8% | 1.1% | 97.0% | 68.3% | 1.4% | 73.0% | 99.9% | 98.4% | 60.8% | 20.8% | 70.0% | 13.0% | 0.0 |
| all_but_v2x.field_ranges | 0.767 | 66.8% | 0.98% | 86.4% | 1.3% | 99.1% | 97.4% | 96.1% | 85.6% | 98.9% | 94.9% | 1.1% | 97.0% | 68.4% | 1.4% | 99.7% | 99.7% | 99.7% | 61.5% | 17.4% | 0.0% | 1.5% | 0.0 |
| all_but_v2x.heading_rate | 0.846 | 72.5% | 0.97% | 86.4% | 1.3% | 99.1% | 97.4% | 96.7% | 85.6% | 99.4% | 94.9% | 1.2% | 97.0% | 68.3% | 1.4% | 99.7% | 99.9% | 99.7% | 61.5% | 20.9% | 70.0% | 13.2% | 0.0 |
| all_but_v2x.implied_speed | 0.848 | 72.5% | 1.04% | 86.4% | 1.0% | 99.1% | 97.4% | 96.8% | 85.7% | 99.4% | 94.9% | 1.2% | 97.0% | 68.4% | 1.4% | 99.7% | 99.9% | 99.7% | 61.5% | 20.9% | 70.0% | 13.4% | 0.0 |
| all_but_v2x.overlap | 0.822 | 72.3% | 0.95% | 86.3% | 1.4% | 99.1% | 97.4% | 96.8% | 85.7% | 99.4% | 94.9% | 0.9% | 97.0% | 68.3% | 1.0% | 99.7% | 99.9% | 99.7% | 61.4% | 20.4% | 70.0% | 12.2% | 0.0 |
| all_but_v2x.pos_heading | 0.846 | 72.3% | 0.99% | 86.4% | 1.2% | 99.1% | 94.2% | 96.8% | 85.6% | 99.4% | 94.9% | 1.1% | 96.7% | 68.0% | 1.4% | 99.7% | 99.9% | 99.7% | 61.5% | 20.8% | 70.0% | 13.2% | 0.0 |
| all_but_v2x.pos_speed | 0.796 | 60.9% | 1.00% | 1.2% | 1.3% | 99.1% | 93.0% | 72.9% | 15.4% | 97.2% | 69.8% | 1.1% | 94.4% | 57.5% | 1.4% | 99.7% | 99.9% | 99.7% | 34.8% | 12.1% | 70.0% | 13.2% | 0.0 |
| all_but_v2x.speed_change | 0.847 | 72.5% | 0.99% | 86.4% | 1.3% | 99.1% | 97.4% | 96.8% | 85.6% | 99.4% | 94.8% | 1.2% | 97.0% | 68.4% | 1.5% | 99.7% | 99.9% | 99.7% | 61.5% | 21.0% | 70.0% | 13.4% | 0.0 |

**VeReMi test, harness group ablation on top of L1**

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | noisy_or | 0.695 | 45.1% | 0.99% |
| L2 | logistic | 0.800 | 67.1% | 1.19% |
| L1+L2 | max | 0.845 | 72.4% | 0.98% |

### Tampa (injected on real BSMs) test

**Tampa test: message-level detection per class, each L2 check at the 1% validation budget**

* = attack type held out of calibration and combiner. Physical limits below.

| class | v2x.pos_speed | v2x.pos_heading | v2x.speed_change | v2x.implied_speed | v2x.heading_rate | v2x.accel_consistency | v2x.yaw_consistency | v2x.overlap | v2x.map_road |
|---|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 13.8% | 0.0% | 0.9% | 0.0% | 1.3% | 0.8% | 0.8% | 0.0% | 5.3% |
| 02_ConstPosOffset | 0.0% | 0.8% | 0.5% | 0.1% | 0.8% | 0.5% | 0.7% | 0.0% | 37.5% |
| 03_RandomPos | 99.6% | 39.8% | 0.8% | 99.6% | 0.9% | 0.8% | 0.5% | 0.0% | 47.1% |
| 04_RandomPosOffset | 99.4% | 44.6% | 0.4% | 99.3% | 0.3% | 0.5% | 0.4% | 0.0% | 44.3% |
| 05_ConstSpeed | 68.9% | 1.6% | 0.0% | 0.3% | 0.0% | 0.0% | 1.8% | 0.0% | 14.1% |
| 06_ConstSpeedOffset * | 18.6% | 1.8% | 1.3% | 0.1% | 0.2% | 1.3% | 1.7% | 0.0% | 17.7% |
| 07_RandomSpeed | 41.7% | 1.0% | 96.9% | 0.2% | 0.0% | 97.6% | 0.5% | 0.0% | 7.1% |
| 08_RandomSpeedOffset | 6.9% | 0.6% | 89.8% | 0.2% | 0.1% | 92.0% | 0.4% | 0.0% | 13.0% |
| 09_EventualStop | 0.1% | 0.0% | 0.2% | 0.0% | 0.0% | 0.2% | 0.0% | 0.0% | 2.8% |
| 10_Disruptive | 94.3% | 15.7% | 72.6% | 93.4% | 13.1% | 74.3% | 14.7% | 0.0% | 0.9% |
| 11_DataReplay | 4.5% | 0.1% | 1.9% | 1.1% | 0.9% | 2.0% | 1.1% | 0.0% | 8.2% |
| 12_DelayedMessages * | 4.5% | 0.7% | 1.8% | 1.6% | 0.7% | 1.8% | 1.7% | 0.0% | 7.1% |
| 13_DoS | 0.1% | 0.6% | 2.0% | 0.4% | 0.6% | 1.8% | 2.5% | 0.0% | 0.8% |
| 14_DoSRandom | 99.6% | 82.1% | 98.7% | 99.6% | 0.4% | 98.9% | 5.4% | 0.0% | 45.8% |
| 15_DoSDisruptive | 93.9% | 14.9% | 78.4% | 94.5% | 13.9% | 79.0% | 15.4% | 0.0% | 5.9% |
| 16_GridSybil | 0.4% | 2.8% | 0.9% | 0.3% | 1.5% | 0.8% | 1.1% | 0.0% | 3.3% |
| 17_DataReplaySybil * | 23.7% | 1.2% | 9.3% | 14.3% | 2.2% | 9.3% | 4.6% | 0.0% | 22.1% |
| 18_DoSRandomSybil | 47.2% | 39.5% | 31.6% | 46.7% | 0.0% | 34.9% | 0.2% | 0.0% | 45.3% |
| 19_DoSDisruptiveSybil | 45.0% | 10.7% | 23.5% | 40.7% | 4.7% | 26.5% | 8.7% | 34.0% | 0.5% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 76.9% | 11.9% |

**Tampa test: message-level detection at the physical limits (no fitted threshold)**



| class | v2x.speed_change@physical | v2x.implied_speed@physical | v2x.heading_rate@physical | L2_physical_union |
|---|---|---|---|---|
| 01_ConstPos | 0.0% | 0.0% | 0.0% | 0.0% |
| 02_ConstPosOffset | 0.0% | 0.0% | 0.0% | 0.0% |
| 03_RandomPos | 0.0% | 99.5% | 0.0% | 99.5% |
| 04_RandomPosOffset | 0.0% | 98.9% | 0.0% | 98.9% |
| 05_ConstSpeed | 0.0% | 0.0% | 0.0% | 0.0% |
| 06_ConstSpeedOffset * | 0.1% | 0.0% | 0.0% | 0.1% |
| 07_RandomSpeed | 89.0% | 0.0% | 0.0% | 89.0% |
| 08_RandomSpeedOffset | 67.9% | 0.0% | 0.0% | 67.9% |
| 09_EventualStop | 0.2% | 0.0% | 0.0% | 0.2% |
| 10_Disruptive | 63.9% | 92.6% | 11.2% | 93.1% |
| 11_DataReplay | 0.2% | 0.6% | 0.1% | 0.6% |
| 12_DelayedMessages * | 0.2% | 0.5% | 0.1% | 0.6% |
| 13_DoS | 0.1% | 0.1% | 0.1% | 0.3% |
| 14_DoSRandom | 96.6% | 99.6% | 0.0% | 99.6% |
| 15_DoSDisruptive | 74.9% | 93.7% | 12.0% | 94.3% |
| 16_GridSybil | 0.0% | 0.0% | 0.0% | 0.0% |
| 17_DataReplaySybil * | 2.7% | 7.2% | 0.6% | 7.6% |
| 18_DoSRandomSybil | 12.3% | 45.3% | 0.0% | 45.3% |
| 19_DoSDisruptiveSybil | 8.8% | 37.1% | 1.0% | 37.2% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 0.0% |

**Tampa test: message-level detection, unions and harness combinations**

L2_union = max of the calibrated L2 scores at one 1% budget; L1_union = beacon rate (budget) OR field ranges (physical) [OR freshness (budget) on Tampa]; L1_and_L2_union = L1_union OR L2_union; combined_* = harness combiner (chosen on validation) of the L1 / L2 / all layers.

| class | L2_union | L1_union_at_operating_points | L1_and_L2_union | combined_L1 | combined_L2 | combined_L1+L2 | combined_all |
|---|---|---|---|---|---|---|---|
| 01_ConstPos | 15.0% | 0.6% | 15.5% | 0.5% | 15.0% | 14.8% | 14.8% |
| 02_ConstPosOffset | 37.2% | 1.2% | 37.6% | 1.1% | 37.2% | 37.3% | 37.3% |
| 03_RandomPos | 99.8% | 1.5% | 99.8% | 1.2% | 99.8% | 99.8% | 99.8% |
| 04_RandomPosOffset | 99.7% | 1.7% | 99.7% | 1.5% | 99.7% | 99.7% | 99.7% |
| 05_ConstSpeed | 54.3% | 0.4% | 54.8% | 0.5% | 54.3% | 52.4% | 52.4% |
| 06_ConstSpeedOffset * | 28.7% | 0.7% | 29.4% | 7.0% | 28.7% | 34.4% | 34.4% |
| 07_RandomSpeed | 97.6% | 0.3% | 97.6% | 3.7% | 97.6% | 97.5% | 97.5% |
| 08_RandomSpeedOffset | 90.3% | 2.1% | 90.5% | 5.8% | 90.3% | 89.9% | 89.9% |
| 09_EventualStop | 3.1% | 0.3% | 3.4% | 0.0% | 3.1% | 3.1% | 3.1% |
| 10_Disruptive | 94.4% | 0.8% | 94.5% | 1.3% | 94.4% | 94.3% | 94.3% |
| 11_DataReplay | 11.4% | 0.0% | 11.4% | 0.0% | 11.4% | 11.4% | 11.4% |
| 12_DelayedMessages * | 10.4% | 0.0% | 10.4% | 0.2% | 10.4% | 10.3% | 10.3% |
| 13_DoS | 2.5% | 5.7% | 7.8% | 5.5% | 2.5% | 4.2% | 4.2% |
| 14_DoSRandom | 99.8% | 94.3% | 99.9% | 94.4% | 99.8% | 99.9% | 99.9% |
| 15_DoSDisruptive | 95.2% | 92.8% | 99.4% | 92.8% | 95.2% | 99.4% | 99.4% |
| 16_GridSybil | 5.1% | 0.6% | 5.6% | 0.6% | 5.1% | 4.9% | 4.9% |
| 17_DataReplaySybil * | 39.6% | 1.4% | 40.4% | 3.1% | 39.6% | 39.7% | 39.7% |
| 18_DoSRandomSybil | 71.0% | 1.3% | 71.3% | 4.3% | 71.0% | 71.5% | 71.5% |
| 19_DoSDisruptiveSybil | 64.0% | 1.3% | 64.4% | 1.7% | 64.0% | 64.4% | 64.4% |
| S20_StaleReplay | 78.9% | 100.0% | 100.0% | 100.0% | 78.9% | 100.0% | 100.0% |

**Tampa test: sender-level detection (>= 1 alarm among the attacker's falsified messages / >= 3 alarms) and median delay (s)**

>= 3 alarms in the next table.

| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 02_ConstPosOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 03_RandomPos | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 04_RandomPosOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 05_ConstSpeed | 100.0% / 0.6 s | 100.0% / 0.6 s |
| 06_ConstSpeedOffset * | 100.0% / 0.3 s | 100.0% / 0.3 s |
| 07_RandomSpeed | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 08_RandomSpeedOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 09_EventualStop | 80.0% / 0.0 s | 80.0% / 0.0 s |
| 10_Disruptive | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 11_DataReplay | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 12_DelayedMessages * | 100.0% / 0.6 s | 100.0% / 0.6 s |
| 13_DoS | 90.0% / 4.6 s | 100.0% / 1.7 s |
| 14_DoSRandom | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 15_DoSDisruptive | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 16_GridSybil | 90.0% / 4.6 s | 90.0% / 1.6 s |
| 17_DataReplaySybil * | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 18_DoSRandomSybil | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 19_DoSDisruptiveSybil | 100.0% / 0.6 s | 100.0% / 0.6 s |
| S20_StaleReplay | 100.0% / 0.0 s | 100.0% / 0.0 s |

| class | L2_union >= 3 alarms | L1_and_L2_union >= 3 alarms |
|---|---|---|
| 01_ConstPos | 100.0% | 100.0% |
| 02_ConstPosOffset | 90.0% | 90.0% |
| 03_RandomPos | 100.0% | 100.0% |
| 04_RandomPosOffset | 100.0% | 100.0% |
| 05_ConstSpeed | 100.0% | 100.0% |
| 06_ConstSpeedOffset | 100.0% | 100.0% |
| 07_RandomSpeed | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 100.0% | 100.0% |
| 09_EventualStop | 10.0% | 20.0% |
| 10_Disruptive | 100.0% | 100.0% |
| 11_DataReplay | 90.0% | 90.0% |
| 12_DelayedMessages | 90.0% | 90.0% |
| 13_DoS | 60.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% |
| 16_GridSybil | 90.0% | 90.0% |
| 17_DataReplaySybil | 100.0% | 100.0% |
| 18_DoSRandomSybil | 100.0% | 100.0% |
| 19_DoSDisruptiveSybil | 100.0% | 100.0% |
| S20_StaleReplay | 100.0% | 100.0% |
| genuine senders with >= 3 alarms | 26.7% | 35.6% |

**Tampa test: attacker-bootstrap 95% CI of message detection (L2_union and L1_and_L2_union)**



| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | [5.9%, 37.3%] | [6.5%, 36.0%] |
| 02_ConstPosOffset | [25.3%, 52.8%] | [25.0%, 55.8%] |
| 03_RandomPos | [99.5%, 99.9%] | [99.5%, 99.9%] |
| 04_RandomPosOffset | [99.3%, 99.9%] | [99.3%, 99.9%] |
| 05_ConstSpeed | [29.3%, 74.4%] | [29.8%, 72.8%] |
| 06_ConstSpeedOffset * | [12.1%, 48.8%] | [13.5%, 48.4%] |
| 07_RandomSpeed | [96.8%, 98.2%] | [96.8%, 98.2%] |
| 08_RandomSpeedOffset | [88.0%, 92.7%] | [88.3%, 93.2%] |
| 09_EventualStop | [0.1%, 25.3%] | [0.1%, 20.4%] |
| 10_Disruptive | [92.9%, 95.1%] | [93.2%, 95.1%] |
| 11_DataReplay | [3.0%, 37.2%] | [3.2%, 39.4%] |
| 12_DelayedMessages * | [2.9%, 33.4%] | [2.8%, 34.8%] |
| 13_DoS | [0.8%, 6.4%] | [5.8%, 12.5%] |
| 14_DoSRandom | [99.2%, 100.0%] | [99.7%, 100.0%] |
| 15_DoSDisruptive | [94.0%, 96.2%] | [99.1%, 99.6%] |
| 16_GridSybil | [0.9%, 14.7%] | [1.3%, 16.4%] |
| 17_DataReplaySybil * | [35.2%, 42.1%] | [36.6%, 43.3%] |
| 18_DoSRandomSybil | [67.6%, 72.9%] | [68.2%, 73.4%] |
| 19_DoSDisruptiveSybil | [54.6%, 66.9%] | [56.7%, 67.3%] |
| S20_StaleReplay | [75.4%, 82.1%] | [100.0%, 100.0%] |

**Tampa test: false alarms on genuine test messages and senders**

| operating point | genuine messages | 95% CI (vehicle bootstrap) | genuine senders with >= 1 alarm |
|---|---|---|---|
| v2x.beacon_rate | 0.2% | [0.0%, 0.7%] | 15.6% |
| v2x.freshness | 1.1% | [0.0%, 3.4%] | 11.1% |
| v2x.field_ranges | 0.3% | [0.1%, 0.8%] | 13.3% |
| v2x.pos_speed | 0.2% | [0.1%, 0.5%] | 20.0% |
| v2x.pos_heading | 0.8% | [0.4%, 1.3%] | 40.0% |
| v2x.speed_change | 0.7% | [0.4%, 1.1%] | 33.3% |
| v2x.implied_speed | 0.2% | [0.0%, 0.4%] | 13.3% |
| v2x.heading_rate | 0.9% | [0.3%, 1.6%] | 20.0% |
| v2x.accel_consistency | 0.7% | [0.5%, 1.2%] | 40.0% |
| v2x.yaw_consistency | 0.6% | [0.2%, 1.2%] | 15.6% |
| v2x.overlap | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.map_road | 5.5% | [0.2%, 17.6%] | 8.9% |
| v2x.field_ranges@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.speed_change@physical | 0.0% | [0.0%, 0.1%] | 4.4% |
| v2x.implied_speed@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.heading_rate@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| L2_physical_union | 0.0% | [0.0%, 0.1%] | 4.4% |
| L2_union | 6.3% | [1.1%, 17.9%] | 42.2% |
| L1_union_at_operating_points | 1.3% | [0.2%, 3.9%] | 26.7% |
| L1_and_L2_union | 7.6% | [1.9%, 19.6%] | 53.3% |
| combined_L1 | 0.9% | [0.2%, 2.6%] | 31.1% |
| combined_L2 | 6.3% | [1.0%, 17.4%] | 42.2% |
| combined_L1+L2 | 6.7% | [1.3%, 18.9%] | 42.2% |
| combined_all | 6.7% | [1.3%, 18.3%] | 42.2% |

Budget 1.0% false alarms on validation normal data. Domain: s3_tampa.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | det S20_StaleReplay | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.781 | 53.3% | 6.69% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 10.3% | 4.2% | 99.9% | 99.4% | 4.9% | 39.7% | 71.5% | 64.4% | 100.0% | 0.0 |
| only_v2x.accel_consistency | 0.624 | 29.6% | 0.73% | 0.8% | 0.5% | 0.8% | 0.5% | 0.0% | 1.3% | 97.6% | 92.0% | 0.2% | 74.3% | 2.0% | 1.8% | 1.8% | 98.9% | 79.0% | 0.8% | 9.3% | 34.9% | 26.5% | 0.0% | 0.0 |
| only_v2x.beacon_rate | 0.527 | 16.3% | 0.21% | 0.6% | 0.1% | 0.3% | 0.1% | 0.4% | 0.6% | 0.2% | 0.1% | 0.3% | 0.7% | 0.0% | 0.0% | 5.7% | 94.3% | 92.8% | 0.6% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0 |
| only_v2x.field_ranges | 0.604 | 1.0% | 0.33% | 0.4% | 0.1% | 0.1% | 0.1% | 0.0% | 6.7% | 2.4% | 3.8% | 0.0% | 0.3% | 0.0% | 0.1% | 0.5% | 2.5% | 0.1% | 0.6% | 0.0% | 2.3% | 0.6% | 0.6% | 0.0 |
| only_v2x.freshness | 0.499 | 1.4% | 1.08% | 0.0% | 1.1% | 1.2% | 1.6% | 0.0% | 0.1% | 0.0% | 2.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.1% | 0.1% | 0.0% | 1.4% | 1.2% | 1.3% | 100.0% | 0.0 |
| only_v2x.heading_rate | 0.443 | 2.1% | 0.89% | 1.3% | 0.8% | 0.9% | 0.3% | 0.0% | 0.2% | 0.0% | 0.1% | 0.0% | 13.1% | 0.9% | 0.7% | 0.6% | 0.4% | 13.9% | 1.5% | 2.2% | 0.0% | 4.7% | 0.0% | 0.0 |
| only_v2x.implied_speed | 0.619 | 34.0% | 0.17% | 0.0% | 0.1% | 99.6% | 99.3% | 0.3% | 0.1% | 0.2% | 0.2% | 0.0% | 93.4% | 1.1% | 1.6% | 0.4% | 99.6% | 94.5% | 0.3% | 14.3% | 46.7% | 40.7% | 0.0% | 0.0 |
| only_v2x.map_road | 0.572 | 18.3% | 5.50% | 5.3% | 37.5% | 47.1% | 44.3% | 14.1% | 17.7% | 7.1% | 13.0% | 2.8% | 0.9% | 8.2% | 7.1% | 0.8% | 45.8% | 5.9% | 3.3% | 22.1% | 45.3% | 0.5% | 11.9% | 0.0 |
| only_v2x.overlap | 0.517 | 3.5% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 34.0% | 76.9% | 0.0 |
| only_v2x.pos_heading | 0.546 | 18.0% | 0.80% | 0.0% | 0.8% | 39.8% | 44.6% | 1.6% | 1.8% | 1.0% | 0.6% | 0.0% | 15.7% | 0.1% | 0.7% | 0.6% | 82.1% | 14.9% | 2.8% | 1.2% | 39.5% | 10.7% | 0.0% | 0.0 |
| only_v2x.pos_speed | 0.690 | 39.8% | 0.20% | 13.8% | 0.0% | 99.6% | 99.4% | 68.9% | 18.6% | 41.7% | 6.9% | 0.1% | 94.3% | 4.5% | 4.5% | 0.1% | 99.6% | 93.9% | 0.4% | 23.7% | 47.2% | 45.0% | 0.0% | 0.0 |
| only_v2x.speed_change | 0.611 | 28.9% | 0.69% | 0.9% | 0.5% | 0.8% | 0.4% | 0.0% | 1.3% | 96.9% | 89.8% | 0.2% | 72.6% | 1.9% | 1.8% | 2.0% | 98.7% | 78.4% | 0.9% | 9.3% | 31.6% | 23.5% | 0.0% | 0.0 |
| only_v2x.yaw_consistency | 0.511 | 3.4% | 0.64% | 0.8% | 0.7% | 0.5% | 0.4% | 1.8% | 1.7% | 0.5% | 0.4% | 0.0% | 14.7% | 1.1% | 1.7% | 2.5% | 5.4% | 15.4% | 1.1% | 4.6% | 0.2% | 8.7% | 0.0% | 0.0 |
| all_but_v2x.accel_consistency | 0.781 | 53.1% | 6.66% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 96.5% | 87.1% | 3.1% | 94.3% | 11.3% | 10.3% | 4.1% | 99.9% | 99.4% | 4.9% | 39.7% | 71.5% | 64.4% | 100.0% | 0.0 |
| all_but_v2x.beacon_rate | 0.765 | 52.9% | 6.66% | 14.7% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.3% | 10.3% | 2.5% | 99.8% | 95.2% | 4.9% | 39.7% | 71.5% | 64.4% | 100.0% | 0.0 |
| all_but_v2x.field_ranges | 0.776 | 53.1% | 6.66% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 28.4% | 97.5% | 89.4% | 3.1% | 94.3% | 11.4% | 10.3% | 4.1% | 99.9% | 99.4% | 4.9% | 39.7% | 71.1% | 64.2% | 100.0% | 0.0 |
| all_but_v2x.freshness | 0.778 | 53.0% | 6.28% | 14.8% | 37.2% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.7% | 3.1% | 94.3% | 11.4% | 10.3% | 4.2% | 99.9% | 99.4% | 4.9% | 39.2% | 71.3% | 64.1% | 78.9% | 0.0 |
| all_but_v2x.heading_rate | 0.782 | 53.2% | 6.48% | 14.6% | 37.1% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.1% | 10.2% | 4.0% | 99.9% | 99.4% | 4.9% | 39.4% | 71.5% | 64.4% | 100.0% | 0.0 |
| all_but_v2x.implied_speed | 0.781 | 53.2% | 6.65% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 10.3% | 4.1% | 99.9% | 99.4% | 4.9% | 37.8% | 71.5% | 64.4% | 100.0% | 0.0 |
| all_but_v2x.map_road | 0.756 | 46.6% | 1.26% | 9.6% | 1.3% | 99.6% | 99.5% | 39.4% | 17.8% | 97.2% | 88.3% | 0.2% | 94.3% | 3.4% | 3.4% | 3.4% | 99.8% | 99.3% | 1.7% | 21.3% | 48.3% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.overlap | 0.770 | 51.7% | 6.69% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 10.3% | 4.2% | 99.9% | 99.4% | 4.9% | 39.7% | 71.5% | 45.5% | 100.0% | 0.0 |
| all_but_v2x.pos_heading | 0.781 | 53.2% | 6.65% | 14.8% | 37.3% | 99.8% | 99.7% | 52.3% | 34.3% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 10.3% | 4.1% | 99.9% | 99.4% | 4.5% | 39.7% | 71.4% | 64.3% | 100.0% | 0.0 |
| all_but_v2x.pos_speed | 0.763 | 50.9% | 6.69% | 6.3% | 37.3% | 99.8% | 99.6% | 14.7% | 25.2% | 95.7% | 87.3% | 3.1% | 93.8% | 9.4% | 8.9% | 4.2% | 99.9% | 99.3% | 4.9% | 33.2% | 71.3% | 61.5% | 100.0% | 0.0 |
| all_but_v2x.speed_change | 0.781 | 53.3% | 6.67% | 14.8% | 37.3% | 99.8% | 99.7% | 52.4% | 34.4% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 10.3% | 4.2% | 99.9% | 99.4% | 4.9% | 39.7% | 71.5% | 64.4% | 100.0% | 0.0 |
| all_but_v2x.yaw_consistency | 0.782 | 53.2% | 6.63% | 14.7% | 37.3% | 99.8% | 99.7% | 52.2% | 34.1% | 97.5% | 89.9% | 3.1% | 94.3% | 11.4% | 9.9% | 3.9% | 99.9% | 99.4% | 4.8% | 39.7% | 71.5% | 64.4% | 100.0% | 0.0 |

**Tampa test, harness group ablation on top of L1**

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | noisy_or | 0.629 | 18.4% | 0.92% |
| L2 | max | 0.754 | 52.6% | 6.35% |
| L1+L2 | max | 0.781 | 53.3% | 6.69% |


The harness column 'median delay' is computed per group (time block / vehicle) and is not meaningful here; per-attacker delays are the 'median delay' values in the sender-level tables.

## Acceptance

| check | result | value |
|---|---|---|
| 3a VeReMi: every check and union <= 1.5% false alarms on genuine test messages | MET | max 1.5% (v2x.overlap) |
| 3b Tampa: every check and union <= 2% false alarms on genuine test messages | NOT MET | exceeded by L1_and_L2_union 7.6%, combined_L1+L2 6.7%, combined_all 6.7%, L2_union 6.3%, combined_L2 6.3%, v2x.map_road 5.5% |
| 3c physical limits (speed_change, implied_speed, heading_rate, field_ranges) <= 0.1% on genuine val and test | MET | VeReMi max 0.0026%, Tampa max 0.0225% |

Pre-registered expectations (stated before the run, not used for tuning):

| expectation | outcome | value |
|---|---|---|
| P1 VeReMi: classes 3, 4, 7, 10, 14, 15, 18, 19 >= 85% (L2 union) | NOT as expected | 3: 99.1%, 4: 97.4%, 7: 98.9%, 10: 97.0%, 14: 99.7%, 15: 98.4%, 18: 0.0%, 19: 1.4% |
| P2 VeReMi: classes 1 and 5 >= 80% | as expected | 1: 86.4%, 5: 96.1% |
| P3 VeReMi: classes 6 and 8 between 20% and 80%; Tampa < 50% | NOT as expected | VeReMi 6: 85.6%, 8: 94.9%; Tampa 6: 28.7%, 8: 90.3% |
| P4 VeReMi: classes 2, 11, 12, 13, 16, 17 each < 10% (consecutive checks blind) | NOT as expected | 2: 1.3%, 11: 68.4%, 12: 1.4%, 13: 73.8%, 16: 60.9%, 17: 17.4% |
| P4 Tampa: same classes each < 10% (map may add on class 2) | NOT as expected | 2: 37.2%, 11: 11.4%, 12: 10.4%, 13: 2.5%, 16: 5.1%, 17: 39.6% |
| P5 class 9 EventualStop message level < 10% | as expected | VeReMi 1.1%, Tampa 3.1% |
| P6 union false alarms on genuine test messages <= 1.5% (VeReMi), <= 2% (Tampa) | NOT as expected | VeReMi 1.0%, Tampa 6.3% |

Acceptance 1 (nine Layers, unit tests, run_tests 116 passed) and 2 (no fitted threshold on test or attack data, limits cited, OSM recorded): MET. 3: NOT MET on Tampa (see table); VeReMi and the physical limits are MET. 4: MET. Overall S3: PARTIAL. The only criterion missed is the Tampa false-alarm bound, caused by the map check (below).

## What L2 catches and what it does not (plain reading)

- **Caught (VeReMi / Tampa message level)**: RandomPos 3 (99.1% / 99.8%), RandomPosOffset 4 (97.4% / 99.7%), RandomSpeed 7 (98.9% / 97.6%), RandomSpeedOffset 8 (94.9% / 90.3%), Disruptive 10 (97.0% / 94.4%), DoSRandom 14 (99.7% / 99.8%), DoSDisruptive 15 (98.4% / 95.2%). Random content jumps between consecutive beacons, so displacement vs speed x dt, implied speed and speed change expose it. The physical limits alone (no fitted threshold) already catch 3 RandomPos and 14 / 15 / 10 via `implied_speed`, and 7 / 14 partly via `speed_change` (tables above).

- **Constant speed / constant position**: ConstSpeed 5 96.1% / 54.3%, ConstSpeedOffset 6 85.6% / 28.7%, ConstPos 1 86.4% / 15.0%. The check is the same (the claimed speed does not produce the observed displacement) but it depends on dt and on position noise: VeReMi has dt = 1 s and noise sigma ~4 m per axis, so a 5-30 m/s error is large; Tampa has dt = 0.1 s and a GPS-like noise, so the same speed error is a metre or less and mostly hidden. Per attacker the picture is much better than per message: at least 3 alarms for most attackers (table above).

- **Not caught**: ConstPosOffset 2 (1.3% / 37.2%; on Tampa the map check adds a third, with the false alarms below), EventualStop 9 (1.1% / 3.1%: only the stopping transition is implausible; sender level on VeReMi 85.1% for >= 1 alarm but 8.0% for >= 3), DelayedMessages 12 (1.4% / 10.4%: a 3 s old state is a consistent trajectory), Tampa DataReplay 11 (11.4%) and GridSybil 16 (5.1%), VeReMi Sybil with a new pseudonym per message 18 (0.0%) and 19 (1.4%).

- **Why VeReMi 18 / 19 are blind**: a fresh pseudonym per message means every track has one message, so there is no consecutive pair to test (a receiver cannot link the pseudonyms). Only `overlap` and `map_road` need no history; overlap sees a part of 19 (11.0% of messages) because the random disruptive content lands on other vehicles. L1 field ranges at its budget point (a quantile of genuine speed, not a physical limit) is what catches 18 in the combination.

- **VeReMi classes 11, 13, 16 are detected although the expectation was that they are not** (validation rows, `results/WP5/s3_diag.json`): DataReplay 11 replays states with position jumps (median displacement 26.8 m vs speed x dt 11.4 m); DoS 13 repeats the same state at dt = 0.25 s (66.4% of consecutive pairs have zero displacement while the speed says 3.3 m); GridSybil 16 ghosts move 10.9 m per beacon while claiming 0.9 m (speed x dt). So this is a property of how VeReMi implements these attacks, not evidence that L2 detects replay or Sybil in general. The injected Tampa versions (consistent replay, constant-velocity DoS, grid ghosts at the true speed) are, as predicted, mostly invisible to these checks.

- **Overlap**: on VeReMi it fires on 27.4% of DataReplay and 25.9% of DataReplaySybil messages (replayed positions land on live vehicles) and on 2.1% of GridSybil (ghosts 15 m / 3.5 m away do not overlap a 4.5 x 1.8 m footprint, as predicted). On Tampa it has 0.0% false alarms and fires only on 19 (34.0%). The 76.9% on S20 is an artefact of how S20 is built (every stale message is its own track, so 0.1 s neighbours of the same victim 'overlap' each other); it is not a detection result and is not credited to L2.

- **Map (Tampa)**: catches 37.5% of ConstPosOffset 2 (position shifted 100-300 m, often off the road), 47.1% of RandomPos 3, but its **false alarms do not transfer** from validation to test: 5.5% on genuine test messages (95% CI 0.2% to 17.6%) against 1% on validation. Post-hoc diagnosis (`s3_diag.json`): the validation q99 distance is 10.0 m (maximum 12.6 m) but 4 of 45 test vehicles exceed it and two of them (RSUs thea24 and thea1, median distance about 27 m from any mapped drivable way) produce 91% of the alarms. Likely causes (not verified): roads or lots missing from the OSM extract (service / private roads, a parking area, a construction detour) or a position offset of those vehicles. The wide vehicle-bootstrap interval shows how little validation (45 vehicles, a few RSUs) says about unseen places. The same lesson as the GPS work package: a map check calibrated on a few drives does not transfer to places it has not seen.

- **False alarms in numbers**: VeReMi union 1.0% of genuine messages, but 54.0% of genuine senders have at least one alarm (10.7% have >= 3): a 1% message budget over ~110 messages per sender is large per sender, as in S2; a sender-level rule needs >= k alarms. Tampa: the union of the eight non-map L2 checks has 1.0% false alarms on genuine test messages (validation 1.0%), so the budget does transfer for the checks that do not depend on place; 40.0% of the test vehicles raise at least one alarm.

## Ablation on top of L1 (harness)
Each layer alone, all layers, and all-but-one are in the harness tables above (`only_*`, `all`, `all_but_*`); the group rows 'L1 / L2 / L1+L2' are in the last table of each dataset. VeReMi: L1 AUC 0.695 / detection 45.1%, L2 0.800 / 67.1%, L1+L2 0.845 / 72.4% (false alarms 0.98%). Tampa: L1 0.629 / 18.4%, L2 0.754 / 52.6%, L1+L2 0.781 / 53.3% (false alarms 6.69%, driven by the map layer). On VeReMi `pos_speed` is the layer whose removal costs the most (`all_but_v2x.pos_speed`), then `field_ranges` and `beacon_rate` (classes 18 and 13-15); on Tampa `pos_speed` and `map_road`. L1 and L2 are complementary: L1 keeps the rate attacks (13 on Tampa, 18 on VeReMi) that L2 misses, L2 adds all the position / speed falsification.

## Problems, surprises, open questions
- **Tampa ids are per RSU, not per vehicle (new finding, affects S1).** The same BSM (same msgCnt, time, position, speed, heading) appears with a different `coreData_id` at each RSU that heard it (every id occurs at exactly one RSU: 226 ids, 38 RSUs). So the '226 vehicles' of S1 are (vehicle, RSU) sessions; one physical vehicle can sit in train, validation and test under different ids. Consequences: the S1 vehicle split can leak, validation-calibrated thresholds see copies of test trajectories (test false alarms are slightly optimistic), replay pools can contain copies of the attacker. S1 numbers are unchanged and S1 was not redone (outside S3); decision for the supervisor: re-split Tampa by (time block, RSU group) or by trajectory identity, or accept and state the limit.
- **Deviation from the written design (decided on validation data before any test run, documented in the notes):** the overlap check compares only tracks heard by the same receiver. Without it 30% of genuine Tampa validation messages 'overlap' with their own copy under another id.
- **Map check fails the Tampa false-alarm bound** (above). It was not retuned. Options for the supervisor: report the map layer as validated on validation only and keep it out of the Tampa union; calibrate it per place with more vehicles; or wait for a second Tampa day. The non-map L2 union holds the budget (1.0%).
- **Pre-registered expectations missed** (table above): P1 for classes 18 and 19 (pseudonym per message, no history), P3 (the offset speed classes are detected more than predicted), P4 (VeReMi's own implementation of replay, DoS and GridSybil is inconsistent in itself). Reported, not tuned.
- **S20 StaleReplay overlap** (76.9%) is a construction artefact (see above). the L2 kinematic checks on S20 are 0%, as expected: a verbatim old message is kinematically consistent; only freshness (L1) sees it.
- **Per-sender false alarms**: at a 1% message budget 54.0% of the genuine VeReMi senders raise at least one alarm; per-sender decisions need a count rule (>= 3 alarms: 10.7% of genuine senders) or the L3 tracker. The `delay` numbers are for the first alarm, i.e. optimistic about how fast a *reliable* sender-level decision is.
- VeReMi test used once (final run), Tampa test used once. Tampa results are noisy (10 attackers per type): intervals in the tables.
- Overpass first returned HTTP 406 (no User-Agent) and a busy-server timeout; the retry with a User-Agent succeeded. Download size 1.4 MB, disk free unchanged (~42 GB).

## Proposed next step
S4 (L3): per-sender Kalman tracker trained on normal motion with innovation tests. It should (a) turn the per-message alarms of L2 into a better sender-level decision, (b) see slow drifts that the consecutive checks cannot (ConstPosOffset, Delayed, consistent replay). Before S4, the supervisor should decide on the Tampa id issue (re-split) and on the map layer. S3b (acceptance range, sudden appearance) waits for receiver positions (D25 / D13).
