Budget 1.0% false alarms on validation normal data. Domain: S7_l3_plus_l4_lodo.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.901 | 62.6% | 0.91% | 54.0% | 58.9% | 46.0% | 88.5% | 72.1% | 52.5% | 2.0 |
| only_gps.l3_residual_normal | 0.875 | 60.1% | 0.64% | 53.0% | 56.7% | 38.4% | 86.2% | 69.9% | 52.4% | 1.0 |
| only_gps.l4_c2 | 0.888 | 58.8% | 0.75% | 50.7% | 52.1% | 42.5% | 88.6% | 71.7% | 43.6% | 2.0 |
