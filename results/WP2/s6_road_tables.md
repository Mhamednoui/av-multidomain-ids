# WP2 S6: ROAD (validation / out-of-fold only)

## P1 L4 timing: variant ['all', 50], val-calibrated 1% window threshold, seen families (instance 2)

| capture | detected | window recall | delay s | clean FA | frame recall @1% |
|---|---|---|---|---|---|
| ambient_dyno_drive_basic_short | - | - | None | 1.6% | - |
| ambient_dyno_drive_winter | - | - | None | 0.0% | - |
| correlated_signal_attack_2 | True | 91.3% | 1.1692899465560913 | 0.0% | 100.0% |
| correlated_signal_attack_2_masquerade | True | 69.6% | 1.1692899465560913 | 0.0% | 62.3% |
| fuzzing_attack_2 | True | 100.0% | 0.6316670179367065 | 0.0% | 99.4% |
| max_speedometer_attack_2 | True | 96.9% | 0.9901502132415771 | 0.0% | 100.0% |
| max_speedometer_attack_2_masquerade | False | 0.0% | None | 0.0% | 37.0% |
| reverse_light_off_attack_2 | True | 100.0% | 0.8308529853820801 | 0.0% | 100.0% |
| reverse_light_off_attack_2_masquerade | True | 70.8% | 0.8308529853820801 | 0.0% | 56.1% |
| reverse_light_on_attack_2 | True | 97.4% | 0.5911200046539307 | 0.0% | 100.0% |
| reverse_light_on_attack_2_masquerade | False | 0.0% | None | 0.0% | 34.0% |

## P1 L4 payload: variant ['all', 1], val-calibrated 1% window threshold, seen families (instance 2)

| capture | detected | window recall | delay s | clean FA | frame recall @1% |
|---|---|---|---|---|---|
| ambient_dyno_drive_basic_short | - | - | None | 0.2% | - |
| ambient_dyno_drive_winter | - | - | None | 0.0% | - |
| correlated_signal_attack_2 | True | 100.0% | 0.1687990427017212 | 0.0% | 100.0% |
| correlated_signal_attack_2_masquerade | True | 100.0% | 0.1687990427017212 | 0.0% | 100.0% |
| fuzzing_attack_2 | True | 100.0% | 0.6316670179367065 | 0.0% | 100.0% |
| max_speedometer_attack_2 | False | 0.0% | None | 6.7% | 100.0% |
| max_speedometer_attack_2_masquerade | False | 0.0% | None | 6.7% | 99.8% |
| reverse_light_off_attack_2 | True | 100.0% | 0.8308529853820801 | 8.3% | 100.0% |
| reverse_light_off_attack_2_masquerade | True | 100.0% | 0.8308529853820801 | 8.3% | 100.0% |
| reverse_light_on_attack_2 | False | 0.0% | None | 5.3% | 100.0% |
| reverse_light_on_attack_2_masquerade | False | 0.0% | None | 5.3% | 7.3% |

## OOF L4 timing: variant ['all', 50], pooled threshold 0.8761, pooled FA 1.0%, unseen families

| capture | detected | window recall | delay s | clean FA | frame recall @1% |
|---|---|---|---|---|---|
| ambient_dyno_drive_basic_long | - | - | None | 0.2% | - |
| ambient_dyno_drive_basic_short | - | - | None | 1.1% | - |
| ambient_dyno_drive_extended_long | - | - | None | 0.0% | - |
| ambient_dyno_drive_radio_infotainment | - | - | None | 0.0% | - |
| ambient_dyno_drive_winter | - | - | None | 0.0% | - |
| ambient_dyno_exercise_all_bits | - | - | None | 2.4% | - |
| ambient_dyno_idle_radio_infotainment | - | - | None | 0.0% | - |
| ambient_highway_street_driving_long | - | - | None | 1.0% | - |
| correlated_signal_attack_1 | True | 54.5% | 0.8076629638671875 | 0.0% | 43.0% |
| correlated_signal_attack_1_masquerade | False | 0.0% | None | 0.0% | 0.0% |
| correlated_signal_attack_2 | True | 78.3% | 1.1692899465560913 | 0.0% | 83.3% |
| correlated_signal_attack_2_masquerade | False | 0.0% | None | 0.0% | 0.0% |
| fuzzing_attack_1 | False | 0.0% | None | 0.0% | 0.7% |
| fuzzing_attack_2 | False | 0.0% | None | 0.0% | 0.9% |
| max_speedometer_attack_1 | True | 100.0% | 0.9900970458984375 | 0.0% | 99.8% |
| max_speedometer_attack_1_masquerade | False | 0.0% | None | 0.0% | 44.7% |
| max_speedometer_attack_2 | True | 96.9% | 0.9901502132415771 | 0.0% | 99.8% |
| max_speedometer_attack_2_masquerade | False | 0.0% | None | 0.0% | 29.5% |
| reverse_light_off_attack_1 | True | 100.0% | 0.3719820976257324 | 0.0% | 100.0% |
| reverse_light_off_attack_1_masquerade | False | 0.0% | None | 0.0% | 41.0% |
| reverse_light_off_attack_2 | True | 100.0% | 0.8308529853820801 | 0.0% | 100.0% |
| reverse_light_off_attack_2_masquerade | True | 12.5% | 1.830759048461914 | 0.0% | 46.8% |
| reverse_light_on_attack_1 | True | 95.2% | 1.0698840618133545 | 0.0% | 100.0% |
| reverse_light_on_attack_1_masquerade | False | 0.0% | None | 0.0% | 33.5% |
| reverse_light_on_attack_2 | True | 97.4% | 0.5911200046539307 | 0.0% | 100.0% |
| reverse_light_on_attack_2_masquerade | False | 0.0% | None | 0.0% | 25.3% |

Reverse-bit windows: 3 alarms in 459 windows (0.7%); other clean ambient windows 1.1% (n 8877).

## OOF L4 payload: variant ['all', 1], pooled threshold 1.226, pooled FA 1.0%, unseen families

| capture | detected | window recall | delay s | clean FA | frame recall @1% |
|---|---|---|---|---|---|
| ambient_dyno_drive_basic_long | - | - | None | 0.0% | - |
| ambient_dyno_drive_basic_short | - | - | None | 0.0% | - |
| ambient_dyno_drive_extended_long | - | - | None | 0.0% | - |
| ambient_dyno_drive_radio_infotainment | - | - | None | 3.6% | - |
| ambient_dyno_drive_winter | - | - | None | 0.0% | - |
| ambient_dyno_exercise_all_bits | - | - | None | 0.7% | - |
| ambient_dyno_idle_radio_infotainment | - | - | None | 0.0% | - |
| ambient_highway_street_driving_long | - | - | None | 1.8% | - |
| correlated_signal_attack_1 | False | 0.0% | None | 0.0% | 61.3% |
| correlated_signal_attack_1_masquerade | False | 0.0% | None | 0.0% | 0.0% |
| correlated_signal_attack_2 | False | 0.0% | None | 0.0% | 96.8% |
| correlated_signal_attack_2_masquerade | False | 0.0% | None | 0.0% | 0.0% |
| fuzzing_attack_1 | False | 0.0% | None | 0.0% | 31.6% |
| fuzzing_attack_2 | False | 0.0% | None | 0.0% | 32.4% |
| max_speedometer_attack_1 | False | 0.0% | None | 0.0% | 100.0% |
| max_speedometer_attack_1_masquerade | False | 0.0% | None | 0.0% | 0.5% |
| max_speedometer_attack_2 | False | 0.0% | None | 13.3% | 95.0% |
| max_speedometer_attack_2_masquerade | False | 0.0% | None | 13.3% | 6.0% |
| reverse_light_off_attack_1 | True | 100.0% | 0.3719820976257324 | 0.0% | 100.0% |
| reverse_light_off_attack_1_masquerade | True | 12.5% | 0.3719820976257324 | 0.0% | 100.0% |
| reverse_light_off_attack_2 | True | 100.0% | 0.8308529853820801 | 0.0% | 100.0% |
| reverse_light_off_attack_2_masquerade | True | 4.2% | 0.8308529853820801 | 0.0% | 99.9% |
| reverse_light_on_attack_1 | True | 100.0% | 0.07059502601623535 | 0.0% | 100.0% |
| reverse_light_on_attack_1_masquerade | True | 4.8% | 0.07059502601623535 | 0.0% | 100.0% |
| reverse_light_on_attack_2 | True | 100.0% | 0.5911200046539307 | 0.0% | 100.0% |
| reverse_light_on_attack_2_masquerade | True | 2.6% | 0.5911200046539307 | 0.0% | 43.9% |

Reverse-bit windows: 27 alarms in 459 windows (5.9%); other clean ambient windows 0.8% (n 8877).

## Ablation on the 11 validation captures, OOF thresholds (unseen families)

| configuration | clean FA | captures detected | masquerade detected | mean window recall |
|---|---|---|---|---|
| base L1+L2b+L3 | 2.3% | 9/9 | 4/4 | 100.0% |
| L1 | 1.8% | 6/9 | 1/4 | 56.0% |
| L2b | 0.0% | 7/9 | 3/4 | 74.1% |
| L3 | 0.5% | 9/9 | 4/4 | 96.3% |
| L1+L2b | 1.8% | 9/9 | 4/4 | 89.4% |
| L4 timing | 0.7% | 5/9 | 1/4 | 42.8% |
| L4 payload | 0.7% | 4/9 | 2/4 | 23.0% |
| base + L4 timing | 3.0% | 9/9 | 4/4 | 100.0% |
| base + L4 payload | 3.0% | 9/9 | 4/4 | 100.0% |
| base + both L4 | 3.7% | 9/9 | 4/4 | 100.0% |

## Ablation on the 11 validation captures, P1 val thresholds (seen families)

| configuration | clean FA | captures detected | masquerade detected | mean window recall |
|---|---|---|---|---|
| base L1+L2b+L3 | 2.3% | 9/9 | 4/4 | 100.0% |
| L1 | 1.8% | 6/9 | 1/4 | 56.0% |
| L2b | 0.0% | 7/9 | 3/4 | 74.1% |
| L3 | 0.5% | 9/9 | 4/4 | 96.3% |
| L1+L2b | 1.8% | 9/9 | 4/4 | 89.4% |
| L4 timing | 1.2% | 7/9 | 2/4 | 69.5% |
| L4 payload | 0.9% | 5/9 | 2/4 | 55.6% |
| base + L4 timing | 3.6% | 9/9 | 4/4 | 100.0% |
| base + L4 payload | 2.9% | 9/9 | 4/4 | 100.0% |
| base + both L4 | 4.1% | 9/9 | 4/4 | 100.0% |
