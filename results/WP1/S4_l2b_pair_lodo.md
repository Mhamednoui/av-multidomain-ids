Budget 1.0% false alarms on validation normal data. Domain: S4_l2b_pair_lodo.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.912 | 72.2% | 1.33% | 57.2% | 63.2% | 54.7% | 87.6% | 100.0% | 68.2% | 1.0 |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.27% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% | 1.0 |
| only_gps.cusum_ekf | 0.791 | 53.1% | 1.78% | 59.9% | 4.2% | 59.4% | 87.5% | 99.3% | 7.5% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% | 1.0 |
| only_gps.ekf_nis | 0.865 | 45.8% | 0.57% | 42.3% | 41.8% | 12.2% | 82.5% | 41.0% | 48.5% | 1.0 |
| all_but_gps.cusum_dr | 0.906 | 67.5% | 1.44% | 57.3% | 56.0% | 54.9% | 87.7% | 99.3% | 47.9% | 1.0 |
| all_but_gps.cusum_ekf | 0.907 | 70.9% | 1.30% | 55.4% | 64.7% | 47.4% | 87.6% | 100.0% | 67.7% | 1.0 |
| all_but_gps.dr_resid_10 | 0.913 | 72.4% | 1.29% | 57.4% | 63.0% | 55.3% | 87.3% | 100.0% | 69.5% | 1.0 |
| all_but_gps.ekf_nis | 0.892 | 71.4% | 1.71% | 57.6% | 59.9% | 56.4% | 87.8% | 100.0% | 65.0% | 1.0 |
