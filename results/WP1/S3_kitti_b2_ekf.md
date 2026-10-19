Budget 1.0% false alarms on validation normal data. Domain: S3_kitti_b2_ekf.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.892 | 64.9% | 1.83% | 51.3% | 70.6% | 39.7% | 86.3% | 73.6% | 63.6% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |
