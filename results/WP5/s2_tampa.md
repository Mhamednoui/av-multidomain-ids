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
