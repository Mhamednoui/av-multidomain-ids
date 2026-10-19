Budget 1.0% false alarms on validation normal data. Domain: S3_kitti_ekf_pair.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.903 | 74.4% | 4.19% | 52.6% | 82.7% | 40.9% | 86.2% | 100.0% | 80.5% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |
| only_gps.ekf_nis_gated | 0.902 | 74.3% | 4.09% | 52.6% | 82.5% | 40.6% | 86.2% | 100.0% | 80.2% | 1.0 |
