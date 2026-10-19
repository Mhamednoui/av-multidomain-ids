# WP5 S2: L1 message checks (beacon rate, freshness, field ranges, sudden appearance)

Date: 2026-10-19    Worker: sonnet (medium)

## Goal of the step
L1 message checks as v3 Layers for V2X: beacon rate per sender, timestamp freshness, field ranges (cited physical limits), sudden appearance. Evaluate per attack class on VeReMi (all 19 classes) and on the injected Tampa types, false alarms on genuine test senders, harness ablation.

## Acceptance rule (notes/WP5_v2x.md, section 'S2 L1 message checks: acceptance rule', written before any S2 result)
1 four Layers + unit tests + run_tests; 2 no threshold fitted on test or attack data, physical limits cited; 3 false alarms at each operating point <= 1.5x budget (VeReMi), <= 2% (Tampa), physical ranges <= 0.1% on genuine val and test; 4 per-class tables for the 19 classes and Tampa types, genuine-sender false alarms, ablation, bootstrap CIs. Plus pre-registered expectations E1-E4 (below). Held-out attack types 6, 12, 17 were removed from the validation set the combiner sees (marked * in the tables).

## What was done
- `v2x/l1.py`: `BeaconRate`, `Freshness`, `FieldRanges`, `SuddenAppearance` (domain v2x, layer L1, kind rule, causal per track; limits and sources in the docstring and in `results/WP5/s2_summary.json`).
- `v2x/adapters.py`: `load_tampa(with_age=True)` adds `age_s` = RSU log time - generation time (default output unchanged).
- `tools/WP5_S2_l1.py` (evaluation, one run on test), `tools/WP5_S2_report.py` (this file), `tests/v2x/test_l1.py` (11 tests).
- Calibration on validation genuine messages only (VeReMi val 161426 genuine messages; Tampa val 4491), 1% budget, tie-safe (`common/`). Tampa evaluation set = all genuine test messages + the falsified messages of the 19 injected scenarios (10 attackers per type) + a supplemental attack S20.
- Supplemental S20 StaleReplay (not in the 19, Tampa only): 10 attackers rebroadcast 100 genuine messages of other vehicles each, verbatim with the original timestamp, delivered 10-60 s late. Added because the 19 injected types stamp the current time (as a real attacker would), so freshness cannot see them by construction.

### Limits and where they come from

| quantity | value | source |
|---|---|---|
| max beacon rate | 10 Hz (+5% tolerance for the physical alarm) | SAE J2945/1 BSM 10 Hz; ETSI EN 302 637-2 T_GenCam_Min 100 ms |
| timestamp resolution | 1 ms | ETSI generationDeltaTime, SAE J2735 DSecond |
| max speed | 70 m/s | 250 km/h electronic limit of road cars (VDA); encodings allow 163.8 m/s |
| max acceleration | 12.75 m/s^2 (1.3 g) | tyre friction (Wong; Rajamani); encodings +-16 (ETSI) / +-20 (J2735) m/s^2 |
| yaw rate | v / 5 m for v >= 3 m/s, else 5.72 rad/s (J2735 range) | Ackermann minimum radius |
| entry distance (sudden appearance) | 300 m | design value; DSRC range 300-1000 m (Kenney, Proc. IEEE 2011) |
| future tolerance (freshness) | 1 s | 1 s resolution of the Tampa RSU log |

Data-driven thresholds (validation genuine, 1% budget), as raw values: VeReMi rate 1.20 Hz, ranges ratio 0.35; Tampa rate 20.4 Hz, freshness 3.05 s, ranges ratio 0.49.

### What is and is not evaluated

- VeReMi: beacon rate and field ranges. Freshness NOT evaluable (the combined CSV has only the send time, no receive time, and the file order is not arrival order). Sudden appearance NOT evaluable (no receiver id / position).
- Tampa: beacon rate, freshness, field ranges. Sudden appearance NOT evaluable (RSU positions are not in the public sample).
- **Sudden appearance: implemented and unit-tested on synthetic data (`tests/v2x/test_l1.py::test_sudden_appearance_synthetic`), NOT evaluated on real data.** No receiver positions were invented.
- The 'combined' column is the harness combination (noisy-or chosen on validation) of the evaluable layers at the 1% budget. The 'L1 union' column is the rule-style operating point: beacon rate (budget) OR field ranges (physical limit) OR freshness (budget, Tampa).

## Results (generated from results/WP5/s2_*.json; full tables in results/WP5/s2_tables.md)

**VeReMi test, message-level detection per class (each check at its operating point)**

Operating points: rate and combined at the 1% validation budget; field_ranges both at the 1% budget and at the physical limit (raw >= 1); union = rate (budget) OR ranges (physical). * = attack type held out from any fitted component.

| class | v2x.beacon_rate | v2x.field_ranges | v2x.field_ranges@physical | L1_union_at_operating_points | combined |
|---|---|---|---|---|---|
| 01_ConstPos | 0.0% | 1.0% | 0.0% | 0.0% | 1.0% |
| 02_ConstPosOffset | 0.0% | 0.9% | 0.0% | 0.0% | 0.9% |
| 03_RandomPos | 0.0% | 1.4% | 0.0% | 0.0% | 1.4% |
| 04_RandomPosOffset | 0.0% | 1.1% | 0.0% | 0.0% | 1.1% |
| 05_ConstSpeed | 0.0% | 71.3% | 0.0% | 0.0% | 71.3% |
| 06_ConstSpeedOffset * | 0.0% | 9.5% | 0.0% | 0.0% | 9.5% |
| 07_RandomSpeed | 0.0% | 70.5% | 0.0% | 0.0% | 70.5% |
| 08_RandomSpeedOffset | 0.0% | 5.3% | 0.0% | 0.0% | 5.3% |
| 09_EventualStop | 0.0% | 0.2% | 0.0% | 0.0% | 0.2% |
| 10_Disruptive | 0.0% | 15.2% | 0.0% | 0.0% | 15.2% |
| 11_DataReplay | 0.0% | 6.0% | 0.0% | 0.0% | 6.0% |
| 12_DelayedMessages * | 0.0% | 0.1% | 0.0% | 0.0% | 0.1% |
| 13_DoS | 99.7% | 0.9% | 0.0% | 99.7% | 99.7% |
| 14_DoSRandom | 99.7% | 70.7% | 0.0% | 99.7% | 99.9% |
| 15_DoSDisruptive | 99.7% | 13.7% | 0.0% | 99.7% | 99.7% |
| 16_GridSybil | 22.0% | 1.6% | 0.0% | 22.0% | 23.5% |
| 17_DataReplaySybil * | 0.0% | 7.9% | 0.0% | 0.0% | 7.9% |
| 18_DoSRandomSybil | 0.0% | 70.2% | 0.0% | 0.0% | 70.2% |
| 19_DoSDisruptiveSybil | 0.3% | 13.4% | 0.0% | 0.3% | 13.7% |

**VeReMi test, sender-level detection (at least one alarm among the attacker's falsified messages) and median delay (s) of the union**



| class | L1_union_at_operating_points | combined |
|---|---|---|
| 01_ConstPos | 0.0% / - s | 50.6% / 93.0 s |
| 02_ConstPosOffset | 0.0% / - s | 44.4% / 90.5 s |
| 03_RandomPos | 0.0% / - s | 61.1% / 98.0 s |
| 04_RandomPosOffset | 0.0% / - s | 48.3% / 79.0 s |
| 05_ConstSpeed | 0.0% / - s | 87.2% / 0.0 s |
| 06_ConstSpeedOffset * | 0.0% / - s | 58.8% / 70.0 s |
| 07_RandomSpeed | 0.0% / - s | 100.0% / 0.0 s |
| 08_RandomSpeedOffset | 0.0% / - s | 90.7% / 17.5 s |
| 09_EventualStop | 0.0% / - s | 11.5% / 13.0 s |
| 10_Disruptive | 0.0% / - s | 88.8% / 15.0 s |
| 11_DataReplay | 0.0% / - s | 75.9% / 27.0 s |
| 12_DelayedMessages * | 0.0% / - s | 3.4% / 74.0 s |
| 13_DoS | 100.0% / 0.4 s | 100.0% / 0.4 s |
| 14_DoSRandom | 100.0% / 0.5 s | 100.0% / 0.0 s |
| 15_DoSDisruptive | 100.0% / 0.5 s | 100.0% / 0.5 s |
| 16_GridSybil | 82.8% / 6.0 s | 97.7% / 7.5 s |
| 17_DataReplaySybil * | 0.0% / - s | 78.8% / 20.0 s |
| 18_DoSRandomSybil | 0.0% / - s | 100.0% / 0.0 s |
| 19_DoSDisruptiveSybil | 4.7% / 0.5 s | 88.4% / 12.5 s |

**VeReMi test, false alarms on genuine messages and genuine senders**

| operating point | genuine messages | genuine senders with >= 1 alarm |
|---|---|---|
| v2x.beacon_rate | 0.0% | 0.0% |
| v2x.field_ranges | 1.0% | 49.2% |
| combined | 1.0% | 49.2% |
| v2x.beacon_rate@physical | 0.0% | 0.0% |
| v2x.field_ranges@physical | 0.0% | 0.0% |
| L1_union_at_operating_points | 0.0% | 0.0% |

Budget 1.0% false alarms on validation normal data. Domain: s2_veremi.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.695 | 45.1% | 0.99% | 1.0% | 0.9% | 1.4% | 1.1% | 71.3% | 9.5% | 70.5% | 5.3% | 0.2% | 15.2% | 6.0% | 0.1% | 99.7% | 99.9% | 99.7% | 23.5% | 7.9% | 70.2% | 13.7% | 0.0 |
| only_v2x.beacon_rate | 0.628 | 32.8% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 99.7% | 99.7% | 99.7% | 22.0% | 0.0% | 0.0% | 0.3% | 0.0 |
| only_v2x.field_ranges | 0.574 | 20.8% | 0.99% | 1.0% | 0.9% | 1.4% | 1.1% | 71.3% | 9.5% | 70.5% | 5.3% | 0.2% | 15.2% | 6.0% | 0.1% | 0.9% | 70.7% | 13.7% | 1.6% | 7.9% | 70.2% | 13.4% | 0.0 |

**Tampa (injected) test, message-level detection per type**

10 attackers per type: see s2_summary.json for attacker-bootstrap 95% CIs. S20 = supplemental stale replay (not in the 19).

| class | v2x.beacon_rate | v2x.freshness | v2x.field_ranges | v2x.field_ranges@physical | L1_union_at_operating_points | combined |
|---|---|---|---|---|---|---|
| 01_ConstPos | 0.6% | 0.0% | 0.4% | 0.0% | 0.6% | 0.5% |
| 02_ConstPosOffset | 0.1% | 1.1% | 0.1% | 0.0% | 1.2% | 1.1% |
| 03_RandomPos | 0.3% | 1.2% | 0.1% | 0.0% | 1.5% | 1.2% |
| 04_RandomPosOffset | 0.1% | 1.6% | 0.1% | 0.0% | 1.7% | 1.5% |
| 05_ConstSpeed | 0.4% | 0.0% | 0.0% | 0.0% | 0.4% | 0.5% |
| 06_ConstSpeedOffset * | 0.6% | 0.1% | 6.7% | 0.0% | 0.7% | 7.0% |
| 07_RandomSpeed | 0.2% | 0.0% | 2.4% | 0.0% | 0.3% | 3.7% |
| 08_RandomSpeedOffset | 0.1% | 2.0% | 3.8% | 0.0% | 2.1% | 5.8% |
| 09_EventualStop | 0.3% | 0.0% | 0.0% | 0.0% | 0.3% | 0.0% |
| 10_Disruptive | 0.7% | 0.1% | 0.3% | 0.0% | 0.8% | 1.3% |
| 11_DataReplay | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 12_DelayedMessages * | 0.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.2% |
| 13_DoS | 5.7% | 0.0% | 0.5% | 0.0% | 5.7% | 5.5% |
| 14_DoSRandom | 94.3% | 0.1% | 2.5% | 0.0% | 94.3% | 94.4% |
| 15_DoSDisruptive | 92.8% | 0.1% | 0.1% | 0.0% | 92.8% | 92.8% |
| 16_GridSybil | 0.6% | 0.0% | 0.6% | 0.0% | 0.6% | 0.6% |
| 17_DataReplaySybil * | 0.0% | 1.4% | 0.0% | 0.0% | 1.4% | 3.1% |
| 18_DoSRandomSybil | 0.1% | 1.2% | 2.3% | 0.0% | 1.3% | 4.3% |
| 19_DoSDisruptiveSybil | 0.0% | 1.3% | 0.6% | 0.0% | 1.3% | 1.7% |
| S20_StaleReplay | 0.0% | 100.0% | 0.6% | 0.0% | 100.0% | 100.0% |

**Tampa test, attacker-bootstrap 95% CI of message detection (combined and union)**



| class | L1_union_at_operating_points | combined |
|---|---|---|
| 01_ConstPos | [0.1%, 1.7%] | [0.0%, 1.4%] |
| 02_ConstPosOffset | [0.0%, 5.6%] | [0.1%, 4.7%] |
| 03_RandomPos | [0.0%, 6.4%] | [0.1%, 5.2%] |
| 04_RandomPosOffset | [0.1%, 6.7%] | [0.1%, 5.7%] |
| 05_ConstSpeed | [0.0%, 1.3%] | [0.2%, 0.9%] |
| 06_ConstSpeedOffset * | [0.1%, 1.6%] | [0.2%, 19.5%] |
| 07_RandomSpeed | [0.0%, 1.3%] | [2.0%, 8.8%] |
| 08_RandomSpeedOffset | [0.0%, 8.3%] | [0.9%, 18.7%] |
| 09_EventualStop | [0.0%, 2.2%] | [0.0%, 0.0%] |
| 10_Disruptive | [0.1%, 1.9%] | [0.2%, 2.6%] |
| 11_DataReplay | [0.0%, 0.1%] | [0.0%, 0.1%] |
| 12_DelayedMessages * | [0.0%, 0.1%] | [0.1%, 0.3%] |
| 13_DoS | [4.7%, 7.7%] | [2.8%, 14.9%] |
| 14_DoSRandom | [91.5%, 95.5%] | [91.8%, 95.6%] |
| 15_DoSDisruptive | [90.6%, 95.1%] | [90.6%, 95.1%] |
| 16_GridSybil | [0.0%, 1.8%] | [0.1%, 1.6%] |
| 17_DataReplaySybil * | [0.0%, 5.2%] | [0.0%, 9.1%] |
| 18_DoSRandomSybil | [0.0%, 5.3%] | [1.8%, 9.2%] |
| 19_DoSDisruptiveSybil | [0.0%, 6.7%] | [0.5%, 5.4%] |
| S20_StaleReplay | [100.0%, 100.0%] | [100.0%, 100.0%] |

**Tampa test, false alarms on genuine messages and vehicles**

| operating point | genuine messages | 95% CI (vehicle bootstrap) | genuine vehicles with >= 1 alarm |
|---|---|---|---|
| v2x.beacon_rate | 0.2% | [0.0%, 0.7%] | 15.6% |
| v2x.freshness | 1.1% | [0.0%, 3.4%] | 11.1% |
| v2x.field_ranges | 0.3% | [0.1%, 0.8%] | 13.3% |
| combined | 0.9% | [0.2%, 2.6%] | 31.1% |
| v2x.field_ranges@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.beacon_rate@physical_standard | 1.5% | [0.8%, 2.7%] | 35.6% |
| L1_union_at_operating_points | 1.3% | [0.2%, 3.9%] | 26.7% |

Budget 1.0% false alarms on validation normal data. Domain: s2_tampa.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | det S20_StaleReplay | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.629 | 18.4% | 0.92% | 0.5% | 1.1% | 1.2% | 1.5% | 0.5% | 7.0% | 3.7% | 5.8% | 0.0% | 1.3% | 0.0% | 0.2% | 5.5% | 94.4% | 92.8% | 0.6% | 3.1% | 4.3% | 1.7% | 100.0% | 0.0 |
| only_v2x.beacon_rate | 0.527 | 16.3% | 0.21% | 0.6% | 0.1% | 0.3% | 0.1% | 0.4% | 0.6% | 0.2% | 0.1% | 0.3% | 0.7% | 0.0% | 0.0% | 5.7% | 94.3% | 92.8% | 0.6% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0 |
| only_v2x.field_ranges | 0.604 | 1.0% | 0.33% | 0.4% | 0.1% | 0.1% | 0.1% | 0.0% | 6.7% | 2.4% | 3.8% | 0.0% | 0.3% | 0.0% | 0.1% | 0.5% | 2.5% | 0.1% | 0.6% | 0.0% | 2.3% | 0.6% | 0.6% | 0.0 |
| only_v2x.freshness | 0.499 | 1.4% | 1.08% | 0.0% | 1.1% | 1.2% | 1.6% | 0.0% | 0.1% | 0.0% | 2.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.1% | 0.1% | 0.0% | 1.4% | 1.2% | 1.3% | 100.0% | 0.0 |
| all_but_v2x.beacon_rate | 0.578 | 1.6% | 0.96% | 0.0% | 1.1% | 1.2% | 1.6% | 0.0% | 0.2% | 1.0% | 2.3% | 0.0% | 0.2% | 0.0% | 0.0% | 0.0% | 0.4% | 0.1% | 0.0% | 1.6% | 2.4% | 1.6% | 100.0% | 0.0 |
| all_but_v2x.field_ranges | 0.553 | 17.7% | 0.95% | 0.1% | 1.1% | 1.2% | 1.6% | 0.2% | 0.2% | 0.1% | 2.0% | 0.0% | 0.2% | 0.1% | 0.1% | 6.8% | 94.3% | 92.9% | 0.2% | 1.4% | 1.3% | 1.3% | 100.0% | 0.0 |
| all_but_v2x.freshness | 0.590 | 16.6% | 0.23% | 0.6% | 0.1% | 0.3% | 0.1% | 0.9% | 1.7% | 0.3% | 0.4% | 0.3% | 1.0% | 0.0% | 0.0% | 7.9% | 94.3% | 92.8% | 0.6% | 0.2% | 0.2% | 0.1% | 0.0% | 0.0 |


The harness column 'median delay' is computed per group (time block / vehicle) and is not meaningful here; per-attacker delays are in the sender-level table.

## Acceptance

| check | result | value |
|---|---|---|
| 3a VeReMi false alarms on genuine test messages <= 1.5% at every operating point | MET | max 1.0% |
| 3b Tampa false alarms on genuine test messages <= 2% at every budget / physical / union operating point | MET | max 1.3% |
| 3c physical field_ranges false alarms <= 0.1% on genuine val and test (both datasets) | MET | max 0.0% |

Pre-registered expectations (stated before the run, not used for tuning):

| expectation | outcome | value |
|---|---|---|
| E1 rate layer detects >= 90% of messages of classes 13, 14, 15 on VeReMi test | as expected | 13: 99.7%, 14: 99.7%, 15: 99.7% |
| E1b same on the Tampa injected types 13, 14, 15 (x2, x4, x4) | NOT as expected | 13: 5.7%, 14: 94.3%, 15: 92.8% |
| E2 field_ranges at the physical limit detects < 5% of every class (both datasets) | as expected | max 0.0% |
| E3 freshness detects only S20 (every other Tampa type < 5%; S20 >= 90%) | as expected | other max 2.0%, S20 100.0% |
| E4 L1 union detects < 30% of classes 1-12 and 17 (VeReMi and Tampa) | as expected | VeReMi max 0.0%, Tampa max 2.1% |

Acceptance 1 (layers, unit tests) and 2 (no fitted threshold on test / attack data, limits cited): MET. 3: MET. 4: MET. Overall S2: MET.

## What L1 does and does not do (plain reading)
- L1 catches rate-type attacks: DoS / DoSRandom / DoSDisruptive on VeReMi (99.7%, 99.7%, 99.7% of messages; every attacker detected within about half a second) and the x4 types on Tampa. It misses the x2 DoS on Tampa (5.7%): the validation genuine vehicles already contain 20 Hz bursts (6% of validation inter-arrivals), so the 1% budget threshold is 20.4 Hz.
- L1 misses almost all position / speed falsification, replay and Sybil-with-plausible-rate classes: every claimed value is physically possible and each sender's rate is normal. This is the reason for L2-L4, not a defect of L1. GridSybil (16) is partly caught on VeReMi only because the ghost pseudonyms are interleaved at different rates (0.17 / 0.33 s gaps), not on the injected Tampa version where ghosts keep the attacker's rate.
- The field-range check at its PHYSICAL limit never fires on any attack (VeReMi random speeds reach 56 m/s, below 70 m/s). At the 1% budget operating point it ranks messages by speed / acceleration relative to the limit and thereby catches high-speed falsification (classes 5, 7, 14, 18 about 70%), but this is a learned quantile of genuine speed (max genuine speed 19 m/s), not a physical limit; it flags 49% of genuine senders at least once. Treat that operating point as an ablation device, not as a deployable rule.
- False alarms: a 1% message budget is large per sender (about 110 messages per VeReMi sender): the budget-point ranges layer alarms on about half of the genuine senders, the beacon-rate layer and the physical operating points on none (VeReMi). Tampa: 11-16% of genuine vehicles for a single layer, 27% for the union (small sample: 45 test vehicles, intervals in the tables).
- Freshness is only useful against stale (late-delivered) messages (S20 100% detection, 1.1% false alarms); it does nothing against the 19 injected types because they carry fresh timestamps.

## Ablation rows
Harness ablation tables are at the end of the Results section (VeReMi: two evaluable layers, so only `only_X` and `all`; Tampa: three layers, `only_X`, `all`, `all_but_X`). The combiner used validation without attack types 6, 12, 17.

## Problems, surprises, open questions
- **Class-13 DoS factor.** S1 reported a median factor of 2x. Per sender it is bimodal: 0.5 s and 0.25 s gaps (rates 2 and 4 Hz, mean 2.97, range 2.0-4.2 Hz over the 390 senders of the combined CSV). The Tampa injection keeps x2 (as approved); the VeReMi detection above uses the real data.
- **Genuine Tampa vehicles sometimes exceed 10 Hz.** 6.1% of validation and 1.5% of test genuine inter-arrivals correspond to > 10.5 Hz (mostly ~20 Hz bursts; one validation vehicle contributes half of them). Applying the standard maximum literally (physical rate alarm) gives 1.5% false alarms on genuine Tampa test messages, so the data-driven threshold is used. Cause not investigated (duplicated temporary ids or logging artefacts are possible).
- Tampa results are noisy (10 attackers per type, 45 test vehicles): use the bootstrap CIs. The combiner / harness AUC on Tampa is dominated by the huge number of injected messages relative to genuine ones (112704 attack vs 8870 genuine test messages); detection rates and false-alarm rates are the meaningful numbers.
- Single-message evaluation hides the sender-level picture: for L1 (budget point) report both. VeReMi test used once; Tampa test used once; no re-draws.
- Question for the supervisor: should S3 evaluate acceptance-range / sudden-appearance on Tampa with the RSU centroid as receiver (flagged as an approximation), or wait for V2AIX / VeReMi NextGen with receiver positions?

## Proposed next step
S3 (L2 plausibility: position / speed / heading consistency between consecutive beacons, kinematic consistency, overlapping vehicles, OSM road plausibility) is where position and speed falsification should start to be detected.
