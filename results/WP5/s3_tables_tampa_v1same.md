### Tampa (injected on real BSMs) test

**Tampa test: message-level detection per class, each L2 check at the 1% validation budget**

* = attack type held out of calibration and combiner. Physical limits below.

| class | v2x.pos_speed | v2x.pos_heading | v2x.speed_change | v2x.implied_speed | v2x.heading_rate | v2x.accel_consistency | v2x.yaw_consistency | v2x.overlap |
|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 13.8% | 0.0% | 0.9% | 0.0% | 1.3% | 0.8% | 0.8% | 0.0% |
| 02_ConstPosOffset | 0.0% | 0.8% | 0.5% | 0.1% | 0.8% | 0.5% | 0.7% | 0.0% |
| 03_RandomPos | 99.6% | 39.8% | 0.8% | 99.6% | 0.9% | 0.8% | 0.5% | 0.0% |
| 04_RandomPosOffset | 99.4% | 44.6% | 0.4% | 99.3% | 0.3% | 0.5% | 0.4% | 0.0% |
| 05_ConstSpeed | 68.9% | 1.6% | 0.0% | 0.3% | 0.0% | 0.0% | 1.8% | 0.0% |
| 06_ConstSpeedOffset * | 18.6% | 1.8% | 1.3% | 0.1% | 0.2% | 1.3% | 1.7% | 0.0% |
| 07_RandomSpeed | 41.7% | 1.0% | 96.9% | 0.2% | 0.0% | 97.6% | 0.5% | 0.0% |
| 08_RandomSpeedOffset | 6.9% | 0.6% | 89.8% | 0.2% | 0.1% | 92.0% | 0.4% | 0.0% |
| 09_EventualStop | 0.1% | 0.0% | 0.2% | 0.0% | 0.0% | 0.2% | 0.0% | 0.0% |
| 10_Disruptive | 94.3% | 15.7% | 72.6% | 93.4% | 13.1% | 74.3% | 14.7% | 0.0% |
| 11_DataReplay | 4.5% | 0.1% | 1.9% | 1.1% | 0.9% | 2.0% | 1.1% | 0.0% |
| 12_DelayedMessages * | 4.5% | 0.7% | 1.8% | 1.6% | 0.7% | 1.8% | 1.7% | 0.0% |
| 13_DoS | 0.1% | 0.6% | 2.0% | 0.4% | 0.6% | 1.8% | 2.5% | 0.0% |
| 14_DoSRandom | 99.6% | 82.1% | 98.7% | 99.6% | 0.4% | 98.9% | 5.4% | 0.0% |
| 15_DoSDisruptive | 93.9% | 14.9% | 78.4% | 94.5% | 13.9% | 79.0% | 15.4% | 0.0% |
| 16_GridSybil | 0.4% | 2.8% | 0.9% | 0.3% | 1.5% | 0.8% | 1.1% | 0.0% |
| 17_DataReplaySybil * | 23.7% | 1.2% | 9.3% | 14.3% | 2.2% | 9.3% | 4.6% | 0.0% |
| 18_DoSRandomSybil | 47.2% | 39.5% | 31.6% | 46.7% | 0.0% | 34.9% | 0.2% | 0.0% |
| 19_DoSDisruptiveSybil | 45.0% | 10.7% | 23.5% | 40.7% | 4.7% | 26.5% | 8.7% | 34.0% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 76.9% |

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
| 01_ConstPos | 10.0% | 0.6% | 10.5% | 0.5% | 19.4% | 9.6% | 9.6% |
| 02_ConstPosOffset | 0.7% | 1.2% | 1.9% | 1.1% | 1.2% | 1.3% | 1.3% |
| 03_RandomPos | 99.6% | 1.5% | 99.6% | 1.2% | 98.2% | 99.6% | 99.6% |
| 04_RandomPosOffset | 99.4% | 1.7% | 99.4% | 1.5% | 98.6% | 99.5% | 99.5% |
| 05_ConstSpeed | 42.5% | 0.4% | 42.9% | 0.5% | 66.3% | 39.4% | 39.4% |
| 06_ConstSpeedOffset * | 12.4% | 0.7% | 13.1% | 7.0% | 42.4% | 17.8% | 17.8% |
| 07_RandomSpeed | 97.6% | 0.3% | 97.6% | 3.7% | 98.1% | 97.2% | 97.2% |
| 08_RandomSpeedOffset | 89.3% | 2.1% | 89.5% | 5.8% | 95.0% | 88.3% | 88.3% |
| 09_EventualStop | 0.2% | 0.3% | 0.6% | 0.0% | 0.2% | 0.2% | 0.2% |
| 10_Disruptive | 94.4% | 0.8% | 94.5% | 1.3% | 93.0% | 94.3% | 94.3% |
| 11_DataReplay | 3.6% | 0.0% | 3.6% | 0.0% | 6.9% | 3.4% | 3.4% |
| 12_DelayedMessages * | 3.6% | 0.0% | 3.6% | 0.2% | 13.0% | 3.4% | 3.4% |
| 13_DoS | 1.9% | 5.7% | 7.2% | 5.5% | 1.0% | 3.4% | 3.4% |
| 14_DoSRandom | 99.6% | 94.3% | 99.8% | 94.4% | 99.6% | 99.8% | 99.8% |
| 15_DoSDisruptive | 95.1% | 92.8% | 99.3% | 92.8% | 93.4% | 99.3% | 99.3% |
| 16_GridSybil | 2.0% | 0.6% | 2.5% | 0.6% | 1.7% | 1.7% | 1.7% |
| 17_DataReplaySybil * | 21.8% | 1.4% | 22.6% | 3.1% | 24.6% | 21.3% | 21.3% |
| 18_DoSRandomSybil | 47.2% | 1.3% | 47.9% | 4.3% | 47.2% | 48.3% | 48.3% |
| 19_DoSDisruptiveSybil | 63.7% | 1.3% | 64.1% | 1.7% | 61.8% | 64.1% | 64.1% |
| S20_StaleReplay | 76.9% | 100.0% | 100.0% | 100.0% | 76.9% | 100.0% | 100.0% |

**Tampa test: sender-level detection (>= 1 alarm among the attacker's falsified messages / >= 3 alarms) and median delay (s)**

>= 3 alarms in the next table.

| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | 100.0% / 1.0 s | 100.0% / 1.0 s |
| 02_ConstPosOffset | 80.0% / 40.3 s | 90.0% / 13.2 s |
| 03_RandomPos | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 04_RandomPosOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 05_ConstSpeed | 100.0% / 1.2 s | 100.0% / 1.2 s |
| 06_ConstSpeedOffset * | 100.0% / 0.7 s | 100.0% / 0.7 s |
| 07_RandomSpeed | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 08_RandomSpeedOffset | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 09_EventualStop | 70.0% / 0.0 s | 70.0% / 0.0 s |
| 10_Disruptive | 100.0% / 0.1 s | 100.0% / 0.1 s |
| 11_DataReplay | 100.0% / 1.4 s | 100.0% / 1.4 s |
| 12_DelayedMessages * | 100.0% / 1.5 s | 100.0% / 1.5 s |
| 13_DoS | 90.0% / 4.4 s | 100.0% / 2.8 s |
| 14_DoSRandom | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 15_DoSDisruptive | 100.0% / 0.0 s | 100.0% / 0.0 s |
| 16_GridSybil | 90.0% / 5.0 s | 90.0% / 4.6 s |
| 17_DataReplaySybil * | 100.0% / 0.3 s | 100.0% / 0.3 s |
| 18_DoSRandomSybil | 100.0% / 0.9 s | 100.0% / 0.9 s |
| 19_DoSDisruptiveSybil | 100.0% / 0.6 s | 100.0% / 0.6 s |
| S20_StaleReplay | 100.0% / 0.0 s | 100.0% / 0.0 s |

| class | L2_union >= 3 alarms | L1_and_L2_union >= 3 alarms |
|---|---|---|
| 01_ConstPos | 100.0% | 100.0% |
| 02_ConstPosOffset | 50.0% | 60.0% |
| 03_RandomPos | 100.0% | 100.0% |
| 04_RandomPosOffset | 100.0% | 100.0% |
| 05_ConstSpeed | 100.0% | 100.0% |
| 06_ConstSpeedOffset | 100.0% | 100.0% |
| 07_RandomSpeed | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 100.0% | 100.0% |
| 09_EventualStop | 0.0% | 10.0% |
| 10_Disruptive | 100.0% | 100.0% |
| 11_DataReplay | 90.0% | 90.0% |
| 12_DelayedMessages | 90.0% | 100.0% |
| 13_DoS | 50.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% |
| 16_GridSybil | 90.0% | 90.0% |
| 17_DataReplaySybil | 100.0% | 100.0% |
| 18_DoSRandomSybil | 100.0% | 100.0% |
| 19_DoSDisruptiveSybil | 100.0% | 100.0% |
| S20_StaleReplay | 100.0% | 100.0% |
| genuine senders with >= 3 alarms | 24.4% | 31.1% |

**Tampa test: attacker-bootstrap 95% CI of message detection (L2_union and L1_and_L2_union)**



| class | L2_union | L1_and_L2_union |
|---|---|---|
| 01_ConstPos | [4.9%, 22.9%] | [5.4%, 23.8%] |
| 02_ConstPosOffset | [0.3%, 1.0%] | [0.6%, 6.2%] |
| 03_RandomPos | [99.0%, 99.7%] | [99.0%, 99.7%] |
| 04_RandomPosOffset | [98.9%, 99.7%] | [98.9%, 99.7%] |
| 05_ConstSpeed | [14.6%, 66.3%] | [17.4%, 69.1%] |
| 06_ConstSpeedOffset * | [6.4%, 20.1%] | [7.1%, 20.9%] |
| 07_RandomSpeed | [96.7%, 97.9%] | [96.7%, 97.9%] |
| 08_RandomSpeedOffset | [88.1%, 89.9%] | [88.4%, 90.0%] |
| 09_EventualStop | [0.1%, 1.1%] | [0.1%, 3.0%] |
| 10_Disruptive | [93.0%, 95.1%] | [93.1%, 95.2%] |
| 11_DataReplay | [2.5%, 7.1%] | [2.5%, 7.0%] |
| 12_DelayedMessages * | [2.3%, 7.1%] | [2.4%, 7.3%] |
| 13_DoS | [0.8%, 4.2%] | [5.3%, 11.0%] |
| 14_DoSRandom | [98.7%, 99.9%] | [99.6%, 99.9%] |
| 15_DoSDisruptive | [93.9%, 96.1%] | [99.1%, 99.6%] |
| 16_GridSybil | [0.8%, 3.8%] | [0.9%, 4.7%] |
| 17_DataReplaySybil * | [18.4%, 26.0%] | [18.6%, 28.6%] |
| 18_DoSRandomSybil | [42.5%, 50.6%] | [43.0%, 51.6%] |
| 19_DoSDisruptiveSybil | [55.0%, 66.6%] | [56.5%, 67.1%] |
| S20_StaleReplay | [73.5%, 80.3%] | [100.0%, 100.0%] |

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
| v2x.field_ranges@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.speed_change@physical | 0.0% | [0.0%, 0.1%] | 4.4% |
| v2x.implied_speed@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| v2x.heading_rate@physical | 0.0% | [0.0%, 0.0%] | 0.0% |
| L2_physical_union | 0.0% | [0.0%, 0.1%] | 4.4% |
| L2_union | 1.0% | [0.6%, 1.6%] | 40.0% |
| L1_union_at_operating_points | 1.3% | [0.2%, 3.6%] | 26.7% |
| L1_and_L2_union | 2.3% | [1.1%, 5.0%] | 53.3% |
| combined_L1 | 0.9% | [0.2%, 2.7%] | 31.1% |
| combined_L2 | 1.3% | [0.9%, 2.0%] | 53.3% |
| combined_L1+L2 | 1.3% | [0.6%, 2.4%] | 37.8% |
| combined_all | 1.3% | [0.6%, 2.6%] | 37.8% |
| v2x.map_road | 5.5% | [0.3%, 17.0%] | 8.9% |
| L1_and_L2_union_OR_v2x.map_road | 7.7% | [2.2%, 19.9%] | 55.6% |

Budget 1.0% false alarms on validation normal data. Domain: s3_tampa_v1same.

| configuration | AUC | detection | false alarms | det 01_ConstPos | det 02_ConstPosOffset | det 03_RandomPos | det 04_RandomPosOffset | det 05_ConstSpeed | det 06_ConstSpeedOffset | det 07_RandomSpeed | det 08_RandomSpeedOffset | det 09_EventualStop | det 10_Disruptive | det 11_DataReplay | det 12_DelayedMessages | det 13_DoS | det 14_DoSRandom | det 15_DoSDisruptive | det 16_GridSybil | det 17_DataReplaySybil | det 18_DoSRandomSybil | det 19_DoSDisruptiveSybil | det S20_StaleReplay | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.756 | 46.6% | 1.26% | 9.6% | 1.3% | 99.6% | 99.5% | 39.4% | 17.8% | 97.2% | 88.3% | 0.2% | 94.3% | 3.4% | 3.4% | 3.4% | 99.8% | 99.3% | 1.7% | 21.3% | 48.3% | 64.1% | 100.0% | 0.0 |
| only_v2x.accel_consistency | 0.624 | 29.6% | 0.73% | 0.8% | 0.5% | 0.8% | 0.5% | 0.0% | 1.3% | 97.6% | 92.0% | 0.2% | 74.3% | 2.0% | 1.8% | 1.8% | 98.9% | 79.0% | 0.8% | 9.3% | 34.9% | 26.5% | 0.0% | 0.0 |
| only_v2x.beacon_rate | 0.527 | 16.3% | 0.21% | 0.6% | 0.1% | 0.3% | 0.1% | 0.4% | 0.6% | 0.2% | 0.1% | 0.3% | 0.7% | 0.0% | 0.0% | 5.7% | 94.3% | 92.8% | 0.6% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0 |
| only_v2x.field_ranges | 0.604 | 1.0% | 0.33% | 0.4% | 0.1% | 0.1% | 0.1% | 0.0% | 6.7% | 2.4% | 3.8% | 0.0% | 0.3% | 0.0% | 0.1% | 0.5% | 2.5% | 0.1% | 0.6% | 0.0% | 2.3% | 0.6% | 0.6% | 0.0 |
| only_v2x.freshness | 0.499 | 1.4% | 1.08% | 0.0% | 1.1% | 1.2% | 1.6% | 0.0% | 0.1% | 0.0% | 2.0% | 0.0% | 0.1% | 0.0% | 0.0% | 0.0% | 0.1% | 0.1% | 0.0% | 1.4% | 1.2% | 1.3% | 100.0% | 0.0 |
| only_v2x.heading_rate | 0.443 | 2.1% | 0.89% | 1.3% | 0.8% | 0.9% | 0.3% | 0.0% | 0.2% | 0.0% | 0.1% | 0.0% | 13.1% | 0.9% | 0.7% | 0.6% | 0.4% | 13.9% | 1.5% | 2.2% | 0.0% | 4.7% | 0.0% | 0.0 |
| only_v2x.implied_speed | 0.619 | 34.0% | 0.17% | 0.0% | 0.1% | 99.6% | 99.3% | 0.3% | 0.1% | 0.2% | 0.2% | 0.0% | 93.4% | 1.1% | 1.6% | 0.4% | 99.6% | 94.5% | 0.3% | 14.3% | 46.7% | 40.7% | 0.0% | 0.0 |
| only_v2x.overlap | 0.517 | 3.5% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 34.0% | 76.9% | 0.0 |
| only_v2x.pos_heading | 0.546 | 18.0% | 0.80% | 0.0% | 0.8% | 39.8% | 44.6% | 1.6% | 1.8% | 1.0% | 0.6% | 0.0% | 15.7% | 0.1% | 0.7% | 0.6% | 82.1% | 14.9% | 2.8% | 1.2% | 39.5% | 10.7% | 0.0% | 0.0 |
| only_v2x.pos_speed | 0.690 | 39.8% | 0.20% | 13.8% | 0.0% | 99.6% | 99.4% | 68.9% | 18.6% | 41.7% | 6.9% | 0.1% | 94.3% | 4.5% | 4.5% | 0.1% | 99.6% | 93.9% | 0.4% | 23.7% | 47.2% | 45.0% | 0.0% | 0.0 |
| only_v2x.speed_change | 0.611 | 28.9% | 0.69% | 0.9% | 0.5% | 0.8% | 0.4% | 0.0% | 1.3% | 96.9% | 89.8% | 0.2% | 72.6% | 1.9% | 1.8% | 2.0% | 98.7% | 78.4% | 0.9% | 9.3% | 31.6% | 23.5% | 0.0% | 0.0 |
| only_v2x.yaw_consistency | 0.511 | 3.4% | 0.64% | 0.8% | 0.7% | 0.5% | 0.4% | 1.8% | 1.7% | 0.5% | 0.4% | 0.0% | 14.7% | 1.1% | 1.7% | 2.5% | 5.4% | 15.4% | 1.1% | 4.6% | 0.2% | 8.7% | 0.0% | 0.0 |
| all_but_v2x.accel_consistency | 0.757 | 46.6% | 1.27% | 9.8% | 1.4% | 99.6% | 99.5% | 41.4% | 17.9% | 96.3% | 85.6% | 0.2% | 94.3% | 3.3% | 3.4% | 3.3% | 99.8% | 99.3% | 1.8% | 21.4% | 48.5% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.beacon_rate | 0.739 | 46.2% | 1.24% | 9.6% | 1.3% | 99.6% | 99.5% | 39.4% | 17.8% | 97.2% | 88.3% | 0.2% | 94.3% | 3.3% | 3.4% | 1.7% | 99.6% | 95.1% | 1.7% | 21.3% | 48.3% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.field_ranges | 0.739 | 46.6% | 1.36% | 9.9% | 1.4% | 99.6% | 99.4% | 41.4% | 12.1% | 97.5% | 89.0% | 0.2% | 94.3% | 3.4% | 3.5% | 3.4% | 99.8% | 99.3% | 1.9% | 21.7% | 47.6% | 64.0% | 100.0% | 0.0 |
| all_but_v2x.freshness | 0.760 | 46.6% | 0.99% | 9.9% | 0.8% | 99.6% | 99.5% | 42.4% | 18.4% | 97.5% | 89.6% | 0.2% | 94.3% | 3.6% | 3.6% | 3.5% | 99.8% | 99.3% | 2.0% | 21.7% | 48.1% | 63.9% | 76.9% | 0.0 |
| all_but_v2x.heading_rate | 0.758 | 46.7% | 1.17% | 9.7% | 1.2% | 99.6% | 99.5% | 41.4% | 18.1% | 97.5% | 89.4% | 0.2% | 94.3% | 3.1% | 3.3% | 3.3% | 99.8% | 99.3% | 1.9% | 21.4% | 48.5% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.implied_speed | 0.756 | 46.7% | 1.38% | 9.9% | 1.4% | 99.6% | 99.5% | 41.4% | 18.1% | 97.5% | 89.4% | 0.2% | 94.3% | 3.4% | 3.5% | 3.4% | 99.8% | 99.3% | 1.9% | 20.5% | 48.5% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.overlap | 0.744 | 45.1% | 1.26% | 9.6% | 1.3% | 99.6% | 99.5% | 39.4% | 17.8% | 97.2% | 88.3% | 0.2% | 94.3% | 3.4% | 3.4% | 3.4% | 99.8% | 99.3% | 1.7% | 21.3% | 48.3% | 45.3% | 100.0% | 0.0 |
| all_but_v2x.pos_heading | 0.757 | 46.7% | 1.33% | 9.9% | 1.3% | 99.6% | 99.5% | 41.2% | 18.0% | 97.5% | 89.4% | 0.2% | 94.3% | 3.4% | 3.5% | 3.4% | 99.8% | 99.3% | 1.5% | 21.7% | 48.4% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.pos_speed | 0.741 | 44.3% | 1.38% | 1.2% | 1.4% | 99.6% | 99.3% | 0.7% | 7.9% | 95.7% | 86.9% | 0.2% | 93.8% | 1.4% | 2.0% | 3.4% | 99.8% | 99.2% | 2.0% | 14.0% | 48.3% | 61.3% | 100.0% | 0.0 |
| all_but_v2x.speed_change | 0.758 | 46.8% | 1.38% | 9.9% | 1.4% | 99.6% | 99.5% | 41.4% | 18.1% | 97.5% | 89.4% | 0.2% | 94.3% | 3.4% | 3.5% | 3.4% | 99.8% | 99.3% | 2.0% | 21.7% | 48.5% | 64.1% | 100.0% | 0.0 |
| all_but_v2x.yaw_consistency | 0.758 | 46.7% | 1.34% | 9.8% | 1.4% | 99.6% | 99.5% | 41.2% | 17.8% | 97.5% | 89.4% | 0.2% | 94.3% | 3.4% | 3.1% | 3.2% | 99.8% | 99.3% | 1.9% | 21.7% | 48.5% | 64.1% | 100.0% | 0.0 |

**Tampa test, harness group ablation on top of L1**

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | noisy_or | 0.629 | 18.4% | 0.92% |
| L2 | logistic | 0.735 | 48.0% | 1.31% |
| L1+L2 | max | 0.756 | 46.6% | 1.26% |
