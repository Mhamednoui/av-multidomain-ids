## ROAD run 2b (revised design, final)
skew variant paper_N50_acc_loc, selected on ['correlated_signal_masquerade', 'max_speedometer_masquerade', 'reverse_light_off_masquerade', 'reverse_light_on_masquerade']

### regime A: summary on test windows
| layer | FA clean | FA/h | attack-window recall |
|---|---|---|---|
| can.l1_id_allow | 0.000 | 0 | 0.008 |
| can.l1_dlc | 0.000 | 0 | 0.000 |
| can.l1_period | 0.043 | 156 | 0.282 |
| can.l1_bus_load | 0.014 | 50 | 0.489 |
| can.l1_flood | 0.000 | 0 | 0.004 |
| can.l2a_skew | 0.350 | 1260 | 0.233 |
| combined_l1_l2a | 0.330 | 1188 | 0.553 |
| combined_l1 | 0.035 | 127 | 0.500 |

### regime A: per capture (window recall / delay s)
| capture | attack windows | L2a | L1 comb | L1+L2a comb |
|---|---|---|---|---|
| correlated_signal_attack_3 | 13 | 0.000 / - | 1.000 / 0.681 | 1.000 / 0.681 |
| correlated_signal_attack_3_masquerade | 13 | 0.000 / - | 0.000 / - | 0.000 / - |
| fuzzing_attack_3 | 2 | 0.000 / - | 1.000 / 0.175 | 1.000 / 0.175 |
| max_engine_coolant_temp_attack | 6 | 0.000 / - | 0.833 / 1.020 | 1.000 / 0.020 |
| max_engine_coolant_temp_attack_masquerade | 6 | 0.000 / - | 0.000 / - | 0.167 / 0.020 |
| max_speedometer_attack_3 | 62 | 0.000 / - | 1.000 / 0.481 | 1.000 / 0.481 |
| max_speedometer_attack_3_masquerade | 62 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_off_attack_3 | 25 | 0.920 / 2.476 | 1.000 / 0.476 | 1.000 / 0.476 |
| reverse_light_off_attack_3_masquerade | 25 | 0.640 / 9.475 | 0.000 / - | 0.480 / 13.475 |
| reverse_light_on_attack_3 | 24 | 0.917 / 2.929 | 1.000 / 0.929 | 1.000 / 0.929 |
| reverse_light_on_attack_3_masquerade | 24 | 0.000 / - | 0.000 / - | 0.000 / - |

### regime A: harness ablation (AUC / detection / FA)
| config | AUC | det | FA |
|---|---|---|---|
| all | 0.688 | 0.553 | 0.3301 |
| only_can.l1_bus_load | 0.677 | 0.489 | 0.0138 |
| only_can.l1_dlc | 0.500 | 0.000 | 0.0000 |
| only_can.l1_flood | 0.494 | 0.004 | 0.0000 |
| only_can.l1_id_allow | 0.504 | 0.008 | 0.0000 |
| only_can.l1_period | 0.825 | 0.282 | 0.0434 |
| only_can.l2a_skew | 0.458 | 0.233 | 0.3501 |
| all_but_can.l1_bus_load | 0.607 | 0.355 | 0.3501 |
| all_but_can.l1_dlc | 0.688 | 0.553 | 0.3301 |
| all_but_can.l1_flood | 0.686 | 0.553 | 0.3301 |
| all_but_can.l1_id_allow | 0.688 | 0.553 | 0.3301 |
| all_but_can.l1_period | 0.644 | 0.527 | 0.3177 |
| all_but_can.l2a_skew | 0.753 | 0.500 | 0.0351 |

### regime Ab0.001: summary on test windows
| layer | FA clean | FA/h | attack-window recall |
|---|---|---|---|
| can.l1_id_allow | 0.000 | 0 | 0.008 |
| can.l1_dlc | 0.000 | 0 | 0.000 |
| can.l1_period | 0.019 | 69 | 0.000 |
| can.l1_bus_load | 0.010 | 37 | 0.481 |
| can.l1_flood | 0.000 | 0 | 0.004 |
| can.l2a_skew | 0.307 | 1107 | 0.210 |
| combined_l1_l2a | 0.326 | 1174 | 0.523 |
| combined_l1 | 0.028 | 102 | 0.500 |

### regime Ab0.001: per capture (window recall / delay s)
| capture | attack windows | L2a | L1 comb | L1+L2a comb |
|---|---|---|---|---|
| correlated_signal_attack_3 | 13 | 0.000 / - | 1.000 / 0.681 | 1.000 / 0.681 |
| correlated_signal_attack_3_masquerade | 13 | 0.000 / - | 0.000 / - | 0.000 / - |
| fuzzing_attack_3 | 2 | 0.000 / - | 1.000 / 0.175 | 1.000 / 0.175 |
| max_engine_coolant_temp_attack | 6 | 0.000 / - | 0.833 / 1.020 | 0.000 / - |
| max_engine_coolant_temp_attack_masquerade | 6 | 0.000 / - | 0.000 / - | 0.000 / - |
| max_speedometer_attack_3 | 62 | 0.000 / - | 1.000 / 0.481 | 1.000 / 0.481 |
| max_speedometer_attack_3_masquerade | 62 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_off_attack_3 | 25 | 0.920 / 2.476 | 1.000 / 0.476 | 1.000 / 0.476 |
| reverse_light_off_attack_3_masquerade | 25 | 0.440 / 14.475 | 0.000 / - | 0.440 / 14.475 |
| reverse_light_on_attack_3 | 24 | 0.875 / 3.929 | 1.000 / 0.929 | 1.000 / 0.929 |
| reverse_light_on_attack_3_masquerade | 24 | 0.000 / - | 0.000 / - | 0.000 / - |

### regime Ab0.001: harness ablation (AUC / detection / FA)
| config | AUC | det | FA |
|---|---|---|---|
| all | 0.688 | 0.523 | 0.3260 |
| only_can.l1_bus_load | 0.677 | 0.481 | 0.0103 |
| only_can.l1_dlc | 0.500 | 0.000 | 0.0000 |
| only_can.l1_flood | 0.494 | 0.004 | 0.0000 |
| only_can.l1_id_allow | 0.504 | 0.008 | 0.0000 |
| only_can.l1_period | 0.825 | 0.000 | 0.0193 |
| only_can.l2a_skew | 0.458 | 0.210 | 0.3074 |
| all_but_can.l1_bus_load | 0.596 | 0.218 | 0.3205 |
| all_but_can.l1_dlc | 0.688 | 0.523 | 0.3260 |
| all_but_can.l1_flood | 0.686 | 0.523 | 0.3260 |
| all_but_can.l1_id_allow | 0.688 | 0.523 | 0.3260 |
| all_but_can.l1_period | 0.644 | 0.523 | 0.3129 |
| all_but_can.l2a_skew | 0.753 | 0.500 | 0.0283 |

## ROAD run 1 (pre-registered design, verdict)
skew variant drift_N20_acc, selected on ['correlated_signal_masquerade', 'max_speedometer_masquerade', 'reverse_light_off_masquerade', 'reverse_light_on_masquerade']

### regime A: summary on test windows
| layer | FA clean | FA/h | attack-window recall |
|---|---|---|---|
| can.l1_id_allow | 0.000 | 0 | 0.008 |
| can.l1_dlc | 0.000 | 0 | 0.000 |
| can.l1_period | 0.043 | 156 | 0.282 |
| can.l1_bus_load | 0.014 | 50 | 0.489 |
| can.l1_flood | 0.000 | 0 | 0.004 |
| can.l2a_skew | 0.039 | 141 | 0.378 |
| combined_l1_l2a | 0.066 | 238 | 0.500 |
| combined_l1 | 0.035 | 127 | 0.500 |

### regime A: per capture (window recall / delay s)
| capture | attack windows | L2a | L1 comb | L1+L2a comb |
|---|---|---|---|---|
| correlated_signal_attack_3 | 13 | 0.538 / 6.681 | 1.000 / 0.681 | 1.000 / 0.681 |
| correlated_signal_attack_3_masquerade | 13 | 0.000 / - | 0.000 / - | 0.000 / - |
| fuzzing_attack_3 | 2 | 0.000 / - | 1.000 / 0.175 | 1.000 / 0.175 |
| max_engine_coolant_temp_attack | 6 | 0.000 / - | 0.833 / 1.020 | 0.833 / 1.020 |
| max_engine_coolant_temp_attack_masquerade | 6 | 0.000 / - | 0.000 / - | 0.000 / - |
| max_speedometer_attack_3 | 62 | 0.887 / 7.483 | 1.000 / 0.481 | 1.000 / 0.481 |
| max_speedometer_attack_3_masquerade | 62 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_off_attack_3 | 25 | 0.760 / 6.476 | 1.000 / 0.476 | 1.000 / 0.476 |
| reverse_light_off_attack_3_masquerade | 25 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_on_attack_3 | 24 | 0.750 / 6.929 | 1.000 / 0.929 | 1.000 / 0.929 |
| reverse_light_on_attack_3_masquerade | 24 | 0.000 / - | 0.000 / - | 0.000 / - |

### regime A: harness ablation (AUC / detection / FA)
| config | AUC | det | FA |
|---|---|---|---|
| all | 0.713 | 0.500 | 0.0662 |
| only_can.l1_bus_load | 0.677 | 0.489 | 0.0138 |
| only_can.l1_dlc | 0.500 | 0.000 | 0.0000 |
| only_can.l1_flood | 0.494 | 0.004 | 0.0000 |
| only_can.l1_id_allow | 0.504 | 0.008 | 0.0000 |
| only_can.l1_period | 0.825 | 0.282 | 0.0434 |
| only_can.l2a_skew | 0.536 | 0.378 | 0.0393 |
| all_but_can.l1_bus_load | 0.801 | 0.481 | 0.0476 |
| all_but_can.l1_dlc | 0.713 | 0.500 | 0.0662 |
| all_but_can.l1_flood | 0.714 | 0.500 | 0.0744 |
| all_but_can.l1_id_allow | 0.713 | 0.500 | 0.0662 |
| all_but_can.l1_period | 0.617 | 0.481 | 0.0496 |
| all_but_can.l2a_skew | 0.753 | 0.500 | 0.0351 |

### regime Ab0.001: summary on test windows
| layer | FA clean | FA/h | attack-window recall |
|---|---|---|---|
| can.l1_id_allow | 0.000 | 0 | 0.008 |
| can.l1_dlc | 0.000 | 0 | 0.000 |
| can.l1_period | 0.019 | 69 | 0.000 |
| can.l1_bus_load | 0.010 | 37 | 0.481 |
| can.l1_flood | 0.000 | 0 | 0.004 |
| can.l2a_skew | 0.039 | 141 | 0.378 |
| combined_l1_l2a | 0.041 | 146 | 0.500 |
| combined_l1 | 0.028 | 102 | 0.500 |

### regime Ab0.001: per capture (window recall / delay s)
| capture | attack windows | L2a | L1 comb | L1+L2a comb |
|---|---|---|---|---|
| correlated_signal_attack_3 | 13 | 0.538 / 6.681 | 1.000 / 0.681 | 1.000 / 0.681 |
| correlated_signal_attack_3_masquerade | 13 | 0.000 / - | 0.000 / - | 0.000 / - |
| fuzzing_attack_3 | 2 | 0.000 / - | 1.000 / 0.175 | 1.000 / 0.175 |
| max_engine_coolant_temp_attack | 6 | 0.000 / - | 0.833 / 1.020 | 0.833 / 1.020 |
| max_engine_coolant_temp_attack_masquerade | 6 | 0.000 / - | 0.000 / - | 0.000 / - |
| max_speedometer_attack_3 | 62 | 0.887 / 7.483 | 1.000 / 0.481 | 1.000 / 0.481 |
| max_speedometer_attack_3_masquerade | 62 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_off_attack_3 | 25 | 0.760 / 6.476 | 1.000 / 0.476 | 1.000 / 0.476 |
| reverse_light_off_attack_3_masquerade | 25 | 0.000 / - | 0.000 / - | 0.000 / - |
| reverse_light_on_attack_3 | 24 | 0.750 / 6.929 | 1.000 / 0.929 | 1.000 / 0.929 |
| reverse_light_on_attack_3_masquerade | 24 | 0.000 / - | 0.000 / - | 0.000 / - |

### regime Ab0.001: harness ablation (AUC / detection / FA)
| config | AUC | det | FA |
|---|---|---|---|
| all | 0.713 | 0.500 | 0.0407 |
| only_can.l1_bus_load | 0.677 | 0.481 | 0.0103 |
| only_can.l1_dlc | 0.500 | 0.000 | 0.0000 |
| only_can.l1_flood | 0.494 | 0.004 | 0.0000 |
| only_can.l1_id_allow | 0.504 | 0.008 | 0.0000 |
| only_can.l1_period | 0.825 | 0.000 | 0.0193 |
| only_can.l2a_skew | 0.536 | 0.378 | 0.0393 |
| all_but_can.l1_bus_load | 0.801 | 0.366 | 0.0179 |
| all_but_can.l1_dlc | 0.713 | 0.500 | 0.0407 |
| all_but_can.l1_flood | 0.714 | 0.500 | 0.0476 |
| all_but_can.l1_id_allow | 0.713 | 0.500 | 0.0407 |
| all_but_can.l1_period | 0.617 | 0.481 | 0.0400 |
| all_but_can.l2a_skew | 0.753 | 0.500 | 0.0283 |

## Car-Hacking
skew variant paper_N50_acc, selected on ['DoS', 'Fuzzy', 'RPM', 'Gear']

### regime A: summary on test windows
| layer | FA clean | FA/h | attack-window recall |
|---|---|---|---|
| can.l1_id_allow | 0.000 | 0 | 0.583 |
| can.l1_dlc | 0.000 | 0 | 0.020 |
| can.l1_period | 0.007 | 24 | 0.922 |
| can.l1_bus_load | 0.000 | 0 | 0.443 |
| can.l1_flood | 0.000 | 0 | 0.287 |
| can.l2a_skew | 0.083 | 300 | 0.008 |
| combined_l1_l2a | 0.007 | 24 | 0.997 |
| combined_l1 | 0.010 | 36 | 0.998 |

### regime A: per capture (window recall / delay s)
| capture | attack windows | L2a | L1 comb | L1+L2a comb |
|---|---|---|---|---|
| DoS | 278 | 0.000 / - | 1.000 / 0.204 | 0.996 / 0.204 |
| Fuzzy | 291 | 0.027 / 2404.715 | 1.000 / 0.711 | 1.000 / 0.711 |
| RPM | 198 | 0.000 / - | 0.995 / 0.518 | 0.995 / 0.518 |
| Gear | 209 | 0.000 / - | 0.995 / 0.612 | 0.995 / 0.612 |

### regime A: harness ablation (AUC / detection / FA)
| config | AUC | det | FA |
|---|---|---|---|
| all | 1.000 | 0.997 | 0.0133 |
| only_can.l1_bus_load | 0.447 | 0.443 | 0.0000 |
| only_can.l1_dlc | 0.510 | 0.020 | 0.0000 |
| only_can.l1_flood | 0.383 | 0.287 | 0.0000 |
| only_can.l1_id_allow | 0.791 | 0.583 | 0.0000 |
| only_can.l1_period | 0.996 | 0.922 | 0.0067 |
| only_can.l2a_skew | 0.156 | 0.008 | 0.0833 |
| all_but_can.l1_bus_load | 0.990 | 0.934 | 0.0900 |
| all_but_can.l1_dlc | 1.000 | 0.997 | 0.0133 |
| all_but_can.l1_flood | 1.000 | 0.997 | 0.0133 |
| all_but_can.l1_id_allow | 1.000 | 0.998 | 0.0900 |
| all_but_can.l1_period | 0.911 | 0.903 | 0.0833 |
| all_but_can.l2a_skew | 1.000 | 0.998 | 0.0100 |

## D11 (window level): per set / subset / regime
| set | sub | vehicle | regime | L2a FA clean | L2a recall | L1 comb FA | L1 comb recall | L1+L2a FA | L1+L2a recall | detected files (L1 / L1+L2a) |
|---|---|---|---|---|---|---|---|---|---|---|
| 01 | test_01 | Impala | A | 0.054 | 0.921 | 0.023 | 1.000 | 0.047 | 1.000 | 8/8 / 8/8 |
| 01 | test_01 | Impala | B | 0.278 | 0.990 | 0.006 | 1.000 | 0.217 | 1.000 | 8/8 / 8/8 |
| 01 | test_02 | Silverado | A | 0.908 | 0.741 | 1.000 | 1.000 | 1.000 | 1.000 | 8/8 / 8/8 |
| 01 | test_02 | Silverado | B | 0.526 | 0.982 | 0.019 | 0.905 | 0.435 | 0.982 | 8/8 / 8/8 |
| 01 | test_03 | Impala | A | 0.000 | 0.729 | 0.034 | 1.000 | 0.007 | 1.000 | 12/12 / 12/12 |
| 01 | test_03 | Impala | B | 0.239 | 0.895 | 0.009 | 1.000 | 0.179 | 1.000 | 12/12 / 12/12 |
| 01 | test_04 | Traverse | A | 0.103 | 0.357 | 1.000 | 1.000 | 1.000 | 1.000 | 12/12 / 12/12 |
| 01 | test_04 | Traverse | B | 0.383 | 0.494 | 0.035 | 1.000 | 0.287 | 1.000 | 12/12 / 12/12 |
| 02 | test_01 | Traverse | A | 0.013 | 0.422 | 0.006 | 1.000 | 0.016 | 1.000 | 12/12 / 12/12 |
| 02 | test_01 | Traverse | B | 0.000 | 0.175 | 0.014 | 1.000 | 0.007 | 1.000 | 12/12 / 12/12 |
| 02 | test_02 | Subaru | A | 0.000 | 0.067 | 1.000 | 1.000 | 1.000 | 1.000 | 12/12 / 12/12 |
| 02 | test_02 | Subaru | B | 0.038 | 0.503 | 0.059 | 1.000 | 0.055 | 0.994 | 12/12 / 12/12 |
| 02 | test_03 | Traverse | A | 0.002 | 0.734 | 0.013 | 0.817 | 0.016 | 0.954 | 8/8 / 8/8 |
| 02 | test_03 | Traverse | B | 0.000 | 0.670 | 0.014 | 0.780 | 0.009 | 0.798 | 8/8 / 8/8 |
| 02 | test_04 | Subaru | A | 0.005 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 8/8 / 8/8 |
| 02 | test_04 | Subaru | B | 0.150 | 0.750 | 0.034 | 0.983 | 0.111 | 1.000 | 8/8 / 8/8 |
| 03 | test_01 | Silverado | A | 0.000 | 0.271 | 0.013 | 1.000 | 0.008 | 1.000 | 10/10 / 10/10 |
| 03 | test_01 | Silverado | B | 0.034 | 0.436 | 0.031 | 1.000 | 0.049 | 1.000 | 10/10 / 10/10 |
| 03 | test_02 | Subaru | A | 0.000 | 0.092 | 1.000 | 1.000 | 1.000 | 1.000 | 10/10 / 10/10 |
| 03 | test_02 | Subaru | B | 0.010 | 0.325 | 0.019 | 1.000 | 0.016 | 1.000 | 10/10 / 10/10 |
| 03 | test_03 | Silverado | A | 0.000 | 0.048 | 0.011 | 0.997 | 0.005 | 0.965 | 14/14 / 14/14 |
| 03 | test_03 | Silverado | B | 0.155 | 0.018 | 0.033 | 0.960 | 0.120 | 0.925 | 14/14 / 13/14 |
| 03 | test_04 | Subaru | A | 0.000 | 0.002 | 1.000 | 1.000 | 1.000 | 1.000 | 14/14 / 14/14 |
| 03 | test_04 | Subaru | B | 0.051 | 0.048 | 0.036 | 1.000 | 0.062 | 1.000 | 14/14 / 14/14 |
| 04 | test_01 | Subaru | A | 0.000 | 0.323 | 0.027 | 1.000 | 0.008 | 1.000 | 14/14 / 14/14 |
| 04 | test_01 | Subaru | B | 0.116 | 0.410 | 0.201 | 1.000 | 0.212 | 1.000 | 14/14 / 14/14 |
| 04 | test_02 | Traverse | A | 0.000 | 0.000 | 1.000 | 1.000 | 1.000 | 1.000 | 14/14 / 14/14 |
| 04 | test_02 | Traverse | B | 0.103 | 0.391 | 0.033 | 1.000 | 0.061 | 1.000 | 14/14 / 14/14 |
| 04 | test_03 | Subaru | A | 0.083 | 0.748 | 0.027 | 1.000 | 0.050 | 1.000 | 10/10 / 10/10 |
| 04 | test_03 | Subaru | B | 0.129 | 0.806 | 0.012 | 1.000 | 0.087 | 1.000 | 10/10 / 10/10 |
| 04 | test_04 | Traverse | A | 0.000 | 0.136 | 1.000 | 1.000 | 1.000 | 1.000 | 9/9 / 9/9 |
| 04 | test_04 | Traverse | B | 0.032 | 0.614 | 0.022 | 1.000 | 0.015 | 1.000 | 9/9 / 9/9 |
