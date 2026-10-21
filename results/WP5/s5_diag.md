**Row kinds: share of rows (VeReMi)**

| split | class | scored | unscored (first / gap) | frozen (exact repeat) |
|---|---|---|---|---|
| train | genuine | 99.1% | 0.9% | 0.0% |
| train | attack | 69.8% | 15.4% | 14.8% |
| val | genuine | 99.1% | 0.9% | 0.0% |
| val | attack | 67.1% | 15.7% | 17.2% |
| test | genuine | 99.1% | 0.9% | 0.0% |
| test | attack | 68.5% | 15.5% | 16.0% |

**L4 (headline model) false alarms on genuine TEST rows by kind**

| kind | genuine rows | FA |
|---|---|---|
| scored | 420555 | 0.2% |
| unscored (first / gap) | 3873 | 100.0% |
| frozen (exact repeat) | 0 | - |

First messages of genuine tracks: 3873; L4 alarms on 100.0% of them; 84.3% of all L4 genuine false alarms are first messages, 0.0% are frozen repeats.

**Per class: share of rows by kind and headline-L4 detection by kind (TEST)**

| class | scored share | scored: L4 | unscored share | unscored: L4 | frozen share | frozen: L4 |
|---|---|---|---|---|---|---|
| 01_ConstPos | 0.0% | - | 0.9% | 100.0% | 99.1% | 100.0% |
| 02_ConstPosOffset | 99.1% | 0.1% | 0.9% | 100.0% | 0.0% | - |
| 03_RandomPos | 99.1% | 100.0% | 0.9% | 100.0% | 0.0% | - |
| 04_RandomPosOffset | 99.1% | 100.0% | 0.9% | 100.0% | 0.0% | - |
| 05_ConstSpeed | 99.1% | 100.0% | 0.9% | 100.0% | 0.0% | - |
| 06_ConstSpeedOffset * | 99.1% | 100.0% | 0.9% | 100.0% | 0.0% | - |
| 07_RandomSpeed | 99.2% | 100.0% | 0.8% | 100.0% | 0.0% | - |
| 08_RandomSpeedOffset | 99.1% | 100.0% | 0.9% | 100.0% | 0.0% | - |
| 09_EventualStop | 20.7% | 0.3% | 0.9% | 100.0% | 78.4% | 100.0% |
| 10_Disruptive | 96.5% | 99.3% | 0.9% | 100.0% | 2.6% | 100.0% |
| 11_DataReplay | 84.5% | 99.2% | 0.9% | 100.0% | 14.7% | 100.0% |
| 12_DelayedMessages * | 48.1% | 100.0% | 0.9% | 100.0% | 51.0% | 100.0% |
| 13_DoS | 32.9% | 100.0% | 0.3% | 100.0% | 66.9% | 100.0% |
| 14_DoSRandom | 99.7% | 100.0% | 0.3% | 100.0% | 0.0% | - |
| 15_DoSDisruptive | 96.7% | 100.0% | 0.3% | 100.0% | 3.0% | 100.0% |
| 16_GridSybil | 96.9% | 80.5% | 3.0% | 100.0% | 0.1% | 100.0% |
| 17_DataReplaySybil * | 32.0% | 74.8% | 54.4% | 100.0% | 13.6% | 100.0% |
| 18_DoSRandomSybil | 0.0% | - | 100.0% | 100.0% | 0.0% | - |
| 19_DoSDisruptiveSybil | 0.2% | 100.0% | 99.7% | 100.0% | 0.1% | 100.0% |

**Scored rows only (kind 0): diagnostic L4 trained on scored train rows only vs headline L4 vs baseline union (re-thresholded on genuine val scored rows, 1%)**

FA on genuine scored test rows: diagnostic 1.6%, baseline 1.0%; AUC on scored test rows: diagnostic 0.955, headline L4 0.955, baseline 0.945.

| class | scored rows | share of class | diagnostic L4 | headline L4 | baseline union |
|---|---|---|---|---|---|
| 01_ConstPos | 0 | 0.0% | - | - | - |
| 02_ConstPosOffset | 9827 | 99.1% | 3.1% | 0.1% | 1.0% |
| 03_RandomPos | 9746 | 99.1% | 100.0% | 100.0% | 100.0% |
| 04_RandomPosOffset | 10128 | 99.1% | 100.0% | 100.0% | 100.0% |
| 05_ConstSpeed | 9308 | 99.1% | 100.0% | 100.0% | 99.9% |
| 06_ConstSpeedOffset * | 9697 | 99.1% | 100.0% | 100.0% | 99.8% |
| 07_RandomSpeed | 10685 | 99.2% | 100.0% | 100.0% | 100.0% |
| 08_RandomSpeedOffset | 9322 | 99.1% | 100.0% | 100.0% | 99.9% |
| 09_EventualStop | 1991 | 20.7% | 2.0% | 0.3% | 0.7% |
| 10_Disruptive | 9703 | 96.5% | 99.3% | 99.3% | 99.2% |
| 11_DataReplay | 7974 | 84.5% | 99.6% | 99.2% | 98.2% |
| 12_DelayedMessages * | 4533 | 48.1% | 100.0% | 100.0% | 100.0% |
| 13_DoS | 10148 | 32.9% | 100.0% | 100.0% | 100.0% |
| 14_DoSRandom | 30030 | 99.7% | 100.0% | 100.0% | 100.0% |
| 15_DoSDisruptive | 26066 | 96.7% | 100.0% | 100.0% | 100.0% |
| 16_GridSybil | 39380 | 96.9% | 81.5% | 80.5% | 76.2% |
| 17_DataReplaySybil * | 3146 | 32.0% | 96.3% | 74.8% | 19.9% |
| 18_DoSRandomSybil | 0 | 0.0% | - | - | - |
| 19_DoSDisruptiveSybil | 28 | 0.2% | 100.0% | 100.0% | 100.0% |
| mean over classes with >= 50 scored rows: seen (16) | | | 83.5% | 83.0% | 82.7% |
| unseen 6 and 17 | | | 98.2% | 87.4% | 59.9% |
