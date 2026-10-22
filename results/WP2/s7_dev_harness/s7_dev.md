Budget 1.0% false alarms on validation normal data. Domain: s7_dev.

| configuration | AUC | detection | false alarms | det correlated_signal | det correlated_signal_masquerade | det fuzzing | det max_speedometer | det max_speedometer_masquerade | det reverse_light_off | det reverse_light_off_masquerade | det reverse_light_on | det reverse_light_on_masquerade | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.997 | 92.1% | 0.97% | 100.0% | 100.0% | 100.0% | 100.0% | 49.1% | 100.0% | 100.0% | 98.3% | 98.3% | 0.0 |
| only_can.l1_spec_rules | 0.837 | 58.0% | 0.99% | 100.0% | 8.9% | 100.0% | 100.0% | 43.9% | 100.0% | 0.0% | 98.3% | 0.0% | 0.0 |
| only_can.l3c_signal_predictors | 0.658 | 52.7% | 0.99% | 100.0% | 100.0% | 42.9% | 100.0% | 100.0% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0 |
| only_can.l3d_reverse_state | 0.729 | 45.8% | 0.00% | 0.0% | 0.0% | 0.0% | 0.0% | 0.0% | 100.0% | 100.0% | 98.3% | 98.3% | 0.0 |
| all_but_can.l1_spec_rules | 0.993 | 98.5% | 0.99% | 100.0% | 100.0% | 42.9% | 100.0% | 100.0% | 100.0% | 100.0% | 98.3% | 98.3% | 0.0 |
| all_but_can.l3c_signal_predictors | 0.930 | 80.9% | 0.99% | 100.0% | 8.9% | 100.0% | 100.0% | 43.9% | 100.0% | 100.0% | 98.3% | 98.3% | 0.0 |
| all_but_can.l3d_reverse_state | 0.862 | 69.2% | 0.97% | 100.0% | 100.0% | 100.0% | 100.0% | 49.1% | 100.0% | 0.0% | 98.3% | 0.0% | 0.0 |
