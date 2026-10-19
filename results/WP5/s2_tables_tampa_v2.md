**Tampa (injected) test, message-level detection per type**

10 attackers per type: see s2_summary.json for attacker-bootstrap 95% CIs. S20 = supplemental stale replay (not in the 19).

| class | v2x.beacon_rate | v2x.freshness | v2x.field_ranges | v2x.field_ranges@physical | L1_union_at_operating_points | combined |
|---|---|---|---|---|---|---|
| 01_ConstPos | 0.0% | 0.0% | 0.6% | 0.0% | 0.0% | 0.6% |
| 02_ConstPosOffset | 0.0% | 0.0% | 0.6% | 0.0% | 0.0% | 0.6% |
| 03_RandomPos | 0.0% | 0.0% | 0.6% | 0.0% | 0.0% | 0.6% |
| 04_RandomPosOffset | 0.0% | 0.0% | 0.3% | 0.0% | 0.0% | 0.3% |
| 05_ConstSpeed | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 06_ConstSpeedOffset * | 0.0% | 0.0% | 11.7% | 0.0% | 0.0% | 11.7% |
| 07_RandomSpeed | 0.0% | 0.0% | 9.6% | 0.0% | 0.0% | 9.9% |
| 08_RandomSpeedOffset | 0.0% | 0.0% | 2.8% | 0.0% | 0.0% | 2.9% |
| 09_EventualStop | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 10_Disruptive | 0.0% | 0.0% | 1.1% | 0.0% | 0.0% | 1.1% |
| 11_DataReplay | 0.0% | 0.0% | 1.2% | 0.0% | 0.0% | 1.2% |
| 12_DelayedMessages * | 0.0% | 0.0% | 0.2% | 0.0% | 0.0% | 0.2% |
| 13_DoS | 5.6% | 0.0% | 0.2% | 0.0% | 5.6% | 4.5% |
| 14_DoSRandom | 96.4% | 0.0% | 10.2% | 0.0% | 96.4% | 80.8% |
| 15_DoSDisruptive | 96.4% | 0.0% | 0.2% | 0.0% | 96.4% | 64.8% |
| 16_GridSybil | 0.0% | 0.0% | 0.6% | 0.0% | 0.0% | 0.6% |
| 17_DataReplaySybil * | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% |
| 18_DoSRandomSybil | 0.0% | 0.0% | 10.1% | 0.0% | 0.0% | 10.1% |
| 19_DoSDisruptiveSybil | 0.0% | 0.0% | 0.3% | 0.0% | 0.0% | 0.3% |
| S20_StaleReplay | 0.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% |

**Tampa test, attacker-bootstrap 95% CI of message detection (combined and union)**



| class | L1_union_at_operating_points | combined |
|---|---|---|
| 01_ConstPos | [0.0%, 0.0%] | [0.0%, 1.3%] |
| 02_ConstPosOffset | [0.0%, 0.0%] | [0.0%, 1.3%] |
| 03_RandomPos | [0.0%, 0.0%] | [0.0%, 1.3%] |
| 04_RandomPosOffset | [0.0%, 0.0%] | [0.0%, 0.4%] |
| 05_ConstSpeed | [0.0%, 0.0%] | [0.0%, 0.0%] |
| 06_ConstSpeedOffset * | [0.0%, 0.0%] | [0.0%, 23.8%] |
| 07_RandomSpeed | [0.0%, 0.0%] | [9.8%, 10.1%] |
| 08_RandomSpeedOffset | [0.0%, 0.0%] | [0.0%, 4.2%] |
| 09_EventualStop | [0.0%, 0.0%] | [0.0%, 0.0%] |
| 10_Disruptive | [0.0%, 0.0%] | [1.0%, 1.4%] |
| 11_DataReplay | [0.0%, 0.0%] | [1.2%, 1.3%] |
| 12_DelayedMessages * | [0.0%, 0.0%] | [0.0%, 0.3%] |
| 13_DoS | [5.1%, 6.1%] | [3.5%, 5.5%] |
| 14_DoSRandom | [94.0%, 98.9%] | [80.1%, 81.5%] |
| 15_DoSDisruptive | [94.1%, 98.9%] | [63.1%, 66.7%] |
| 16_GridSybil | [0.0%, 0.0%] | [0.0%, 1.3%] |
| 17_DataReplaySybil * | [0.0%, 0.0%] | [0.0%, 0.0%] |
| 18_DoSRandomSybil | [0.0%, 0.1%] | [10.1%, 10.1%] |
| 19_DoSDisruptiveSybil | [0.0%, 0.0%] | [0.2%, 0.4%] |
| S20_StaleReplay | [100.0%, 100.0%] | [0.0%, 0.0%] |

**Tampa test, false alarms on genuine messages and vehicles**

| operating point | genuine messages | 95% CI (vehicle bootstrap) | genuine vehicles with >= 1 alarm |
|---|---|---|---|
| v2x.beacon_rate | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.freshness | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.field_ranges | 0.5% | [0.0%, 1.1%] | 50.0% |
| combined | 0.5% | [0.0%, 1.1%] | 50.0% |
| v2x.field_ranges@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.beacon_rate@physical_standard | 8.4% | [3.2%, 12.1%] | 100.0% |
| L1_union_at_operating_points | 0.0% | [0.0%, 0.0%] | 0.0% |

Budget 1.0% false alarms on validation normal data. Domain: s2_tampa_v2.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | det S20_StaleReplay | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.671 | 21.1% | 0.47% | 0.6% | 0.6% | 0.6% | 0.3% | 0.0% | 11.7% | 9.9% | 2.9% | 0.0% | 1.1% | 1.2% | 0.2% | 4.5% | 80.8% | 64.8% | 0.6% | 0.0% | 10.1% | 0.3% | 0.0% | 0.0 |
| only_v2x.beacon_rate | 0.594 | 25.9% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 5.6% | 96.4% | 96.4% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_v2x.field_ranges | 0.562 | 2.9% | 0.47% | 0.6% | 0.6% | 0.6% | 0.3% | 0.0% | 11.7% | 9.6% | 2.8% | 0.0% | 1.1% | 1.2% | 0.2% | 0.2% | 10.2% | 0.2% | 0.6% | 0.0% | 10.1% | 0.3% | 0.0% | 0.0 |
| only_v2x.freshness | 0.508 | 0.3% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0 |
| all_but_v2x.beacon_rate | 0.564 | 2.9% | 0.47% | 0.6% | 0.6% | 0.6% | 0.3% | 0.0% | 11.7% | 9.6% | 2.8% | 0.0% | 1.1% | 1.2% | 0.2% | 0.2% | 10.2% | 0.2% | 0.6% | 0.0% | 10.1% | 0.3% | 0.0% | 0.0 |
| all_but_v2x.field_ranges | 0.602 | 26.0% | 0.09% | 0.0% | 0.0% | 0.0% | 0.2% | 0.2% | 0.0% | 0.0% | 0.2% | 0.0% | 0.2% | 0.0% | 0.2% | 5.7% | 96.4% | 96.4% | 0.0% | 0.2% | 0.1% | 0.0% | 0.0% | 0.0 |
| all_but_v2x.freshness | 0.671 | 17.6% | 0.47% | 0.6% | 0.6% | 0.6% | 0.3% | 0.0% | 11.7% | 9.8% | 2.8% | 0.0% | 1.1% | 1.2% | 0.2% | 2.6% | 73.7% | 46.8% | 0.6% | 0.0% | 10.2% | 0.3% | 0.0% | 0.0 |
