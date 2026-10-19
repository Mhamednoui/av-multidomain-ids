Budget 1.0% false alarms on validation normal data. Domain: S4_l2b_pair_valonly.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.913 | 74.7% | 1.93% | 56.9% | 72.2% | 53.6% | 87.7% | 100.0% | 75.3% | 1.0 |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.26% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% | 1.0 |
| only_gps.cusum_ekf | 0.791 | 53.3% | 1.92% | 60.4% | 4.2% | 60.0% | 87.5% | 99.3% | 7.5% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |
| all_but_gps.cusum_dr | 0.907 | 71.5% | 1.98% | 57.3% | 67.2% | 54.6% | 87.8% | 99.3% | 60.7% | 1.0 |
| all_but_gps.cusum_ekf | 0.908 | 72.4% | 1.38% | 55.7% | 69.3% | 45.9% | 87.7% | 100.0% | 72.6% | 1.0 |
| all_but_gps.dr_resid_10 | 0.913 | 75.6% | 2.31% | 58.0% | 73.0% | 57.2% | 87.5% | 100.0% | 76.3% | 1.0 |
| all_but_gps.ekf_nis | 0.892 | 71.4% | 1.47% | 57.8% | 59.4% | 56.6% | 87.8% | 100.0% | 65.0% | 1.0 |
