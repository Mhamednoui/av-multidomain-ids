### VeReMi (D12) test

**VeReMi test: message-level detection per class at the 1% genuine-validation budget (L1L2L3_union = deployable baseline, no kf_cusum_lo)**

* = attack type NEVER used in training, hyperparameter choice, threshold or combiner (unseen). L4_* variants: same hyperparameters, refit on train.

| class | L1L2L3_union | L4 | combined_L1+L2+L3 | combined_L1+L2+L3+L4 | L4_A1_no_time_track | L4_A2_residuals_only | L4_no_memory | L4_shuffled_labels |
|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 98.1% | 100.0% | 98.1% | 99.8% | 100.0% | 100.0% | 98.6% | 0.4% |
| 02_ConstPosOffset | 1.0% | 1.0% | 1.0% | 1.4% | 1.0% | 0.9% | 1.0% | 1.1% |
| 03_RandomPos | 99.2% | 100.0% | 99.2% | 99.8% | 100.0% | 100.0% | 100.0% | 11.8% |
| 04_RandomPosOffset | 99.3% | 100.0% | 99.3% | 99.9% | 100.0% | 100.0% | 99.0% | 2.2% |
| 05_ConstSpeed | 99.3% | 100.0% | 99.7% | 100.0% | 100.0% | 100.0% | 99.9% | 3.3% |
| 06_ConstSpeedOffset * | 99.1% | 100.0% | 99.1% | 100.0% | 100.0% | 100.0% | 99.8% | 1.3% |
| 07_RandomSpeed | 99.4% | 100.0% | 99.8% | 100.0% | 100.0% | 100.0% | 100.0% | 1.1% |
| 08_RandomSpeedOffset | 99.1% | 100.0% | 99.1% | 100.0% | 100.0% | 100.0% | 99.8% | 0.5% |
| 09_EventualStop | 1.1% | 79.3% | 1.1% | 79.4% | 79.3% | 79.3% | 79.3% | 0.2% |
| 10_Disruptive | 98.5% | 99.3% | 98.6% | 99.2% | 99.3% | 99.3% | 98.6% | 3.0% |
| 11_DataReplay | 97.8% | 99.3% | 97.8% | 98.8% | 99.1% | 99.1% | 80.2% | 7.7% |
| 12_DelayedMessages * | 48.2% | 100.0% | 48.2% | 99.8% | 100.0% | 100.0% | 53.3% | 11.2% |
| 13_DoS | 99.8% | 100.0% | 99.8% | 100.0% | 100.0% | 100.0% | 100.0% | 1.2% |
| 14_DoSRandom | 99.8% | 100.0% | 99.9% | 100.0% | 100.0% | 100.0% | 100.0% | 7.9% |
| 15_DoSDisruptive | 99.7% | 100.0% | 99.7% | 100.0% | 100.0% | 100.0% | 100.0% | 8.1% |
| 16_GridSybil | 74.5% | 81.1% | 74.5% | 81.0% | 81.1% | 80.5% | 77.3% | 3.8% |
| 17_DataReplaySybil * | 46.4% | 91.9% | 48.9% | 80.5% | 78.6% | 78.1% | 81.1% | 9.5% |
| 18_DoSRandomSybil | 6.3% | 100.0% | 71.8% | 99.8% | 100.0% | 100.0% | 100.0% | 0.0% |
| 19_DoSDisruptiveSybil | 37.3% | 100.0% | 47.4% | 99.9% | 100.0% | 100.0% | 100.0% | 2.3% |
| mean seen (16) | 75.6% | 91.3% | 80.4% | 91.2% | 91.2% | 91.2% | 89.6% | 3.4% |
| mean unseen 6 and 17 | 72.8% | 96.0% | 74.0% | 90.2% | 89.3% | 89.0% | 90.5% | 5.4% |
| mean over 19 | 73.9% | 92.2% | 78.1% | 91.5% | 91.5% | 91.4% | 87.8% | 4.0% |
| FA genuine messages | 1.1% | 1.1% | 1.1% | 1.2% | 1.1% | 1.0% | 1.0% | 1.1% |
| FA genuine senders (>= 1 alarm) | 58.7% | 100.0% | 59.5% | 93.8% | 100.0% | 100.0% | 100.0% | 51.3% |

**VeReMi test: unions and harness combinations (L2L3L4_union = max of calibrated scores at ONE 1% budget)**



| class | L1L2L3_union | L2L3L4_union | L1L2L3L4_union | combined_L1+L2 | combined_L1+L2+L4 | combined_L1+L2+L3 | combined_L1+L2+L3+L4 |
|---|---|---|---|---|---|---|---|
| 01_ConstPos | 98.1% | 99.3% | 99.3% | 86.3% | 99.8% | 98.1% | 99.8% |
| 02_ConstPosOffset | 1.0% | 1.0% | 1.0% | 1.1% | 1.4% | 1.0% | 1.4% |
| 03_RandomPos | 99.2% | 99.2% | 99.2% | 99.1% | 99.8% | 99.2% | 99.8% |
| 04_RandomPosOffset | 99.3% | 99.4% | 99.4% | 97.3% | 99.9% | 99.3% | 99.9% |
| 05_ConstSpeed | 99.3% | 99.4% | 99.4% | 96.7% | 100.0% | 99.7% | 100.0% |
| 06_ConstSpeedOffset * | 99.1% | 99.3% | 99.3% | 85.2% | 99.9% | 99.1% | 100.0% |
| 07_RandomSpeed | 99.4% | 99.4% | 99.4% | 99.4% | 100.0% | 99.8% | 100.0% |
| 08_RandomSpeedOffset | 99.1% | 99.3% | 99.3% | 94.8% | 99.9% | 99.1% | 100.0% |
| 09_EventualStop | 1.1% | 78.6% | 78.6% | 1.1% | 79.4% | 1.1% | 79.4% |
| 10_Disruptive | 98.5% | 99.0% | 99.0% | 97.0% | 99.2% | 98.6% | 99.2% |
| 11_DataReplay | 97.8% | 98.5% | 98.5% | 68.3% | 98.9% | 97.8% | 98.8% |
| 12_DelayedMessages * | 48.2% | 99.2% | 99.2% | 1.4% | 99.8% | 48.2% | 99.8% |
| 13_DoS | 99.8% | 99.8% | 99.8% | 99.7% | 100.0% | 99.8% | 100.0% |
| 14_DoSRandom | 99.8% | 99.8% | 99.8% | 99.9% | 100.0% | 99.9% | 100.0% |
| 15_DoSDisruptive | 99.7% | 99.9% | 99.9% | 99.7% | 100.0% | 99.7% | 100.0% |
| 16_GridSybil | 74.5% | 80.1% | 80.1% | 61.4% | 81.2% | 74.5% | 81.0% |
| 17_DataReplaySybil * | 46.4% | 63.1% | 63.1% | 20.8% | 83.3% | 48.9% | 80.5% |
| 18_DoSRandomSybil | 6.3% | 68.4% | 68.4% | 70.0% | 99.7% | 71.8% | 99.8% |
| 19_DoSDisruptiveSybil | 37.3% | 95.5% | 95.5% | 13.1% | 99.9% | 47.4% | 99.9% |
| mean over 19 | 73.9% | 88.3% | 88.3% | 68.0% | 91.7% | 78.1% | 91.5% |
| FA genuine messages | 1.1% | 1.1% | 1.1% | 1.0% | 1.3% | 1.1% | 1.2% |

**VeReMi test: L4 vs deployable baseline with attacker-bootstrap CIs**

| class | L4 detection [95% CI, attacker bootstrap] | deployable L1L2L3_union [95% CI] | n attackers | L4 sender >= 3 alarms | L4 median delay (s) |
|---|---|---|---|---|---|
| 01_ConstPos | 100.0% [100.0%, 100.0%] | 98.1% [97.6%, 98.6%] | 89 | 98.9% | 0.0 |
| 02_ConstPosOffset | 1.0% [0.9%, 1.1%] | 1.0% [0.7%, 1.3%] | 90 | 2.2% | 0.0 |
| 03_RandomPos | 100.0% [100.0%, 100.0%] | 99.2% [99.1%, 99.3%] | 90 | 98.9% | 0.0 |
| 04_RandomPosOffset | 100.0% [100.0%, 100.0%] | 99.3% [99.2%, 99.4%] | 89 | 100.0% | 0.0 |
| 05_ConstSpeed | 100.0% [100.0%, 100.0%] | 99.3% [99.1%, 99.4%] | 86 | 100.0% | 0.0 |
| 06_ConstSpeedOffset * | 100.0% [99.9%, 100.0%] | 99.1% [98.9%, 99.3%] | 85 | 100.0% | 0.0 |
| 07_RandomSpeed | 100.0% [100.0%, 100.0%] | 99.4% [99.3%, 99.5%] | 90 | 100.0% | 0.0 |
| 08_RandomSpeedOffset | 100.0% [100.0%, 100.0%] | 99.1% [99.0%, 99.3%] | 86 | 100.0% | 0.0 |
| 09_EventualStop | 79.3% [73.7%, 84.1%] | 1.1% [1.0%, 1.3%] | 87 | 83.9% | 0.0 |
| 10_Disruptive | 99.3% [98.2%, 100.0%] | 98.5% [97.5%, 99.3%] | 89 | 98.9% | 0.0 |
| 11_DataReplay | 99.3% [99.0%, 99.6%] | 97.8% [97.3%, 98.2%] | 83 | 98.8% | 0.0 |
| 12_DelayedMessages * | 100.0% [100.0%, 100.0%] | 48.2% [43.0%, 52.9%] | 87 | 100.0% | 0.0 |
| 13_DoS | 100.0% [100.0%, 100.0%] | 99.8% [99.7%, 99.8%] | 88 | 100.0% | 0.0 |
| 14_DoSRandom | 100.0% [100.0%, 100.0%] | 99.8% [99.7%, 99.8%] | 87 | 100.0% | 0.0 |
| 15_DoSDisruptive | 100.0% [100.0%, 100.0%] | 99.7% [99.7%, 99.8%] | 87 | 100.0% | 0.0 |
| 16_GridSybil | 81.1% [78.7%, 83.2%] | 74.5% [71.3%, 76.8%] | 87 | 98.9% | 0.0 |
| 17_DataReplaySybil * | 91.9% [90.3%, 93.4%] | 46.4% [42.5%, 50.0%] | 85 | 98.8% | 0.0 |
| 18_DoSRandomSybil | 100.0% [100.0%, 100.0%] | 6.3% [5.4%, 7.4%] | 89 | 100.0% | 0.0 |
| 19_DoSDisruptiveSybil | 100.0% [100.0%, 100.0%] | 37.3% [33.8%, 41.5%] | 86 | 100.0% | 0.0 |

**VeReMi test, harness group ablation (all attacks pooled; combiner chosen on validation)**

| group | method | AUC | detection (all attacks) | false alarms | median delay |
|---|---|---|---|---|---|
| L1+L2 | max | 0.845 | 72.4% | 0.98% | 0.0 |
| L1+L2+L3 | max | 0.893 | 81.1% | 1.07% | 0.0 |
| L1+L2+L4 | logistic | 0.968 | 92.7% | 1.28% | 0.0 |
| L1+L2+L3+L4 | logistic | 0.968 | 92.6% | 1.22% | 0.0 |
| L4 | single layer | 0.968 | 93.1% | 1.08% | 0.0 |

**Leakage checks: feature-set ablations and shuffled-label control**

| variant | n features | val AUC | test AUC | val FA | test FA (genuine msgs) | test detection (all attacks pooled) |
|---|---|---|---|---|---|---|
| full | 27 | 0.975 | 0.968 | 1.0% | 1.1% | 93.1% |
| A1_no_time_track | 25 | 0.974 | 0.967 | 1.0% | 1.1% | 92.6% |
| A2_residuals_only | 20 | 0.970 | 0.965 | 1.0% | 1.0% | 92.5% |
| no_memory | 15 | 0.971 | 0.958 | 1.0% | 1.0% | 89.9% |
| shuffled_labels | 27 | 0.461 | 0.475 | 1.0% | 1.1% | 4.1% |

**Gain importance of the final model (top 15)**

| feature | share of total gain | single-feature test AUC (information) |
|---|---|---|
| cusum_hi | 55.5% | 0.829 |
| implied_speed | 12.7% | 0.519 |
| w_pos_speed_mean | 12.2% | 0.751 |
| pos_speed | 8.5% | 0.737 |
| nis | 3.9% | 0.737 |
| w_pos_speed_max | 3.7% | 0.750 |
| rate | 0.8% | 0.586 |
| w_rate_max | 0.4% | 0.594 |
| track_birth_density | 0.3% | - |
| w_nis_mean | 0.3% | - |
| dt_prev | 0.2% | - |
| w_implied_speed_max | 0.2% | - |
| birth_density | 0.2% | - |
| accel_consistency | 0.2% | - |
| w_nis_max | 0.2% | - |

**Class 12 (DelayedMessages, held out): the zero-placeholder artefact**

| operating point | all class-12 rows | zero-placeholder rows (x = y = 0) | rows after the jump |
|---|---|---|---|
| L1L2L3_union | 48.2% | 0.2% | 100.0% |
| L4 | 100.0% | 100.0% | 100.0% |
| L4_no_memory | 53.3% | 100.0% | 2.8% |
| L4_A2_residuals_only | 100.0% | 100.0% | 100.0% |
| combined_L1+L2+L3 | 48.2% | 0.2% | 100.0% |
| combined_L1+L2+L3+L4 | 99.8% | 99.5% | 100.0% |
| rows | 9421 | 4888 | 4533 |

**VeReMi test: false alarms on genuine test messages and senders**

| operating point | genuine messages | genuine senders with >= 1 alarm |
|---|---|---|
| L1L2L3_union | 1.1% | 58.7% |
| L4 | 1.1% | 100.0% |
| combined_L1+L2+L3 | 1.1% | 59.5% |
| combined_L1+L2+L3+L4 | 1.2% | 93.8% |
| L4_A1_no_time_track | 1.1% | 100.0% |
| L4_A2_residuals_only | 1.0% | 100.0% |
| L4_no_memory | 1.0% | 100.0% |
| L4_shuffled_labels | 1.1% | 51.3% |

### Tampa (injected on real BSMs) test: ILLUSTRATION

**Tampa test (illustration: 3 vehicles, 2 attackers per type, no statistics): message-level detection, VeReMi-trained L4 applied unchanged**

@veremi_thr = threshold of VeReMi validation (no Tampa data used); @tampa_val_thr = 1% of genuine Tampa validation messages. * = type unseen by L4 (and by every other layer calibration).

| class | L1L2L3_union | combined_L1+L2+L3 | combined_L1+L2+L3+L4 | L4_full@veremi_thr | L4_full@tampa_val_thr | L4_A1_no_time_track@tampa_val_thr | L4_A2_residuals_only@veremi_thr | L4_A2_residuals_only@tampa_val_thr | L4_shuffled_labels@tampa_val_thr |
|---|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 99.7% | 99.7% | 99.7% | 100.0% | 99.7% | 99.8% | 100.0% | 99.8% | 29.0% |
| 02_ConstPosOffset | 3.4% | 3.3% | 3.3% | 100.0% | 0.2% | 1.7% | 19.9% | 0.0% | 1.3% |
| 03_RandomPos | 99.8% | 99.8% | 99.8% | 100.0% | 99.8% | 99.8% | 100.0% | 99.8% | 38.8% |
| 04_RandomPosOffset | 99.7% | 99.7% | 99.7% | 100.0% | 99.7% | 99.7% | 100.0% | 99.7% | 57.8% |
| 05_ConstSpeed | 98.9% | 98.8% | 98.8% | 100.0% | 98.2% | 98.0% | 99.3% | 97.3% | 27.7% |
| 06_ConstSpeedOffset * | 99.0% | 99.2% | 99.2% | 100.0% | 97.4% | 97.7% | 99.1% | 97.2% | 20.0% |
| 07_RandomSpeed | 99.8% | 99.8% | 99.8% | 100.0% | 99.7% | 99.8% | 100.0% | 99.8% | 49.8% |
| 08_RandomSpeedOffset | 99.9% | 99.9% | 99.9% | 100.0% | 99.4% | 99.5% | 100.0% | 99.3% | 23.7% |
| 09_EventualStop | 0.1% | 0.1% | 0.7% | 100.0% | 99.7% | 99.8% | 100.0% | 3.3% | 0.8% |
| 10_Disruptive | 99.9% | 99.9% | 99.9% | 100.0% | 99.9% | 99.9% | 100.0% | 99.9% | 36.0% |
| 11_DataReplay | 98.9% | 98.9% | 98.9% | 100.0% | 95.3% | 95.2% | 97.4% | 95.0% | 9.5% |
| 12_DelayedMessages * | 55.0% | 54.9% | 55.0% | 100.0% | 55.8% | 59.9% | 72.8% | 53.5% | 1.9% |
| 13_DoS | 9.9% | 8.8% | 8.8% | 100.0% | 3.7% | 5.2% | 41.7% | 0.0% | 21.5% |
| 14_DoSRandom | 99.9% | 99.9% | 99.9% | 100.0% | 99.9% | 99.9% | 100.0% | 99.9% | 55.2% |
| 15_DoSDisruptive | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 27.8% |
| 16_GridSybil | 33.7% | 33.7% | 33.7% | 99.9% | 25.2% | 26.9% | 43.2% | 24.6% | 1.3% |
| 17_DataReplaySybil * | 29.3% | 29.2% | 29.2% | 99.8% | 12.8% | 15.2% | 29.9% | 12.5% | 5.7% |
| 18_DoSRandomSybil | 63.1% | 66.8% | 96.5% | 100.0% | 94.2% | 90.7% | 100.0% | 90.6% | 54.6% |
| 19_DoSDisruptiveSybil | 64.3% | 63.0% | 96.4% | 100.0% | 93.9% | 91.4% | 99.9% | 89.8% | 54.1% |
| S20_StaleReplay | 100.0% | 100.0% | 100.0% | 100.0% | 0.0% | 0.0% | 100.0% | 0.0% | 1.5% |
| mean over 19 | 71.3% | 71.3% | 74.7% | 100.0% | 77.6% | 77.9% | 84.4% | 71.7% | 27.2% |
| FA genuine messages | 3.0% | 2.8% | 2.8% | 100.0% | 0.3% | 1.4% | 16.2% | 0.0% | 1.1% |
| FA 95% CI (vehicle bootstrap) | [0.2%, 6.0%] | [0.1%, 6.0%] | [0.1%, 6.0%] | [100.0%, 100.0%] | [0.2%, 0.5%] | [0.1%, 2.7%] | [6.8%, 24.2%] | [0.0%, 0.0%] | [0.5%, 1.9%] |

**Tampa: transfer of the VeReMi-trained models**

| model | VeReMi threshold (p) | Tampa val threshold (p) | Tampa val FA at VeReMi threshold | Tampa test AUC | median p genuine | median p attack |
|---|---|---|---|---|---|---|
| full | 0.220 | 0.998 | 100.0% | 0.904 | 0.980 | 1.000 |
| A1_no_time_track | 0.203 | 0.997 | 100.0% | 0.878 | 0.980 | 1.000 |
| A2_residuals_only | 0.238 | 0.996 | 22.9% | 0.882 | 0.056 | 1.000 |
| no_memory | 0.590 | 1.000 | 99.5% | 0.855 | 0.995 | 1.000 |
| shuffled_labels | 0.396 | 0.389 | 0.4% | 0.736 | 0.339 | 0.366 |

**Tampa test, harness group ablation (combiner fitted on Tampa validation, as in S4)**

| group | method | AUC | detection (all attacks) | false alarms |
|---|---|---|---|---|
| L1+L2+L3 | max | 0.854 | 69.2% | 2.82% |
| L1+L2+L3+L4 | max | 0.891 | 72.2% | 2.82% |
