**Tampa data, old vs new**

| | old (S1) | new (S1b) |
|---|---|---|
| rows in the CSV | 34464 | 34464 |
| distinct over-the-air messages | (34,453 counted, copies kept) | 19527 |
| grouping unit | 226 coreData_ids (per RSU) | 40 passages of 38 physical vehicles |
| split | by id 136 / 45 / 45 | time blocks (episodes) seed 48: 30 / 6 / 4 passages |
| genuine val / test messages scored | 4491 / 8870 | 2094 / 4225 |
| attackers per type val / test | 10 / 10 | 2 / 2 |

**False alarms on genuine test messages (95% vehicle/passage bootstrap CI for new)**

| operating point | old | v1same | new |
|---|---|---|---|
| beacon rate (L1) | 0.2% | 0.2% | 0.0% [0-0] |
| freshness (L1) | 1.1% | 1.1% | 0.0% [0-0] |
| field ranges, budget (L1) | 0.3% | 0.3% | 0.5% [0-1] |
| field ranges, physical | 0.0% | 0.0% | 0.0% [0-0] |
| L1 union | 1.3% | 1.3% | 0.0% [0-0] |
| pos_speed | 0.2% | 0.2% | 0.5% [0-1] |
| pos_heading | 0.8% | 0.8% | 1.4% [1-2] |
| speed_change | 0.7% | 0.7% | 0.6% [0-1] |
| implied_speed | 0.2% | 0.2% | 0.5% [0-2] |
| heading_rate | 0.9% | 0.9% | 2.7% [1-5] |
| accel_consistency | 0.7% | 0.7% | 0.7% [0-1] |
| yaw_consistency | 0.6% | 0.6% | 1.2% [0-2] |
| overlap | 0.0% | 0.0% | 0.0% [0-0] |
| L2 physical union | 0.0% | 0.0% | 0.0% [0-0] |
| L2 union (deployable; old = with map) | 6.3% | 1.0% | 1.8% [0-4] |
| L1 + L2 union (deployable; old = with map) | 7.6% | 2.3% | 1.8% [0-4] |
| harness combined, all layers | 6.7% | 1.3% | 1.7% [0-3] |
| map_road alone (soft layer) | 5.5% | 5.5% | 7.8% [0-19] |
| L1 + L2 union OR map_road | - | 7.7% | 9.1% [0-23] |

**Physical limits, false alarms on genuine val / test** (bound 0.1%)

| limit | old | v1same | new |
|---|---|---|---|
| v2x.field_ranges | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| v2x.speed_change | 0.000% / 0.023% | 0.000% / 0.023% | 0.000% / 0.000% |
| v2x.implied_speed | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| v2x.heading_rate | 0.000% / 0.000% | 0.000% / 0.000% | 0.000% / 0.000% |
| L2_physical_union | 0.000% / 0.023% | 0.000% / 0.023% | 0.000% / 0.000% |

**Tampa test, message-level detection, L1 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 0.6% | 0.6% | 0.0% [0-0] | 2 |
| 02_ConstPosOffset | 1.2% | 1.2% | 0.0% [0-0] | 2 |
| 03_RandomPos | 1.5% | 1.5% | 0.0% [0-0] | 2 |
| 04_RandomPosOffset | 1.7% | 1.7% | 0.0% [0-0] | 2 |
| 05_ConstSpeed | 0.4% | 0.4% | 0.0% [0-0] | 2 |
| 06_ConstSpeedOffset * | 0.7% | 0.7% | 0.0% [0-0] | 2 |
| 07_RandomSpeed | 0.3% | 0.3% | 0.0% [0-0] | 2 |
| 08_RandomSpeedOffset | 2.1% | 2.1% | 0.0% [0-0] | 2 |
| 09_EventualStop | 0.3% | 0.3% | 0.0% [0-0] | 2 |
| 10_Disruptive | 0.8% | 0.8% | 0.0% [0-0] | 2 |
| 11_DataReplay | 0.0% | 0.0% | 0.0% [0-0] | 2 |
| 12_DelayedMessages * | 0.0% | 0.0% | 0.0% [0-0] | 2 |
| 13_DoS | 5.7% | 5.7% | 5.6% [5-6] | 2 |
| 14_DoSRandom | 94.3% | 94.3% | 96.4% [94-99] | 2 |
| 15_DoSDisruptive | 92.8% | 92.8% | 96.4% [94-99] | 2 |
| 16_GridSybil | 0.6% | 0.6% | 0.0% [0-0] | 2 |
| 17_DataReplaySybil * | 1.4% | 1.4% | 0.0% [0-0] | 2 |
| 18_DoSRandomSybil | 1.3% | 1.3% | 0.0% [0-0] | 2 |
| 19_DoSDisruptiveSybil | 1.3% | 1.3% | 0.0% [0-0] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Tampa test, message-level detection, L2 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 15.0% | 10.0% | 10.4% [4-18] | 2 |
| 02_ConstPosOffset | 37.2% | 0.7% | 1.1% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.4% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 54.3% | 42.5% | 3.5% [3-6] | 2 |
| 06_ConstSpeedOffset * | 28.7% | 12.4% | 3.5% [2-5] | 2 |
| 07_RandomSpeed | 97.6% | 97.6% | 96.0% [95-97] | 2 |
| 08_RandomSpeedOffset | 90.3% | 89.3% | 86.7% [85-89] | 2 |
| 09_EventualStop | 3.1% | 0.2% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.4% | 94.4% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.6% | 8.1% [7-9] | 2 |
| 12_DelayedMessages * | 10.4% | 3.6% | 6.1% [1-9] | 2 |
| 13_DoS | 2.5% | 1.9% | 6.6% [4-10] | 2 |
| 14_DoSRandom | 99.8% | 99.6% | 97.9% [96-100] | 2 |
| 15_DoSDisruptive | 95.2% | 95.1% | 95.9% [94-98] | 2 |
| 16_GridSybil | 5.1% | 2.0% | 2.1% [2-2] | 2 |
| 17_DataReplaySybil * | 39.6% | 21.8% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.0% | 47.2% | 57.7% [57-59] | 2 |
| 19_DoSDisruptiveSybil | 64.0% | 63.7% | 60.2% [59-62] | 2 |
| S20_StaleReplay | 78.9% | 76.9% | 35.0% [33-37] | 2 |

**Tampa test, message-level detection, L1+L2 union** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 15.5% | 10.5% | 10.4% [4-18] | 2 |
| 02_ConstPosOffset | 37.6% | 1.9% | 1.1% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.4% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 54.8% | 42.9% | 3.5% [3-6] | 2 |
| 06_ConstSpeedOffset * | 29.4% | 13.1% | 3.5% [2-5] | 2 |
| 07_RandomSpeed | 97.6% | 97.6% | 96.0% [95-97] | 2 |
| 08_RandomSpeedOffset | 90.5% | 89.5% | 86.7% [85-89] | 2 |
| 09_EventualStop | 3.4% | 0.6% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.5% | 94.5% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.6% | 8.1% [7-9] | 2 |
| 12_DelayedMessages * | 10.4% | 3.6% | 6.1% [1-9] | 2 |
| 13_DoS | 7.8% | 7.2% | 10.9% [8-14] | 2 |
| 14_DoSRandom | 99.9% | 99.8% | 99.9% [100-100] | 2 |
| 15_DoSDisruptive | 99.4% | 99.3% | 99.8% [100-100] | 2 |
| 16_GridSybil | 5.6% | 2.5% | 2.1% [2-2] | 2 |
| 17_DataReplaySybil * | 40.4% | 22.6% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.3% | 47.9% | 57.8% [57-60] | 2 |
| 19_DoSDisruptiveSybil | 64.4% | 64.1% | 60.2% [59-62] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Tampa test, message-level detection, map_road (soft)** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 5.3% | 5.3% | 0.0% [0-0] | 2 |
| 02_ConstPosOffset | 37.5% | 37.5% | 62.2% [49-77] | 2 |
| 03_RandomPos | 47.1% | 47.1% | 63.2% [63-63] | 2 |
| 04_RandomPosOffset | 44.3% | 44.3% | 69.7% [67-71] | 2 |
| 05_ConstSpeed | 14.1% | 14.1% | 0.9% [0-1] | 2 |
| 06_ConstSpeedOffset * | 17.7% | 17.7% | 14.0% [1-26] | 2 |
| 07_RandomSpeed | 7.1% | 7.1% | 0.6% [0-1] | 2 |
| 08_RandomSpeedOffset | 13.0% | 13.0% | 0.0% [0-0] | 2 |
| 09_EventualStop | 2.8% | 2.8% | 0.0% [0-0] | 2 |
| 10_Disruptive | 0.9% | 0.9% | 12.8% [13-13] | 2 |
| 11_DataReplay | 8.2% | 8.2% | 1.2% [1-1] | 2 |
| 12_DelayedMessages * | 7.1% | 7.1% | 17.8% [0-26] | 2 |
| 13_DoS | 0.8% | 0.8% | 12.5% [0-26] | 2 |
| 14_DoSRandom | 45.8% | 45.8% | 63.4% [63-63] | 2 |
| 15_DoSDisruptive | 5.9% | 5.9% | 17.2% [17-17] | 2 |
| 16_GridSybil | 3.3% | 3.3% | 0.5% [0-1] | 2 |
| 17_DataReplaySybil * | 22.1% | 22.1% | 59.6% [48-65] | 2 |
| 18_DoSRandomSybil | 45.3% | 45.3% | 63.5% [63-64] | 2 |
| 19_DoSDisruptiveSybil | 0.5% | 0.5% | 12.2% [11-13] | 2 |
| S20_StaleReplay | 11.9% | 11.9% | 14.5% [11-18] | 2 |

**Tampa test, message-level detection, combined** (new: attacker-bootstrap CI; * held-out type)

| type | old | v1same | new | attackers (new) |
|---|---|---|---|---|
| 01_ConstPos | 14.8% | 9.6% | 8.9% [4-15] | 2 |
| 02_ConstPosOffset | 37.3% | 1.3% | 1.0% [0-2] | 2 |
| 03_RandomPos | 99.8% | 99.6% | 99.8% [100-100] | 2 |
| 04_RandomPosOffset | 99.7% | 99.5% | 99.7% [100-100] | 2 |
| 05_ConstSpeed | 52.4% | 39.4% | 3.3% [2-5] | 2 |
| 06_ConstSpeedOffset * | 34.4% | 17.8% | 14.8% [5-25] | 2 |
| 07_RandomSpeed | 97.5% | 97.2% | 96.3% [96-97] | 2 |
| 08_RandomSpeedOffset | 89.9% | 88.3% | 86.6% [85-89] | 2 |
| 09_EventualStop | 3.1% | 0.2% | 0.1% [0-0] | 2 |
| 10_Disruptive | 94.3% | 94.3% | 97.7% [98-98] | 2 |
| 11_DataReplay | 11.4% | 3.4% | 7.9% [7-9] | 2 |
| 12_DelayedMessages * | 10.3% | 3.4% | 5.1% [1-7] | 2 |
| 13_DoS | 4.2% | 3.4% | 9.9% [7-13] | 2 |
| 14_DoSRandom | 99.9% | 99.8% | 99.9% [100-100] | 2 |
| 15_DoSDisruptive | 99.4% | 99.3% | 99.8% [100-100] | 2 |
| 16_GridSybil | 4.9% | 1.7% | 1.9% [2-2] | 2 |
| 17_DataReplaySybil * | 39.7% | 21.3% | 5.1% [4-6] | 2 |
| 18_DoSRandomSybil | 71.5% | 48.3% | 61.8% [61-64] | 2 |
| 19_DoSDisruptiveSybil | 64.4% | 64.1% | 57.4% [57-59] | 2 |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% [100-100] | 2 |

**Mean detection over the 19 injected types (unweighted), test**

| operating point | old | v1same | new |
|---|---|---|---|
| L1 union | 10.9% | 10.9% | 10.4% |
| L2 union | 53.6% | 46.6% | 44.1% |
| L1+L2 union | 54.4% | 47.4% | 44.7% |
| map_road (soft) | 17.3% | 17.3% | 24.8% |
| combined | 54.1% | 47.0% | 45.1% |

**Harness group ablation, AUC / detection at the 1% validation budget / test FA** (old L2 and L1+L2 contain map_road; v1same and new do not)

| group | old | v1same | new |
|---|---|---|---|
| L1 | 0.629 / 18.4% / FA 0.9% | 0.629 / 18.4% / FA 0.9% | 0.671 / 21.1% / FA 0.5% |
| L2 | 0.754 / 52.6% / FA 6.3% | 0.735 / 48.0% / FA 1.3% | 0.764 / 47.2% / FA 1.8% |
| L1+L2 | 0.781 / 53.3% / FA 6.7% | 0.756 / 46.6% / FA 1.3% | 0.798 / 48.7% / FA 1.7% |

**Each layer alone in the S3 harness (AUC / detection at 1% budget / test FA)**

| layer | old | v1same | new |
|---|---|---|---|
| v2x.accel_consistency | 0.624 / 29.6% / 0.7% | 0.624 / 29.6% / 0.7% | 0.672 / 37.3% / 0.7% |
| v2x.beacon_rate | 0.527 / 16.3% / 0.2% | 0.527 / 16.3% / 0.2% | 0.594 / 25.9% / 0.0% |
| v2x.field_ranges | 0.604 / 1.0% / 0.3% | 0.604 / 1.0% / 0.3% | 0.562 / 2.9% / 0.5% |
| v2x.freshness | 0.499 / 1.4% / 1.1% | 0.499 / 1.4% / 1.1% | 0.508 / 0.3% / 0.0% |
| v2x.heading_rate | 0.443 / 2.1% / 0.9% | 0.443 / 2.1% / 0.9% | 0.449 / 9.2% / 2.7% |
| v2x.implied_speed | 0.619 / 34.0% / 0.2% | 0.619 / 34.0% / 0.2% | 0.669 / 39.7% / 0.5% |
| v2x.map_road | 0.572 / 18.3% / 5.5% | - | - |
| v2x.overlap | 0.517 / 3.5% / 0.0% | 0.517 / 3.5% / 0.0% | 0.511 / 2.1% / 0.0% |
| v2x.pos_heading | 0.546 / 18.0% / 0.8% | 0.546 / 18.0% / 0.8% | 0.557 / 26.5% / 1.4% |
| v2x.pos_speed | 0.690 / 39.8% / 0.2% | 0.690 / 39.8% / 0.2% | 0.751 / 43.3% / 0.5% |
| v2x.speed_change | 0.611 / 28.9% / 0.7% | 0.611 / 28.9% / 0.7% | 0.643 / 36.9% / 0.6% |
| v2x.yaw_consistency | 0.511 / 3.4% / 0.6% | 0.511 / 3.4% / 0.6% | 0.541 / 12.2% / 1.2% |

**Leave-one-out (all-but-X) in the S3 harness (AUC / detection)**

| removed | old | v1same | new |
|---|---|---|---|
| all_but_v2x.accel_consistency | 0.781 / 53.1% | 0.757 / 46.6% | 0.796 / 48.6% |
| all_but_v2x.beacon_rate | 0.765 / 52.9% | 0.739 / 46.2% | 0.781 / 47.7% |
| all_but_v2x.field_ranges | 0.776 / 53.1% | 0.739 / 46.6% | 0.789 / 48.1% |
| all_but_v2x.freshness | 0.778 / 53.0% | 0.760 / 46.6% | 0.796 / 48.5% |
| all_but_v2x.heading_rate | 0.782 / 53.2% | 0.758 / 46.7% | 0.807 / 48.6% |
| all_but_v2x.implied_speed | 0.781 / 53.2% | 0.756 / 46.7% | 0.798 / 48.7% |
| all_but_v2x.map_road | 0.756 / 46.6% | - | - |
| all_but_v2x.overlap | 0.770 / 51.7% | 0.744 / 45.1% | 0.790 / 48.5% |
| all_but_v2x.pos_heading | 0.781 / 53.2% | 0.757 / 46.7% | 0.797 / 48.5% |
| all_but_v2x.pos_speed | 0.763 / 50.9% | 0.741 / 44.3% | 0.764 / 47.7% |
| all_but_v2x.speed_change | 0.781 / 53.3% | 0.758 / 46.8% | 0.804 / 48.7% |
| all_but_v2x.yaw_consistency | 0.782 / 53.2% | 0.758 / 46.7% | 0.797 / 48.6% |

**S2 (L1) on Tampa, false alarms on genuine test messages**

| | old | v1same | new |
|---|---|---|---|
| beacon rate FA | 0.2% | 0.2% | 0.0% |
| freshness FA | 1.1% | 1.1% | 0.0% |
| field ranges (budget) FA | 0.3% | 0.3% | 0.5% |
| field ranges (physical) FA | 0.0% | 0.0% | 0.0% |
| L1 union FA | 1.3% | 1.3% | 0.0% |
| S2 combined FA | 0.9% | 0.9% | 0.5% |

**S2 (L1 union) on Tampa, message-level detection per type**

| type | old | v1same | new |
|---|---|---|---|
| 01_ConstPos | 0.6% | 0.6% | 0.0% |
| 02_ConstPosOffset | 1.2% | 1.2% | 0.0% |
| 03_RandomPos | 1.5% | 1.5% | 0.0% |
| 04_RandomPosOffset | 1.7% | 1.7% | 0.0% |
| 05_ConstSpeed | 0.4% | 0.4% | 0.0% |
| 06_ConstSpeedOffset | 0.7% | 0.7% | 0.0% |
| 07_RandomSpeed | 0.3% | 0.3% | 0.0% |
| 08_RandomSpeedOffset | 2.1% | 2.1% | 0.0% |
| 09_EventualStop | 0.3% | 0.3% | 0.0% |
| 10_Disruptive | 0.8% | 0.8% | 0.0% |
| 11_DataReplay | 0.0% | 0.0% | 0.0% |
| 12_DelayedMessages | 0.0% | 0.0% | 0.0% |
| 13_DoS | 5.7% | 5.7% | 5.6% |
| 14_DoSRandom | 94.3% | 94.3% | 96.4% |
| 15_DoSDisruptive | 92.8% | 92.8% | 96.4% |
| 16_GridSybil | 0.6% | 0.6% | 0.0% |
| 17_DataReplaySybil | 1.4% | 1.4% | 0.0% |
| 18_DoSRandomSybil | 1.3% | 1.3% | 0.0% |
| 19_DoSDisruptiveSybil | 1.3% | 1.3% | 0.0% |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% |
