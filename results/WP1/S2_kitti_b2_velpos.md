Budget 1.0% false alarms on validation normal data. Domain: S2_kitti_b2_velpos.

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.847 | 53.4% | 1.42% | 53.9% | 40.1% | 44.0% | 85.8% | 69.6% | 23.5% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% | 1.0 |
