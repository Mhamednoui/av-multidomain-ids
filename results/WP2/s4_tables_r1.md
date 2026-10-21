| capture | L2b detected | recall | delay s | FA clean | L1 detected | L1 delay | L1+L2b detected | L1+L2b delay | L1+L2b FA | frame recall 1% |
|---|---|---|---|---|---|---|---|---|---|---|
| correlated_signal_attack_3 | True | 1.000 | 0.681 | - | True | 0.681 | True | 0.681 | - | 1.000 |
| max_speedometer_attack_3 | True | 1.000 | 0.481 | 0.000 | True | 0.481 | True | 0.481 | 0.000 | 1.000 |
| reverse_light_off_attack_3 | False | 0.000 | - | 0.000 | True | 0.476 | True | 0.476 | 0.000 | 0.000 |
| reverse_light_on_attack_3 | True | 1.000 | 0.929 | 0.000 | True | 0.929 | True | 0.929 | 0.000 | 1.000 |
| fuzzing_attack_3 | True | 0.500 | 0.658 | - | True | 0.175 | True | 0.175 | - | 0.017 |
| correlated_signal_attack_3_masquerade | True | 1.000 | 0.681 | - | False | - | True | 0.681 | - | 1.000 |
| max_speedometer_attack_3_masquerade | True | 1.000 | 0.481 | 0.000 | False | - | True | 0.481 | 0.000 | 1.000 |
| reverse_light_off_attack_3_masquerade | False | 0.000 | - | 0.000 | False | - | False | - | 0.000 | 0.000 |
| reverse_light_on_attack_3_masquerade | True | 1.000 | 0.929 | 0.000 | False | - | True | 0.929 | 0.000 | 1.000 |
| max_engine_coolant_temp_attack | True | 1.000 | 0.020 | 0.000 | True | 0.020 | True | 0.020 | 0.000 | 1.000 |
| max_engine_coolant_temp_attack_masquerade | True | 1.000 | 0.020 | 0.000 | True | 0.020 | True | 0.020 | 0.000 | 1.000 |
| ambient_dyno_drive_benign_anomaly | - | - | - | 0.495 | - | - | - | - | 0.544 | - |
| ambient_dyno_drive_extended_short | - | - | - | 0.666 | - | - | - | - | 0.719 | - |
| ambient_dyno_reverse | - | - | - | 0.000 | - | - | - | - | 0.000 | - |
| ambient_highway_street_driving_diagnostics | - | - | - | 0.000 | - | - | - | - | 0.002 | - |

Clean-window FA over the test split: {'l1': 0.05236728837876614, 'l2b': 0.32281205164992827, 'l1_or_l2b': 0.3522238163558106, 'n': 1394}
AUC (window, all test): 0.847