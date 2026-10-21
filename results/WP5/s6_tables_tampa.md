### Tampa (injected on real BSMs): ILLUSTRATION, 3 test vehicles, no CIs (test)

Frozen VeReMi-trained scored-row L4, Tampa tracker and layer calibrations, thresholds = 1% of Tampa genuine validation messages. Combiner: max (parameter-free; VeReMi chose max). Layers: beacon_rate, field_ranges, freshness, pos_speed, pos_heading, speed_change, implied_speed, heading_rate, accel_consistency, overlap, kf_nis, kf_cusum_hi, track_birth, l4_scored.

| configuration | FA msgs | FA scored msgs | scored: mean seen | scored: 6* | scored: 17* | sender>=3: mean seen | all rows: mean 19 | AUC scored |
|---|---|---|---|---|---|---|---|---|
| L1 | 0.5% | 0.5% | 16.0% | 12.6% | 0.0% | 68.8% | 16.9% | 0.694 |
| L2 | 1.9% | 2.2% | 64.3% | 3.6% | 5.2% | 93.8% | 44.7% | 0.823 |
| L3 | 1.8% | 2.0% | 81.2% | 99.3% | 33.4% | 87.5% | 71.8% | 0.857 |
| L4-scored | 0.1% | 0.1% | 80.2% | 97.9% | 16.5% | 78.1% | 56.7% | 0.871 |
| L1+L2+L3+L4 | 2.8% | 3.2% | 81.8% | 99.4% | 29.0% | 90.6% | 72.8% | 0.890 |
| all but L1 | 3.0% | 3.4% | 81.8% | 99.2% | 29.2% | 90.6% | 72.1% | 0.879 |
| all but L2 | 2.0% | 2.2% | 81.5% | 99.4% | 31.2% | 90.6% | 72.6% | 0.897 |
| all but L3 | 1.6% | 1.8% | 80.6% | 98.3% | 14.8% | 90.6% | 64.8% | 0.879 |
| all but L4 (= L1+L2+L3) | 3.0% | 3.4% | 81.7% | 99.4% | 29.1% | 90.6% | 72.9% | 0.891 |

**Per class, message level, scored rows / all rows (full stack vs L1+L2+L3 and each layer alone)**

| class | scored share | L1 | L2 | L3 | L4-scored | L1+L2+L3+L4 | all but L1 | all but L2 | all but L3 | all but L4 (= L1+L2+L3) |
|---|---|---|---|---|---|---|---|---|---|---|
| 01_ConstPos | 0.0% | (0.6% all) | (10.5% all) | (99.7% all) | (0.0% all) | (99.7% all) | (99.7% all) | (99.7% all) | (8.8% all) | (99.7% all) |
| 02_ConstPosOffset | 85.2% | 0.7% | 1.1% | 3.6% | 0.2% | 3.9% | 3.9% | 3.7% | 1.1% | 3.9% |
| 03_RandomPos | 99.8% | 0.6% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 04_RandomPosOffset | 99.7% | 0.3% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 05_ConstSpeed | 99.8% | 0.0% | 3.2% | 99.3% | 98.6% | 99.1% | 99.1% | 99.2% | 98.3% | 99.1% |
| 06_ConstSpeedOffset | 92.7% | 12.6% | 3.6% | 99.3% | 97.9% | 99.4% | 99.2% | 99.4% | 98.3% | 99.4% |
| 07_RandomSpeed | 85.2% | 9.6% | 96.2% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 80.7% | 3.4% | 87.0% | 99.9% | 100.0% | 100.0% | 100.0% | 99.9% | 100.0% | 100.0% |
| 09_EventualStop | 0.1% | (0.0% all) | (0.1% all) | (0.5% all) | (0.1% all) | (0.1% all) | (0.1% all) | (0.2% all) | (0.1% all) | (0.1% all) |
| 10_Disruptive | 99.8% | 1.1% | 97.9% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 11_DataReplay | 99.8% | 1.2% | 8.3% | 99.6% | 96.4% | 99.2% | 99.2% | 99.3% | 95.9% | 99.1% |
| 12_DelayedMessages | 72.1% | 0.2% | 6.3% | 45.9% | 45.8% | 47.5% | 47.6% | 45.9% | 47.3% | 47.6% |
| 13_DoS | 74.8% | 2.5% | 6.2% | 0.0% | 0.0% | 6.1% | 5.8% | 2.5% | 6.4% | 6.4% |
| 14_DoSRandom | 97.9% | 96.8% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 15_DoSDisruptive | 98.1% | 96.4% | 97.7% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 16_GridSybil | 85.2% | 0.7% | 2.7% | 39.4% | 29.1% | 39.0% | 39.1% | 39.1% | 29.4% | 39.1% |
| 17_DataReplaySybil | 97.8% | 0.0% | 5.2% | 33.4% | 16.5% | 29.0% | 29.2% | 31.2% | 14.8% | 29.1% |
| 18_DoSRandomSybil | 57.7% | 10.3% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% | 100.0% |
| 19_DoSDisruptiveSybil | 56.4% | 0.4% | 99.4% | 95.4% | 98.4% | 97.9% | 98.0% | 97.5% | 98.0% | 96.5% |
| S20_StaleReplay | 0.0% | (100.0% all) | (45.5% all) | (97.0% all) | (0.0% all) | (100.0% all) | (97.0% all) | (100.0% all) | (100.0% all) | (100.0% all) |

Genuine Tampa rows by kind (test): {"scored": 0.874, "first / gap": 0.002, "exact repeat": 0.124}; stack FA by kind: {"scored": 0.032, "first / gap": 0.0, "exact repeat": 0.0}.

