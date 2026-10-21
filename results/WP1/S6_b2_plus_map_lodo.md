Budget 1.0% false alarms on validation normal data. Domain: S6_b2_plus_map_lodo.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.824 | 56.7% | 5.66% | 47.0% | 50.4% | 35.7% | 86.8% | 86.8% | 29.4% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% | 1.0 |
| only_gps.map_dist | 0.652 | 31.5% | 7.62% | 38.8% | 40.9% | 22.6% | 18.0% | 59.9% | 8.4% | 2.0 |
