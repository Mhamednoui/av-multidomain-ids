### VeReMi (primary)

**Noise fit** (genuine TRAIN only): sp = 0.050 m, sv = 0.020 m/s, sa = 1.937 m/s^2/sqrt(s); 800 tracks, 72964 messages, 800 senders; neg. log-lik/message 2.175; floors SP_MIN 0.05, SV_MIN 0.02 (a value equal to a floor means the data wanted less).

**Filter consistency on genuine data** (NIS, dim 4: expected mean 4, median 3.36, above chi2 95% = 5%, below chi2 5% = 5%)

| set | n scored | NIS mean | NIS median | above 95% | below 5% | q99 (chi2: 13.3) |
|---|---|---|---|---|---|---|
| val all_genuine | 159940 | 4.15 | 0.194 | 7.0% | 61.2% | 86.3 |
| val moving_ge_3mps | 134445 | 4.84 | 0.310 | 8.3% | 56.2% | 99.2 |
| val slow_lt_3mps | 25495 | 0.52 | 0.053 | 0.5% | 87.9% | 5.7 |
| test all_genuine | 420555 | 3.87 | 0.201 | 6.7% | 61.1% | 75.1 |
| test moving_ge_3mps | 353875 | 4.50 | 0.321 | 7.9% | 56.1% | 89.6 |
| test slow_lt_3mps | 66680 | 0.52 | 0.056 | 0.5% | 87.6% | 5.7 |

**VeReMi (primary): message-level detection at 1% validation budget, per class**

L3_union = max of the 4 calibrated L3 scores at one 1% budget; L1_and_L2_union = S3 deployable union; L1_L2_L3_union = L1 operating points OR (L2 + L3 at one budget); combined_* = harness combiner. * = held out.

| class | v2x.kf_nis | v2x.kf_cusum_hi | v2x.kf_cusum_lo | v2x.track_birth | L3_union | L1_and_L2_union | L1_L2_L3_union | combined_L1+L2 | combined_L1+L2+L3 |
|---|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 79.6% | 95.1% | 0.0% | 0.4% | 95.9% | 86.4% | 98.1% | 86.3% | 98.1% |
| 02_ConstPosOffset | 0.9% | 0.9% | 1.3% | 0.8% | 1.0% | 1.3% | 0.9% | 1.1% | 0.9% |
| 03_RandomPos | 99.1% | 99.1% | 0.0% | 0.5% | 99.3% | 99.1% | 99.2% | 99.1% | 99.2% |
| 04_RandomPosOffset | 97.4% | 99.1% | 0.0% | 0.7% | 99.5% | 97.4% | 99.3% | 97.3% | 99.3% |
| 05_ConstSpeed | 97.9% | 98.9% | 0.0% | 0.9% | 99.4% | 96.1% | 99.3% | 96.7% | 99.7% |
| 06_ConstSpeedOffset * | 96.5% | 97.8% | 0.0% | 0.7% | 98.6% | 85.6% | 99.1% | 85.2% | 99.1% |
| 07_RandomSpeed | 99.0% | 99.2% | 0.0% | 0.7% | 99.5% | 98.9% | 99.4% | 99.4% | 99.8% |
| 08_RandomSpeedOffset | 94.8% | 97.2% | 0.0% | 0.7% | 97.9% | 94.9% | 99.1% | 94.8% | 99.1% |
| 09_EventualStop | 0.6% | 0.1% | 18.7% | 0.7% | 11.4% | 1.1% | 8.7% | 1.1% | 8.3% |
| 10_Disruptive | 96.3% | 98.1% | 0.0% | 0.6% | 98.5% | 97.0% | 98.5% | 97.0% | 98.6% |
| 11_DataReplay | 67.5% | 97.2% | 0.0% | 0.7% | 97.6% | 68.4% | 97.8% | 68.3% | 97.7% |
| 12_DelayedMessages * | 1.6% | 48.1% | 0.0% | 0.7% | 48.3% | 1.4% | 48.2% | 1.4% | 48.2% |
| 13_DoS | 79.4% | 98.2% | 0.3% | 0.3% | 98.3% | 99.7% | 99.8% | 99.7% | 99.8% |
| 14_DoSRandom | 99.7% | 99.7% | 0.0% | 0.2% | 99.8% | 99.7% | 99.8% | 99.9% | 99.9% |
| 15_DoSDisruptive | 99.3% | 99.5% | 0.0% | 0.2% | 99.7% | 99.7% | 99.7% | 99.7% | 99.7% |
| 16_GridSybil | 57.9% | 72.3% | 0.1% | 1.0% | 73.3% | 61.5% | 74.4% | 61.4% | 74.4% |
| 17_DataReplaySybil * | 14.2% | 11.7% | 0.0% | 48.8% | 52.7% | 17.4% | 46.4% | 20.8% | 48.8% |
| 18_DoSRandomSybil | 0.0% | 0.0% | 0.0% | 38.4% | 15.9% | 0.0% | 6.3% | 70.0% | 71.8% |
| 19_DoSDisruptiveSybil | 0.3% | 0.2% | 0.0% | 42.8% | 39.3% | 1.5% | 37.2% | 13.1% | 47.3% |
| mean over the 19 classes | 62.2% | 69.1% | 1.1% | 7.4% | 75.0% | 63.5% | 74.3% | 68.0% | 78.4% |

**VeReMi (primary): sender level, attackers with >= 3 alarms** (genuine senders with >= 3 alarms in the last row)

| class | L2_union | L3_union | L1_and_L2_union | L1_L2_L3_union |
|---|---|---|---|---|
| 01_ConstPos | 98.9% | 97.8% | 98.9% | 97.8% |
| 02_ConstPosOffset | 16.7% | 3.3% | 16.7% | 10.0% |
| 03_RandomPos | 98.9% | 98.9% | 98.9% | 98.9% |
| 04_RandomPosOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 05_ConstSpeed | 98.8% | 100.0% | 98.8% | 98.8% |
| 06_ConstSpeedOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 07_RandomSpeed | 98.9% | 100.0% | 98.9% | 98.9% |
| 08_RandomSpeedOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 09_EventualStop | 8.0% | 33.3% | 8.0% | 31.0% |
| 10_Disruptive | 98.9% | 98.9% | 98.9% | 98.9% |
| 11_DataReplay | 98.8% | 98.8% | 98.8% | 98.8% |
| 12_DelayedMessages | 14.9% | 77.0% | 14.9% | 77.0% |
| 13_DoS | 100.0% | 100.0% | 100.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% | 100.0% | 100.0% |
| 16_GridSybil | 98.9% | 98.9% | 98.9% | 98.9% |
| 17_DataReplaySybil | 92.9% | 97.6% | 92.9% | 97.6% |
| 18_DoSRandomSybil | 0.0% | 97.8% | 0.0% | 89.9% |
| 19_DoSDisruptiveSybil | 36.0% | 100.0% | 37.2% | 100.0% |
| genuine senders >= 3 alarms | 10.7% | 2.9% | 10.7% | 9.5% |

**VeReMi (primary): false alarms on genuine TEST messages** (budget on validation 1%)

| operating point | genuine test messages | genuine senders >= 1 alarm |
|---|---|---|
| v2x.kf_nis | 0.9% | 52.3% |
| v2x.kf_cusum_hi | 0.6% | 2.3% |
| v2x.kf_cusum_lo | 0.7% | 3.4% |
| v2x.track_birth | 0.7% | 80.8% |
| L3_kf_union | 0.8% | 24.1% |
| L3_union | 0.9% | 50.9% |
| L2_union | 1.0% | 54.0% |
| L1_and_L2_union | 1.0% | 54.0% |
| L1_L2_L3_union | 1.1% | 56.8% |
| combined_L1+L2 | 1.0% | 54.4% |
| combined_L1+L2+L3 | 1.1% | 57.7% |

track_birth false alarms per genuine birth (first message of a genuine track): val 61.6% of 1486, test 80.8% of 3873.

**VeReMi (primary): harness group ablation** (combiner chosen on validation per group)

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | noisy_or | 0.695 | 45.1% | 0.99% |
| L2 | logistic | 0.800 | 67.1% | 1.19% |
| L3 | logistic | 0.843 | 78.7% | 1.01% |
| L1+L2 | max | 0.845 | 72.4% | 0.98% |
| L1+L2+L3 | max | 0.907 | 81.3% | 1.08% |

**VeReMi (primary): harness, each layer alone and all-but-one (AUC / detection / false alarms)**

| configuration | AUC | detection | false alarms |
|---|---|---|---|
| all | 0.907 | 81.3% | 1.08% |
| only_v2x.kf_cusum_hi | 0.829 | 71.2% | 0.59% |
| only_v2x.kf_cusum_lo | 0.127 | 0.7% | 0.75% |
| only_v2x.kf_nis | 0.737 | 64.1% | 0.87% |
| only_v2x.track_birth | 0.533 | 7.3% | 0.74% |
| all_but_v2x.kf_cusum_hi | 0.888 | 76.3% | 1.09% |
| all_but_v2x.kf_cusum_lo | 0.893 | 81.1% | 1.07% |
| all_but_v2x.kf_nis | 0.907 | 81.3% | 1.08% |
| all_but_v2x.track_birth | 0.877 | 78.0% | 0.95% |

### Tampa (illustration: 3 test vehicles, 2 attackers per type)

**Noise fit** (genuine TRAIN only): sp = 0.366 m, sv = 0.020 m/s, sa = 1.160 m/s^2/sqrt(s); 37 tracks, 3069 messages, 22 senders; neg. log-lik/message -1.621; floors SP_MIN 0.05, SV_MIN 0.02 (a value equal to a floor means the data wanted less).

**Filter consistency on genuine data** (NIS, dim 4: expected mean 4, median 3.36, above chi2 95% = 5%, below chi2 5% = 5%)

| set | n scored | NIS mean | NIS median | above 95% | below 5% | q99 (chi2: 13.3) |
|---|---|---|---|---|---|---|
| val all_genuine | 2084 | 2.10 | 0.512 | 5.0% | 55.6% | 22.7 |
| val moving_ge_3mps | 1568 | 2.56 | 0.628 | 6.7% | 51.9% | 27.2 |
| val slow_lt_3mps | 516 | 0.68 | 0.341 | 0.0% | 66.9% | 2.6 |
| test all_genuine | 4216 | 1.93 | 0.609 | 3.3% | 53.5% | 17.0 |
| test moving_ge_3mps | 3004 | 2.54 | 1.015 | 4.6% | 40.9% | 21.0 |
| test slow_lt_3mps | 1212 | 0.44 | 0.110 | 0.0% | 84.6% | 4.5 |

**Tampa (illustration: 3 test vehicles, 2 attackers per type): message-level detection at 1% validation budget, per class**

L3_union = max of the 4 calibrated L3 scores at one 1% budget; L1_and_L2_union = S3 deployable union; L1_L2_L3_union = L1 operating points OR (L2 + L3 at one budget); combined_* = harness combiner. * = held out.

| class | v2x.kf_nis | v2x.kf_cusum_hi | v2x.kf_cusum_lo | v2x.track_birth | L3_union | L1_and_L2_union | L1_L2_L3_union | combined_L1+L2 | combined_L1+L2+L3 |
|---|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 77.2% | 99.4% | 0.0% | 0.0% | 99.7% | 10.4% | 99.7% | 8.9% | 99.7% |
| 02_ConstPosOffset | 1.1% | 3.1% | 23.2% | 0.0% | 25.5% | 1.1% | 25.7% | 1.0% | 25.6% |
| 03_RandomPos | 99.8% | 99.8% | 0.0% | 0.0% | 99.8% | 99.8% | 99.8% | 99.8% | 99.8% |
| 04_RandomPosOffset | 99.7% | 99.7% | 0.0% | 0.0% | 99.7% | 99.7% | 99.7% | 99.7% | 99.7% |
| 05_ConstSpeed | 99.2% | 98.4% | 0.0% | 0.0% | 99.0% | 3.5% | 98.9% | 3.3% | 98.8% |
| 06_ConstSpeedOffset * | 99.1% | 98.4% | 0.0% | 0.0% | 99.1% | 3.5% | 99.0% | 14.8% | 99.2% |
| 07_RandomSpeed | 99.0% | 99.8% | 0.0% | 0.0% | 99.8% | 96.0% | 99.8% | 96.3% | 99.8% |
| 08_RandomSpeedOffset | 99.6% | 99.8% | 0.0% | 0.0% | 99.8% | 86.7% | 99.9% | 86.6% | 99.9% |
| 09_EventualStop | 0.1% | 1.2% | 64.2% | 0.0% | 63.3% | 0.1% | 62.8% | 0.1% | 62.7% |
| 10_Disruptive | 99.9% | 99.9% | 0.0% | 0.0% | 99.9% | 97.7% | 99.9% | 97.7% | 99.9% |
| 11_DataReplay | 70.2% | 99.1% | 0.0% | 0.0% | 99.1% | 8.1% | 98.9% | 7.9% | 98.9% |
| 12_DelayedMessages * | 12.8% | 53.2% | 0.0% | 0.0% | 53.8% | 6.1% | 55.0% | 5.1% | 54.9% |
| 13_DoS | 0.1% | 0.0% | 0.0% | 0.0% | 0.0% | 10.9% | 9.9% | 9.9% | 8.8% |
| 14_DoSRandom | 97.9% | 97.9% | 0.0% | 0.0% | 97.9% | 99.9% | 99.9% | 99.9% | 99.9% |
| 15_DoSDisruptive | 98.1% | 98.1% | 0.0% | 0.0% | 98.1% | 99.8% | 100.0% | 99.8% | 100.0% |
| 16_GridSybil | 9.2% | 34.2% | 6.9% | 0.1% | 40.2% | 2.1% | 39.9% | 1.9% | 39.8% |
| 17_DataReplaySybil * | 26.5% | 32.7% | 0.0% | 0.9% | 32.7% | 5.1% | 29.3% | 5.1% | 29.2% |
| 18_DoSRandomSybil | 57.7% | 57.7% | 0.0% | 5.3% | 63.0% | 57.8% | 63.1% | 61.8% | 66.8% |
| 19_DoSDisruptiveSybil | 53.5% | 53.6% | 0.0% | 5.6% | 59.6% | 60.2% | 64.3% | 57.4% | 63.0% |
| S20_StaleReplay | 0.0% | 0.0% | 0.0% | 97.0% | 97.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| mean over the 19 classes | 63.2% | 69.8% | 5.0% | 0.6% | 75.3% | 44.7% | 76.1% | 45.1% | 76.1% |

**Tampa (illustration: 3 test vehicles, 2 attackers per type): sender level, attackers with >= 3 alarms** (genuine senders with >= 3 alarms in the last row)

| class | L2_union | L3_union | L1_and_L2_union | L1_L2_L3_union |
|---|---|---|---|---|
| 01_ConstPos | 100.0% | 100.0% | 100.0% | 100.0% |
| 02_ConstPosOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 03_RandomPos | 100.0% | 100.0% | 100.0% | 100.0% |
| 04_RandomPosOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 05_ConstSpeed | 100.0% | 100.0% | 100.0% | 100.0% |
| 06_ConstSpeedOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 07_RandomSpeed | 100.0% | 100.0% | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 100.0% | 100.0% | 100.0% | 100.0% |
| 09_EventualStop | 0.0% | 100.0% | 0.0% | 100.0% |
| 10_Disruptive | 100.0% | 100.0% | 100.0% | 100.0% |
| 11_DataReplay | 100.0% | 100.0% | 100.0% | 100.0% |
| 12_DelayedMessages | 100.0% | 100.0% | 100.0% | 100.0% |
| 13_DoS | 100.0% | 0.0% | 100.0% | 100.0% |
| 14_DoSRandom | 100.0% | 100.0% | 100.0% | 100.0% |
| 15_DoSDisruptive | 100.0% | 100.0% | 100.0% | 100.0% |
| 16_GridSybil | 100.0% | 100.0% | 100.0% | 100.0% |
| 17_DataReplaySybil | 100.0% | 100.0% | 100.0% | 100.0% |
| 18_DoSRandomSybil | 100.0% | 100.0% | 100.0% | 100.0% |
| 19_DoSDisruptiveSybil | 100.0% | 100.0% | 100.0% | 100.0% |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% | 100.0% |
| genuine senders >= 3 alarms | 75.0% | 50.0% | 75.0% | 75.0% |

**Tampa (illustration: 3 test vehicles, 2 attackers per type): false alarms on genuine TEST messages** (budget on validation 1%)

| operating point | genuine test messages | genuine senders >= 1 alarm |
|---|---|---|
| v2x.kf_nis | 0.6% | 25.0% |
| v2x.kf_cusum_hi | 1.8% | 25.0% |
| v2x.kf_cusum_lo | 13.5% | 25.0% |
| v2x.track_birth | 0.0% | 0.0% |
| L3_kf_union | 14.8% | 50.0% |
| L3_union | 14.8% | 50.0% |
| L2_union | 1.8% | 100.0% |
| L1_and_L2_union | 1.8% | 100.0% |
| L1_L2_L3_union | 16.0% | 100.0% |
| combined_L1+L2 | 1.7% | 100.0% |
| combined_L1+L2+L3 | 15.8% | 75.0% |

**Tampa (illustration: 3 test vehicles, 2 attackers per type): harness group ablation** (combiner chosen on validation per group)

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1 | logistic | 0.671 | 21.1% | 0.47% |
| L2 | max | 0.764 | 47.2% | 1.82% |
| L3 | noisy_or | 0.794 | 70.5% | 13.18% |
| L1+L2 | max | 0.798 | 48.7% | 1.66% |
| L1+L2+L3 | max | 0.852 | 72.2% | 15.79% |

**Tampa (illustration: 3 test vehicles, 2 attackers per type): harness, each layer alone and all-but-one (AUC / detection / false alarms)**

| configuration | AUC | detection | false alarms |
|---|---|---|---|
| all | 0.852 | 72.2% | 15.79% |
| only_v2x.kf_cusum_hi | 0.834 | 67.0% | 1.78% |
| only_v2x.kf_cusum_lo | 0.174 | 3.2% | 13.49% |
| only_v2x.kf_nis | 0.747 | 59.1% | 0.62% |
| only_v2x.track_birth | 0.504 | 0.8% | 0.00% |
| all_but_v2x.kf_cusum_hi | 0.811 | 63.3% | 14.39% |
| all_but_v2x.kf_cusum_lo | 0.854 | 69.2% | 2.82% |
| all_but_v2x.kf_nis | 0.854 | 72.1% | 15.79% |
| all_but_v2x.track_birth | 0.848 | 71.7% | 15.79% |

**VeReMi test: track length of the attackers** (why the tracker cannot see classes 17 / 18 / 19)

| class | median messages per track | tracks with one message |
|---|---|---|
| 16_GridSybil | 80 | 0.9% |
| 17_DataReplaySybil | 1 | 54.5% |
| 18_DoSRandomSybil | 2 | 24.7% |
| 19_DoSDisruptiveSybil | 2 | 30.5% |
| 12_DelayedMessages | 101 | 0.0% |
| 09_EventualStop | 105 | 0.0% |

**Diagnostics on VeReMi VALIDATION** (tools/WP5_S4_diag.py)

| class | cusum_hi alarm (val q99 of genuine) | alarms whose own NIS is below chi2 95% (memory of an earlier jump) | messages with own NIS above chi2 95% |
|---|---|---|---|
| 00_Genuine | 1.0% | 86.6% | 7.0% |
| 02_ConstPosOffset | 0.0% | - | 6.9% |
| 09_EventualStop | 1.1% | 90.5% | 2.2% |
| 11_DataReplay | 95.7% | 17.4% | 80.1% |
| 12_DelayedMessages | 50.6% | 89.8% | 5.2% |
| 13_DoS | 98.2% | 10.0% | 89.9% |
| 16_GridSybil | 65.7% | 17.7% | 60.2% |
| 17_DataReplaySybil | 17.7% | 12.5% | 39.6% |

Class 12 as it appears in the CSV: 49.4% of the messages are exactly (0, 0) with speed 0, 93.8% of the tracks go from the origin to real positions.

Standstill pairs on VeReMi val: genuine 0.0% have an exactly repeated position (median displacement 0.10 m); EventualStop 98.8%.
