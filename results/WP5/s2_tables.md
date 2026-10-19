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
