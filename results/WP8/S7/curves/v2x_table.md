# v2x (H31, H31 scoring (frozen v3 vs frozen v3.1, one run))

| subset | exposure | n_pos | n_neg | auc | det@1.0% | det@2.0% | op_fa | op_det |
|---|---|---|---|---|---|---|---|---|
| V2X 01_ConstPos | re-used test (exposure n+1) | 826 | 42463 | 0.950 | 0.883 | 0.884 | 0.108 | 0.907 |
| V2X 02_ConstPosOffset | re-used test (exposure n+1) | 1296 | 42463 | 0.785 | 0.525 | 0.531 | 0.108 | 0.586 |
| V2X 03_RandomPos | re-used test (exposure n+1) | 744 | 42463 | 0.846 | 0.711 | 0.712 | 0.108 | 0.746 |
| V2X 04_RandomPosOffset | re-used test (exposure n+1) | 1008 | 42463 | 0.992 | 0.971 | 0.971 | 0.108 | 0.977 |
| V2X 05_ConstSpeed | re-used test (exposure n+1) | 1105 | 42463 | 0.995 | 0.987 | 0.987 | 0.108 | 0.990 |
| V2X 06_ConstSpeedOffset | re-used test (exposure n+1) | 1381 | 42463 | 0.995 | 0.979 | 0.981 | 0.108 | 0.988 |
| V2X 07_RandomSpeed | re-used test (exposure n+1) | 1578 | 42463 | 0.999 | 0.996 | 0.996 | 0.108 | 0.997 |
| V2X 08_RandomSpeedOffset | re-used test (exposure n+1) | 1528 | 42463 | 0.996 | 0.982 | 0.986 | 0.108 | 0.990 |
| V2X 09_EventualStop | re-used test (exposure n+1) | 796 | 42463 | 0.771 | 0.574 | 0.584 | 0.108 | 0.632 |
| V2X 10_Disruptive | re-used test (exposure n+1) | 1510 | 42463 | 0.968 | 0.925 | 0.927 | 0.108 | 0.938 |
| V2X 11_DataReplay | re-used test (exposure n+1) | 1202 | 42463 | 0.966 | 0.916 | 0.916 | 0.108 | 0.928 |
| V2X 13_DoS | re-used test (exposure n+1) | 6119 | 42463 | 0.999 | 0.999 | 0.999 | 0.108 | 0.999 |
| V2X 14_DoSRandom | re-used test (exposure n+1) | 2651 | 42463 | 0.990 | 0.976 | 0.976 | 0.108 | 0.981 |
| V2X 15_DoSDisruptive | re-used test (exposure n+1) | 4047 | 42463 | 0.995 | 0.988 | 0.988 | 0.108 | 0.990 |
| V2X 16_GridSybil | re-used test (exposure n+1) | 6350 | 42463 | 0.991 | 0.974 | 0.975 | 0.108 | 0.982 |
| V2X 17_DataReplaySybil | re-used test (exposure n+1) | 1127 | 42463 | 0.930 | 0.750 | 0.753 | 0.108 | 0.831 |
| V2X 18_DoSRandomSybil | re-used test (exposure n+1) | 1773 | 42463 | 0.964 | 0.867 | 0.867 | 0.108 | 0.890 |
| V2X 19_DoSDisruptiveSybil | re-used test (exposure n+1) | 3118 | 42463 | 0.969 | 0.787 | 0.818 | 0.108 | 0.935 |
| V2X pooled attack types | re-used test (exposure n+1) | 38159 | 42463 | 0.972 [0.966, 0.977] | 0.920 [0.896, 0.937] | 0.924 [0.903, 0.939] | 0.108 | 0.944 |
