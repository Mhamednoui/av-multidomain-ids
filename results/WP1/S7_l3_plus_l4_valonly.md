Budget 1.0% false alarms on validation normal data. Domain: S7_l3_plus_l4_valonly.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.899 | 62.3% | 0.84% | 53.7% | 58.6% | 44.8% | 88.0% | 71.8% | 53.1% | 2.0 |
| only_gps.l3_residual_normal | 0.875 | 62.3% | 1.18% | 54.3% | 58.7% | 40.6% | 87.2% | 72.4% | 56.3% | 1.0 |
| only_gps.l4_c2 | 0.888 | 56.5% | 0.36% | 47.9% | 49.3% | 38.8% | 87.7% | 71.0% | 40.5% | 2.0 |
