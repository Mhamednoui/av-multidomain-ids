Budget 1.0% false alarms on validation normal data. Domain: S6_b2_plus_map_valonly.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.837 | 51.8% | 0.64% | 41.9% | 45.0% | 26.7% | 85.9% | 84.2% | 22.3% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.map_dist | 0.652 | 23.0% | 1.14% | 32.4% | 35.4% | 15.7% | 2.7% | 51.7% | 0.3% | 4.0 |
