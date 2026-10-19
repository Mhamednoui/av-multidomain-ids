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
