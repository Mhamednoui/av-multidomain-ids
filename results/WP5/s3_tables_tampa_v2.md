### Tampa (injected on real BSMs) test

**Tampa test: message-level detection per class, each L2 check at the 1% validation budget**

* = attack type held out of calibration and combiner. Physical limits below.

| class | v2x.pos_speed | v2x.pos_heading | v2x.speed_change | v2x.implied_speed | v2x.heading_rate | v2x.accel_consistency | v2x.yaw_consistency | v2x.overlap |
|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 37.9% | 0.0% | 0.5% | 0.0% | 1.6% | 0.5% | 1.1% | 0.0% |
| 02_ConstPosOffset | 0.9% | 1.0% | 0.5% | 0.9% | 1.6% | 0.5% | 1.1% | 0.0% |
| 03_RandomPos | 99.8% | 69.4% | 0.5% | 99.8% | 1.6% | 0.5% | 1.1% | 0.0% |
| 04_RandomPosOffset | 99.7% | 70.6% | 0.8% | 99.7% | 4.2% | 1.1% | 1.3% | 0.0% |
| 05_ConstSpeed | 27.6% | 1.7% | 0.0% | 1.3% | 0.1% | 0.0% | 1.4% | 0.0% |
| 06_ConstSpeedOffset * | 7.2% | 2.7% | 0.7% | 0.9% | 0.6% | 0.7% | 2.3% | 0.0% |
| 07_RandomSpeed | 32.1% | 1.0% | 97.3% | 0.9% | 0.1% | 97.8% | 0.9% | 0.0% |
| 08_RandomSpeedOffset | 3.2% | 1.3% | 91.9% | 0.0% | 0.0% | 92.8% | 0.2% | 0.0% |
| 09_EventualStop | 0.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.1% | 0.0% | 0.0% |
| 10_Disruptive | 97.7% | 59.7% | 94.4% | 97.2% | 55.1% | 95.0% | 59.3% | 0.0% |
| 11_DataReplay | 12.4% | 1.5% | 1.3% | 10.1% | 2.0% | 1.1% | 3.4% | 0.0% |
| 12_DelayedMessages * | 4.9% | 1.8% | 1.2% | 1.2% | 4.4% | 1.2% | 5.6% | 0.0% |
| 13_DoS | 0.0% | 1.0% | 3.9% | 0.6% | 4.6% | 3.0% | 9.8% | 0.0% |
| 14_DoSRandom | 97.9% | 81.1% | 97.3% | 97.9% | 1.4% | 97.4% | 13.8% | 0.0% |
| 15_DoSDisruptive | 94.5% | 45.7% | 94.2% | 95.6% | 44.0% | 94.5% | 49.1% | 0.0% |
| 16_GridSybil | 0.9% | 3.9% | 0.5% | 0.9% | 1.6% | 0.5% | 1.1% | 0.0% |
| 17_DataReplaySybil * | 6.8% | 0.0% | 3.2% | 4.9% | 1.0% | 3.3% | 3.5% | 0.0% |
| 18_DoSRandomSybil | 57.7% | 47.2% | 36.1% | 57.1% | 0.0% | 39.0% | 1.1% | 0.0% |
| 19_DoSDisruptiveSybil | 52.7% | 16.0% | 24.0% | 45.8% | 10.2% | 26.9% | 14.2% | 41.7% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 45.5% |

**Tampa test: message-level detection at the physical limits (no fitted threshold)**



| class | v2x.speed_change@physical | v2x.implied_speed@physical | v2x.heading_rate@physical | L2_physical_union |
|---|---|---|---|---|
| 01_ConstPos | 0.0% | 0.0% | 0.0% | 0.0% |
| 02_ConstPosOffset | 0.0% | 0.0% | 0.0% | 0.0% |
| 03_RandomPos | 0.0% | 99.8% | 0.0% | 99.8% |
| 04_RandomPosOffset | 0.0% | 99.4% | 0.0% | 99.4% |
| 05_ConstSpeed | 0.0% | 0.0% | 0.0% | 0.0% |
| 06_ConstSpeedOffset * | 0.0% | 0.0% | 0.0% | 0.0% |
| 07_RandomSpeed | 91.6% | 0.0% | 0.0% | 91.6% |
| 08_RandomSpeedOffset | 72.1% | 0.0% | 0.0% | 72.1% |
| 09_EventualStop | 0.1% | 0.0% | 0.0% | 0.1% |
| 10_Disruptive | 86.4% | 96.6% | 47.6% | 97.1% |
| 11_DataReplay | 0.2% | 1.0% | 0.2% | 1.2% |
| 12_DelayedMessages * | 0.1% | 0.4% | 0.2% | 0.4% |
| 13_DoS | 1.3% | 0.3% | 0.6% | 1.4% |
| 14_DoSRandom | 95.9% | 97.9% | 0.3% | 97.9% |
| 15_DoSDisruptive | 89.2% | 94.3% | 40.2% | 95.1% |
| 16_GridSybil | 0.0% | 0.0% | 0.0% | 0.0% |
| 17_DataReplaySybil * | 0.9% | 2.0% | 0.0% | 2.0% |
| 18_DoSRandomSybil | 13.9% | 55.2% | 0.0% | 55.2% |
| 19_DoSDisruptiveSybil | 8.4% | 38.2% | 2.6% | 38.5% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 0.0% |

**Tampa test: message-level detection, unions and harness combinations**

L2_union = max of the calibrated L2 scores at one 1% budget; L1_union = beacon rate (budget) OR field ranges (physical) [OR freshness (budget) on Tampa]; L1_and_L2_union = L1_union OR L2_union; combined_* = harness combiner (chosen on validation) of the L1 / L2 / all layers.

| class | L2_union | L1_union_at_operating_points | L1_and_L2_union | combined_L1 | combined_L2 | combined_L1+L2 | combined_all |
|---|---|---|---|---|---|---|---|
| 01_ConstPos | 10.4% | 0.0% | 10.4% | 0.6% | 10.4% | 8.9% | 8.9% |
| 02_ConstPosOffset | 1.1% | 0.0% | 1.1% | 0.6% | 1.1% | 1.0% | 1.0% |
| 03_RandomPos | 99.8% | 0.0% | 99.8% | 0.6% | 99.8% | 99.8% | 99.8% |
| 04_RandomPosOffset | 99.7% | 0.0% | 99.7% | 0.3% | 99.7% | 99.7% | 99.7% |
| 05_ConstSpeed | 3.5% | 0.0% | 3.5% | 0.0% | 3.5% | 3.3% | 3.3% |
| 06_ConstSpeedOffset * | 3.5% | 0.0% | 3.5% | 11.7% | 3.5% | 14.8% | 14.8% |
| 07_RandomSpeed | 96.0% | 0.0% | 96.0% | 9.9% | 96.0% | 96.3% | 96.3% |
| 08_RandomSpeedOffset | 86.7% | 0.0% | 86.7% | 2.9% | 86.7% | 86.6% | 86.6% |
| 09_EventualStop | 0.1% | 0.0% | 0.1% | 0.0% | 0.1% | 0.1% | 0.1% |
| 10_Disruptive | 97.7% | 0.0% | 97.7% | 1.1% | 97.7% | 97.7% | 97.7% |
| 11_DataReplay | 8.1% | 0.0% | 8.1% | 1.2% | 8.1% | 7.9% | 7.9% |
| 12_DelayedMessages * | 6.1% | 0.0% | 6.1% | 0.2% | 6.1% | 5.1% | 5.1% |
| 13_DoS | 6.6% | 5.6% | 10.9% | 4.5% | 6.6% | 9.9% | 9.9% |
| 14_DoSRandom | 97.9% | 96.4% | 99.9% | 80.8% | 97.9% | 99.9% | 99.9% |
| 15_DoSDisruptive | 95.9% | 96.4% | 99.8% | 64.8% | 95.9% | 99.8% | 99.8% |
| 16_GridSybil | 2.1% | 0.0% | 2.1% | 0.6% | 2.1% | 1.9% | 1.9% |
| 17_DataReplaySybil * | 5.1% | 0.0% | 5.1% | 0.0% | 5.1% | 5.1% | 5.1% |
| 18_DoSRandomSybil | 57.7% | 0.0% | 57.8% | 10.1% | 57.7% | 61.8% | 61.8% |
| 19_DoSDisruptiveSybil | 60.2% | 0.0% | 60.2% | 0.3% | 60.2% | 57.4% | 57.4% |
| S20_StaleReplay | 35.0% | 100.0% | 100.0% | 0.0% | 35.0% | 100.0% | 100.0% |

**Tampa test: sender-level detection (>= 1 alarm among the attacker's falsified messages / >= 3 alarms) and median delay (s)**

>= 3 alarms in the next table.

| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | 100.0% / 0.3 s | 100.0% / 0.3 s |
| 02_ConstPosOffset | 100.0% / 83.4 s | 100.0% / 83.4 s |
| 03_RandomPos | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 04_RandomPosOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 05_ConstSpeed | 100.0% / 0.6 s | 100.0% / 0.6 s |
| 06_ConstSpeedOffset * | 100.0% / 5.6 s | 100.0% / 5.6 s |
| 07_RandomSpeed | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 08_RandomSpeedOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 09_EventualStop | 50.0% / 0.0 s | 50.0% / 0.0 s |
| 10_Disruptive | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 11_DataReplay | 100.0% / 1.4 s | 100.0% / 1.4 s |
| 12_DelayedMessages * | 100.0% / 26.8 s | 100.0% / 26.8 s |
| 13_DoS | 100.0% / 7.2 s | 100.0% / 1.2 s |
| 14_DoSRandom | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 15_DoSDisruptive | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 16_GridSybil | 100.0% / 45.3 s | 100.0% / 45.3 s |
| 17_DataReplaySybil * | 100.0% / 2.8 s | 100.0% / 2.8 s |
| 18_DoSRandomSybil | 100.0% / 0.8 s | 100.0% / 0.8 s |
| 19_DoSDisruptiveSybil | 100.0% / 0.7 s | 100.0% / 0.7 s |
| S20_StaleReplay | 100.0% / 2.0 s | 100.0% / 0.0 s |

| class | L2_union >= 3 alarms | L1_and_L2_union >= 3 alarms |
|---|---|---|
| 01_ConstPos | 100.0% | 100.0% |
| 02_ConstPosOffset | 100.0% | 100.0% |
| 03_RandomPos | 100.0% | 100.0% |
| 04_RandomPosOffset | 100.0% | 100.0% |
| 05_ConstSpeed | 100.0% | 100.0% |
| 06_ConstSpeedOffset | 100.0% | 100.0% |
| 07_RandomSpeed | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 100.0% | 100.0% |
| 09_EventualStop | 0.0% | 0.0% |
| 10_Disruptive | 100.0% | 100.0% |
| 11_DataReplay | 100.0% | 100.0% |
| 12_DelayedMessages | 100.0% | 100.0% |
| 13_DoS | 100.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% |
| 16_GridSybil | 100.0% | 100.0% |
| 17_DataReplaySybil | 100.0% | 100.0% |
| 18_DoSRandomSybil | 100.0% | 100.0% |
| 19_DoSDisruptiveSybil | 100.0% | 100.0% |
| S20_StaleReplay | 100.0% | 100.0% |
| genuine senders with >= 3 alarms | 75.0% | 75.0% |

**Tampa test: attacker-bootstrap 95% CI of message detection (L2_union and L1_and_L2_union)**



| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | [3.8%, 17.8%] | [3.8%, 17.8%] |
| 02_ConstPosOffset | [0.2%, 2.0%] | [0.2%, 2.0%] |
| 03_RandomPos | [99.7%, 99.9%] | [99.7%, 99.9%] |
| 04_RandomPosOffset | [99.7%, 99.8%] | [99.7%, 99.8%] |
| 05_ConstSpeed | [2.5%, 5.6%] | [2.5%, 5.6%] |
| 06_ConstSpeedOffset * | [1.8%, 5.2%] | [1.8%, 5.2%] |
| 07_RandomSpeed | [95.3%, 96.5%] | [95.3%, 96.5%] |
| 08_RandomSpeedOffset | [85.5%, 89.4%] | [85.5%, 89.4%] |
| 09_EventualStop | [0.0%, 0.2%] | [0.0%, 0.2%] |
| 10_Disruptive | [97.7%, 97.7%] | [97.7%, 97.7%] |
| 11_DataReplay | [7.5%, 8.8%] | [7.5%, 8.8%] |
| 12_DelayedMessages * | [0.9%, 8.6%] | [0.9%, 8.6%] |
| 13_DoS | [3.7%, 9.8%] | [7.8%, 14.1%] |
| 14_DoSRandom | [96.0%, 99.9%] | [99.9%, 99.9%] |
| 15_DoSDisruptive | [94.2%, 97.8%] | [99.8%, 99.9%] |
| 16_GridSybil | [2.0%, 2.3%] | [2.0%, 2.3%] |
| 17_DataReplaySybil * | [4.4%, 6.4%] | [4.4%, 6.4%] |
| 18_DoSRandomSybil | [56.9%, 59.5%] | [56.9%, 59.6%] |
| 19_DoSDisruptiveSybil | [59.3%, 62.2%] | [59.3%, 62.2%] |
| S20_StaleReplay | [33.0%, 37.0%] | [100.0%, 100.0%] |

**Tampa test: false alarms on genuine test messages and senders**

| operating point | genuine messages | 95% CI (vehicle bootstrap) | genuine senders with >= 1 alarm |
|---|---|---|---|
| v2x.beacon_rate | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.freshness | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.field_ranges | 0.5% | [0.0%, 1.1%] | 50.0% |
| v2x.pos_speed | 0.5% | [0.0%, 1.3%] | 25.0% |
| v2x.pos_heading | 1.4% | [0.8%, 1.9%] | 100.0% |
| v2x.speed_change | 0.6% | [0.2%, 1.0%] | 100.0% |
| v2x.implied_speed | 0.5% | [0.0%, 1.6%] | 25.0% |
| v2x.heading_rate | 2.7% | [0.7%, 5.2%] | 75.0% |
| v2x.accel_consistency | 0.7% | [0.2%, 1.2%] | 100.0% |
| v2x.yaw_consistency | 1.2% | [0.2%, 2.0%] | 75.0% |
| v2x.overlap | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.field_ranges@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.speed_change@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.implied_speed@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.heading_rate@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| L2_physical_union | 0.0% | [0.0%, 0.0%] | 0.0% |
| L2_union | 1.8% | [0.3%, 3.6%] | 100.0% |
| L1_union_at_operating_points | 0.0% | [0.0%, 0.0%] | 0.0% |
| L1_and_L2_union | 1.8% | [0.3%, 3.6%] | 100.0% |
| combined_L1 | 0.5% | [0.0%, 1.1%] | 50.0% |
| combined_L2 | 1.8% | [0.2%, 3.6%] | 100.0% |
| combined_L1+L2 | 1.7% | [0.2%, 2.8%] | 100.0% |
| combined_all | 1.7% | [0.2%, 3.3%] | 100.0% |
| v2x.map_road | 7.8% | [0.0%, 19.2%] | 50.0% |
| L1_and_L2_union_OR_v2x.map_road | 9.1% | [0.3%, 22.6%] | 100.0% |

Budget 1.0% false alarms on validation normal data. Domain: s3_tampa_v2.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | det S20_StaleReplay | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.798 | 48.7% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 5.1% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| only_v2x.accel_consistency | 0.672 | 37.3% | 0.73% | 0.5% | 0.5% | 0.5% | 1.1% | 0.0% | 0.7% | 97.8% | 92.8% | 0.1% | 95.0% | 1.1% | 1.2% | 3.0% | 97.4% | 94.5% | 0.5% | 3.3% | 39.0% | 26.9% | 0.0% | 0.0 |
| only_v2x.beacon_rate | 0.594 | 25.9% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 5.6% | 96.4% | 96.4% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_v2x.field_ranges | 0.562 | 2.9% | 0.47% | 0.6% | 0.6% | 0.6% | 0.3% | 0.0% | 11.7% | 9.6% | 2.8% | 0.0% | 1.1% | 1.2% | 0.2% | 0.2% | 10.2% | 0.2% | 0.6% | 0.0% | 10.1% | 0.3% | 0.0% | 0.0 |
| only_v2x.freshness | 0.508 | 0.3% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 0.0 |
| only_v2x.heading_rate | 0.449 | 9.2% | 2.67% | 1.6% | 1.6% | 1.6% | 4.2% | 0.1% | 0.6% | 0.1% | 0.0% | 0.0% | 55.1% | 2.0% | 4.4% | 4.6% | 1.4% | 44.0% | 1.6% | 1.0% | 0.0% | 10.2% | 0.0% | 0.0 |
| only_v2x.implied_speed | 0.669 | 39.7% | 0.52% | 0.0% | 0.9% | 99.8% | 99.7% | 1.3% | 0.9% | 0.9% | 0.0% | 0.0% | 97.2% | 10.1% | 1.2% | 0.6% | 97.9% | 95.6% | 0.9% | 4.9% | 57.1% | 45.8% | 0.0% | 0.0 |
| only_v2x.overlap | 0.511 | 2.1% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 41.7% | 45.5% | 0.0 |
| only_v2x.pos_heading | 0.557 | 26.5% | 1.37% | 0.0% | 1.0% | 69.4% | 70.6% | 1.7% | 2.7% | 1.0% | 1.3% | 0.0% | 59.7% | 1.5% | 1.8% | 1.0% | 81.1% | 45.7% | 3.9% | 0.0% | 47.2% | 16.0% | 0.0% | 0.0 |
| only_v2x.pos_speed | 0.751 | 43.3% | 0.50% | 37.9% | 0.9% | 99.8% | 99.7% | 27.6% | 7.2% | 32.1% | 3.2% | 0.0% | 97.7% | 12.4% | 4.9% | 0.0% | 97.9% | 94.5% | 0.9% | 6.8% | 57.7% | 52.7% | 0.0% | 0.0 |
| only_v2x.speed_change | 0.643 | 36.9% | 0.62% | 0.5% | 0.5% | 0.5% | 0.8% | 0.0% | 0.7% | 97.3% | 91.9% | 0.1% | 94.4% | 1.3% | 1.2% | 3.9% | 97.3% | 94.2% | 0.5% | 3.2% | 36.1% | 24.0% | 0.0% | 0.0 |
| only_v2x.yaw_consistency | 0.541 | 12.2% | 1.18% | 1.1% | 1.1% | 1.1% | 1.3% | 1.4% | 2.3% | 0.9% | 0.2% | 0.0% | 59.3% | 3.4% | 5.6% | 9.8% | 13.8% | 49.1% | 1.1% | 3.5% | 1.1% | 14.2% | 0.0% | 0.0 |
| all_but_v2x.accel_consistency | 0.796 | 48.6% | 1.61% | 8.9% | 0.9% | 99.8% | 99.7% | 3.3% | 14.8% | 95.9% | 83.3% | 0.1% | 97.7% | 7.9% | 5.0% | 9.9% | 99.9% | 99.8% | 1.8% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.beacon_rate | 0.781 | 47.7% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 5.1% | 5.7% | 98.2% | 95.9% | 1.9% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.field_ranges | 0.789 | 48.1% | 1.61% | 8.9% | 0.9% | 99.8% | 99.7% | 3.3% | 3.3% | 95.9% | 86.4% | 0.1% | 97.7% | 7.9% | 5.0% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 57.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.freshness | 0.796 | 48.5% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 5.1% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 61.8% | 57.4% | 27.5% | 0.0 |
| all_but_v2x.heading_rate | 0.807 | 48.6% | 0.71% | 8.8% | 0.9% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.7% | 3.1% | 8.6% | 99.9% | 99.8% | 1.8% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.implied_speed | 0.798 | 48.7% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.4% | 5.1% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.overlap | 0.790 | 48.5% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 5.1% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 61.8% | 51.8% | 100.0% | 0.0 |
| all_but_v2x.pos_heading | 0.797 | 48.5% | 1.59% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.7% | 96.3% | 86.5% | 0.1% | 97.7% | 7.9% | 5.0% | 9.9% | 99.9% | 99.8% | 1.0% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.pos_speed | 0.764 | 47.7% | 1.66% | 1.0% | 1.0% | 99.8% | 99.7% | 0.5% | 12.3% | 95.5% | 86.0% | 0.1% | 97.4% | 3.4% | 3.5% | 9.9% | 99.9% | 99.8% | 1.9% | 2.8% | 61.5% | 51.0% | 100.0% | 0.0 |
| all_but_v2x.speed_change | 0.804 | 48.7% | 1.66% | 8.9% | 1.0% | 99.8% | 99.7% | 3.3% | 14.8% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 5.1% | 9.9% | 99.9% | 99.8% | 1.9% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |
| all_but_v2x.yaw_consistency | 0.797 | 48.6% | 1.59% | 8.8% | 0.9% | 99.8% | 99.7% | 2.9% | 14.6% | 96.3% | 86.6% | 0.1% | 97.7% | 7.9% | 4.9% | 8.6% | 99.9% | 99.8% | 1.8% | 5.1% | 61.8% | 57.4% | 100.0% | 0.0 |

**Tampa test, harness group ablation on top of L1**

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | logistic | 0.671 | 21.1% | 0.47% |
| L2 | max | 0.764 | 47.2% | 1.82% |
| L1+L2 | max | 0.798 | 48.7% | 1.66% |
