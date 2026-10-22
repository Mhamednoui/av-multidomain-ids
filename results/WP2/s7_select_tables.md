L1 variant (period rule alone, mean window recall of the 5 non-masquerade families at pooled 1%):
- variant 0 [0.99, 0.05]: 0.000 {'correlated_signal': 0.0, 'fuzzing': 0.0, 'max_speedometer': 0.0, 'reverse_light_off': 0.0, 'reverse_light_on': 0.0}
- variant 1 [0.999, 0.05]: 0.000 {'correlated_signal': 0.0, 'fuzzing': 0.0, 'max_speedometer': 0.0, 'reverse_light_off': 0.0, 'reverse_light_on': 0.0}
- variant 2 [0.99, 0.25]: 0.000 {'correlated_signal': 0.0, 'fuzzing': 0.0, 'max_speedometer': 0.0, 'reverse_light_off': 0.0, 'reverse_light_on': 0.0}
- variant 3 [0.999, 0.25]: 0.000 {'correlated_signal': 0.0, 'fuzzing': 0.0, 'max_speedometer': 0.0, 'reverse_light_off': 0.0, 'reverse_light_on': 0.0}

L2b check sets: K0: lead FA 0.000, max fold FA 1.000, masq recall 0.50 (4/8); K1: lead FA 0.000, max fold FA 1.000, masq recall 0.75 (6/8); K2: lead FA 0.000, max fold FA 0.064, masq recall 0.75 (6/8); K3: lead FA 0.000, max fold FA 0.066, masq recall 0.75 (6/8); chosen None

L3c designs: dyno-avg FA / road-avg FA / regime avg / max fold / lead FA(union) / masq recall (detected of 8)
- 0 M0_r0.0_P0: 0.020 / 0.240 / 0.130 / 0.283 / 0.022 / 0.99 (8/8)
- 1 M1_r0.0_P0: 0.027 / 0.002 / 0.014 / 0.134 / 0.022 / 0.99 (8/8)
- 2 M0_r0.9_P0: 0.019 / 0.125 / 0.072 / 0.219 / 0.022 / 0.99 (8/8)
- 3 M1_r0.9_P0: 0.026 / 0.002 / 0.014 / 0.129 / 0.022 / 0.99 (8/8)
- 4 M0_r0.0_P1: 0.002 / 0.022 / 0.012 / 0.040 / 0.000 / 0.74 (6/8)
- 5 M1_r0.0_P1: 0.024 / 0.006 / 0.015 / 0.116 / 0.030 / 0.99 (8/8)
- 6 M0_r0.9_P1: 0.002 / 0.022 / 0.012 / 0.037 / 0.000 / 0.75 (8/8)
- 7 M1_r0.9_P1: 0.025 / 0.006 / 0.016 / 0.120 / 0.030 / 0.99 (8/8)
chosen: 3 (qualifying designs: lowest regime-averaged threshold-LOCO FA)