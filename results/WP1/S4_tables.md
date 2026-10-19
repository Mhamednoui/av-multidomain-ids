Selected on the 16 train+val drives (S4_dev.json): best DR layer `cusum_dr_nis|k=2.0|scale=learn|freeze=self8+nis`, best EKF-innovation layer `cusum_ekf_axis|k=1.5`; criterion J = mean(6 run-level detections, slow drift <0.5 m/s within 30 s) at the pooled-LODO 1% threshold on the 16 drives.

**Development drives (train + val): what LODO changes.** FA on the 13 train drives with a threshold from the 3 val drives only, vs the pooled LODO threshold; held-out FA = each drive's FA with the threshold from the other 15 drives.

| layer | FA 13 train drives @ val-only thr | FA 13 train drives @ LODO thr | LODO held-out FA (pooled) | worst held-out drive |
|---|---|---|---|---|
| gps.dr_resid_10 | 0.51% | 0.96% | 1.21% | 4.28% |
| gps.ekf_nis | 3.10% | 1.11% | 1.30% | 19.50% |
| cusum_ekf_axis|k=1.5 | 1.19% | 1.02% | 1.04% | 1.79% |
| cusum_dr_nis|k=2.0|scale=learn|freeze=self8+nis | 1.00% | 1.00% | 1.04% | 1.96% |

**Grid, top 8 by J (dev drives, LODO threshold)** (full table: S4_dev_grid.md)

| candidate | J | slow-drift30 | LODO held-out FA |
|---|---|---|---|
| cusum_dr_nis|k=2.0|scale=learn|freeze=self8+nis | 0.699 | 44% | 1.04% |
| cusum_dr_axis|k=2.0|scale=learn|freeze=self8+nis | 0.697 | 44% | 1.06% |
| cusum_dr_axis|k=1.5|scale=learn|freeze=self8+nis | 0.695 | 44% | 1.03% |
| cusum_dr_nis|k=2.0|scale=learn|freeze=never | 0.694 | 44% | 1.03% |
| cusum_dr_nis|k=1.5|scale=learn|freeze=self8+nis | 0.693 | 41% | 1.06% |
| cusum_dr_axis|k=2.0|scale=learn|freeze=never | 0.693 | 44% | 1.01% |
| cusum_dr_nis|k=1.0|scale=learn|freeze=self8+nis | 0.690 | 41% | 1.04% |
| cusum_dr_axis|k=2.0|scale=learn|freeze=self8 | 0.688 | 44% | 1.05% |

**KITTI test, LODO calibration (16 drives) - primary: run-level detection (row-level in brackets)**

| layer | FA clean runs | FA normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | slow drift <0.5 m/s within 30 s | AUC (row) |
|---|---|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 1.58% | 1.53% | 39% (34%) | 43% (46%) | 100% (72%) | 89% (87%) | 41% (47%) | 49% (33%) | 14% of 14 | 0.847 |
| gps.ekf_nis | 0.44% | 0.57% | 26% (12%) | 36% (42%) | 100% (41%) | 76% (83%) | 80% (42%) | 66% (48%) | 14% of 14 | 0.865 |
| gps.cusum_ekf | 2.53% | 1.78% | 80% (59%) | 67% (60%) | 100% (99%) | 84% (87%) | 23% (4%) | 29% (8%) | 43% of 14 | 0.791 |
| gps.cusum_dr | 1.64% | 1.27% | 70% (44%) | 61% (55%) | 100% (100%) | 84% (87%) | 70% (60%) | 61% (65%) | 14% of 14 | 0.846 |
| gps.cusum_dr_noscale | 4.42% | 1.60% | 20% (23%) | 34% (37%) | 100% (99%) | 77% (81%) | 30% (39%) | 34% (41%) | 7% of 14 | 0.849 |
| gps.cusum_dr_nofreeze | 1.83% | 1.30% | 69% (43%) | 60% (55%) | 100% (98%) | 84% (87%) | 67% (53%) | 61% (58%) | 14% of 14 | 0.831 |

**KITTI test, val-only calibration (3 drives): run-level detection (row-level in brackets)**

| layer | FA clean runs | FA normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | slow drift <0.5 m/s within 30 s | AUC (row) |
|---|---|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 0.38% | 0.70% | 34% (30%) | 41% (44%) | 100% (71%) | 89% (86%) | 39% (44%) | 40% (29%) | 7% of 14 | 0.847 |
| gps.ekf_nis | 2.59% | 2.41% | 54% (31%) | 56% (49%) | 100% (59%) | 81% (84%) | 97% (66%) | 79% (61%) | 14% of 14 | 0.865 |
| gps.cusum_ekf | 2.65% | 1.92% | 80% (60%) | 67% (60%) | 100% (99%) | 84% (87%) | 23% (4%) | 29% (8%) | 43% of 14 | 0.791 |
| gps.cusum_dr | 1.58% | 1.26% | 70% (44%) | 61% (55%) | 100% (100%) | 84% (87%) | 70% (60%) | 61% (65%) | 14% of 14 | 0.846 |
| gps.cusum_dr_noscale | 10.94% | 5.39% | 64% (52%) | 56% (54%) | 100% (100%) | 83% (87%) | 61% (59%) | 64% (64%) | 29% of 14 | 0.846 |
| gps.cusum_dr_nofreeze | 1.83% | 1.30% | 69% (43%) | 60% (55%) | 100% (98%) | 84% (87%) | 67% (53%) | 61% (58%) | 14% of 14 | 0.831 |

**Detection delay distribution, lodo** (fixes after onset of the first alarm, detected runs only; q10 / q25 / median / q75 / q90; share of ALL runs detected within 10 s / 30 s)

| layer | drift | accel_drift | jump | freeze | doppler_spoof | meaconing |
|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 3/4/5/6/8 ; 36% / 39% | 5/6/6/8/9 ; 41% / 43% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 89% / 89% | 4/5/6/7/7 ; 40% / 41% | 3/4/5/7/8 ; 49% / 49% |
| gps.ekf_nis | 3/3/6/12/14 ; 17% / 26% | 4/5/6/8/9 ; 34% / 36% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 76% / 76% | 1/2/2/3/4 ; 79% / 80% | 1/1/1/3/3 ; 66% / 66% |
| gps.cusum_ekf | 1/1/2/3/5 ; 77% / 80% | 3/3/4/5/6 ; 67% / 67% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 0/2/6/8/18 ; 17% / 23% | 1/1/2/6/12 ; 24% / 29% |
| gps.cusum_dr | 1/1/2/3/5 ; 70% / 70% | 3/3/4/6/7 ; 59% / 61% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 2/3/4/4/5 ; 69% / 70% | 1/2/3/4/5 ; 61% / 61% |

**Detection delay distribution, valonly** (fixes after onset of the first alarm, detected runs only; q10 / q25 / median / q75 / q90; share of ALL runs detected within 10 s / 30 s)

| layer | drift | accel_drift | jump | freeze | doppler_spoof | meaconing |
|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 4/5/5/6/8 ; 33% / 34% | 6/6/7/8/8 ; 40% / 41% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 89% / 89% | 4/6/7/7/8 ; 37% / 39% | 4/4/5/7/9 ; 40% / 40% |
| gps.ekf_nis | 1/2/2/3/6 ; 51% / 54% | 1/4/4/6/8 ; 53% / 56% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 81% / 81% | 1/1/1/2/2 ; 97% / 97% | 1/1/1/1/2 ; 79% / 79% |
| gps.cusum_ekf | 1/1/2/3/5 ; 77% / 80% | 3/3/4/5/6 ; 67% / 67% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 0/2/6/8/18 ; 17% / 23% | 1/1/2/6/12 ; 24% / 29% |
| gps.cusum_dr | 1/1/2/3/5 ; 70% / 70% | 3/3/4/6/7 ; 59% / 61% | 0/0/0/0/0 ; 100% / 100% | 1/1/1/1/1 ; 84% / 84% | 2/3/4/4/5 ; 69% / 70% | 1/2/3/4/5 ; 61% / 61% |

**FA transfer on test (clean test runs, 1% budget).**

| layer | val-only calibration | LODO calibration | LODO held-out estimate (dev) | worst dev drive |
|---|---|---|---|---|
| gps.dr_resid_10 | 0.38% | 1.58% | 1.21% | 4.28% |
| gps.ekf_nis | 2.59% | 0.44% | 1.30% | 19.50% |
| gps.cusum_ekf | 2.65% | 2.53% | 1.04% | 1.79% |
| gps.cusum_dr | 1.58% | 1.64% | 1.04% | 1.96% |

**Beat-or-not vs B2 (both LODO-calibrated; rule B6: >= +5 points run-level AND clean-run FA <= B2 + 0.5 point).**

| attack | gps.ekf_nis | gps.cusum_ekf | gps.cusum_dr |
|---|---|---|---|
| drift | -13 pts: worse | +41 pts: more detection, higher FA | +31 pts: beats B2 |
| accel_drift | -7 pts: worse | +24 pts: more detection, higher FA | +19 pts: beats B2 |
| jump | +0 pts: no difference | +0 pts: no difference | +0 pts: no difference |
| freeze | -13 pts: worse | -4 pts: no difference | -4 pts: no difference |
| doppler_spoof | +39 pts: beats B2 | -19 pts: worse | +29 pts: beats B2 |
| meaconing | +17 pts: beats B2 | -20 pts: worse | +13 pts: beats B2 |

**L2c on clean TEST runs: scale convergence** (|s_hat - s*|/s*, median over runs that reach that time; prior error = |1 - s*|)

| prior median | prior RMS | 10 s | 20 s | 30 s | 60 s |
|---|---|---|---|---|---|
| 1.33% | 2.34% | 0.70% (n=50) | 0.28% (n=30) | 0.24% (n=20) | n/a (n=0) |

**L2c on TEST attacks: scale error at onset+30 s (drag) with / without freezing** (s* from the run; frozen = share of the first 30 s with GPS updates skipped)

| attack | runs | at onset | +30 s learn+freeze | +30 s learn, no freeze | +30 s no scale learning | frozen share |
|---|---|---|---|---|---|---|
| drift | 1 | 2.07% | 1.60% | 7.63% | 1.81% | 93% |
| accel_drift | 4 | 0.44% | 0.48% | 7.73% | 1.20% | 82% |
| jump | 2 | 0.19% | 0.19% | 1.58% | 1.35% | 100% |
| freeze | 2 | 1.15% | 1.15% | 87.55% | 2.91% | 97% |
| doppler_spoof | 6 | 0.57% | 0.36% | 2.43% | 1.80% | 82% |
| meaconing | 3 | 0.47% | 0.47% | 7.09% | 0.79% | 97% |

**Absorption on TEST: position-estimate error / reported error at onset+30 s (median, runs with reported error >= 5 m)**

| attack | ungated EKF (S3) | DR branch, no freeze | DR branch, selected (freeze) |
|---|---|---|---|
| drift | 0.43 | 0.72 | 0.06 |
| accel_drift | 0.38 | 0.82 | 0.02 |
| jump | 0.73 | 1.13 | 0.12 |
| freeze | 0.49 | 0.96 | 0.02 |
| doppler_spoof | 0.99 | 0.86 | 0.09 |
| meaconing | 0.97 | 1.13 | 0.21 |

**Harness ablation S4_all, LODO calibration + combiner fitted on the 16 drives**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.922 | 70.6% | 1.14% | 55.9% | 62.2% | 50.4% | 87.5% | 99.9% | 65.7% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.27% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.cusum_ekf | 0.791 | 53.1% | 1.78% | 59.9% | 4.2% | 59.4% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% |
| only_gps.ekf_nis | 0.865 | 45.8% | 0.57% | 42.3% | 41.8% | 12.2% | 82.5% | 41.0% | 48.5% |
| only_gps.jerk | 0.601 | 8.4% | 0.75% | 1.0% | 2.1% | 3.3% | 12.7% | 30.0% | 1.1% |
| only_gps.lat_accel | 0.531 | 2.3% | 0.15% | 0.3% | 0.0% | 0.5% | 0.0% | 13.1% | 0.1% |
| only_gps.long_accel | 0.580 | 4.7% | 0.10% | 0.3% | 0.8% | 0.5% | 6.8% | 19.4% | 0.0% |
| only_gps.max_speed | 0.482 | 2.6% | 0.00% | 7.8% | 0.7% | 0.0% | 0.0% | 6.8% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 31.0% | 1.33% | 52.5% | 1.5% | 28.5% | 84.6% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 1.0% | 0.58% | 0.1% | 0.0% | 0.2% | 0.1% | 5.1% | 0.7% |
| all_but_gps.cusum_dr | 0.914 | 66.8% | 1.44% | 55.5% | 59.4% | 54.6% | 87.2% | 92.5% | 49.4% |
| all_but_gps.cusum_ekf | 0.917 | 70.0% | 1.12% | 55.0% | 62.7% | 45.6% | 87.2% | 99.4% | 67.1% |
| all_but_gps.dr_resid_10 | 0.915 | 69.9% | 1.17% | 55.6% | 61.5% | 45.6% | 87.3% | 99.9% | 66.6% |
| all_but_gps.ekf_nis | 0.912 | 69.8% | 1.24% | 55.5% | 59.4% | 49.6% | 87.6% | 100.0% | 64.5% |
| all_but_gps.jerk | 0.921 | 70.7% | 1.20% | 56.1% | 62.4% | 50.5% | 87.6% | 99.9% | 65.5% |
| all_but_gps.lat_accel | 0.922 | 70.6% | 1.14% | 55.9% | 62.3% | 50.4% | 87.5% | 99.9% | 65.5% |
| all_but_gps.long_accel | 0.924 | 70.1% | 1.00% | 55.4% | 61.5% | 49.8% | 87.5% | 99.9% | 64.5% |
| all_but_gps.max_speed | 0.914 | 70.9% | 1.11% | 55.5% | 62.3% | 50.4% | 87.3% | 99.9% | 67.8% |
| all_but_gps.vel_pos_consistency | 0.922 | 70.4% | 1.27% | 55.9% | 61.8% | 50.1% | 87.3% | 99.9% | 64.8% |
| all_but_gps.yaw_rate | 0.919 | 70.8% | 1.39% | 56.1% | 61.8% | 51.3% | 87.3% | 99.9% | 66.3% |

**Harness ablation S4_base_dr, LODO calibration + combiner fitted on the 16 drives**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.917 | 70.0% | 1.12% | 55.0% | 62.7% | 45.6% | 87.2% | 99.4% | 67.1% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.27% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% |
| only_gps.ekf_nis | 0.865 | 45.8% | 0.57% | 42.3% | 41.8% | 12.2% | 82.5% | 41.0% | 48.5% |
| only_gps.jerk | 0.601 | 8.4% | 0.75% | 1.0% | 2.1% | 3.3% | 12.7% | 30.0% | 1.1% |
| only_gps.lat_accel | 0.531 | 2.3% | 0.15% | 0.3% | 0.0% | 0.5% | 0.0% | 13.1% | 0.1% |
| only_gps.long_accel | 0.580 | 4.7% | 0.10% | 0.3% | 0.8% | 0.5% | 6.8% | 19.4% | 0.0% |
| only_gps.max_speed | 0.482 | 2.6% | 0.00% | 7.8% | 0.7% | 0.0% | 0.0% | 6.8% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 31.0% | 1.33% | 52.5% | 1.5% | 28.5% | 84.6% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 1.0% | 0.58% | 0.1% | 0.0% | 0.2% | 0.1% | 5.1% | 0.7% |
| all_but_gps.cusum_dr | 0.900 | 62.8% | 1.29% | 51.6% | 65.2% | 42.6% | 86.6% | 71.8% | 55.4% |
| all_but_gps.dr_resid_10 | 0.906 | 69.7% | 1.20% | 55.2% | 61.8% | 44.7% | 87.1% | 100.0% | 66.4% |
| all_but_gps.ekf_nis | 0.907 | 69.1% | 1.12% | 55.1% | 59.9% | 45.0% | 87.3% | 99.7% | 64.9% |
| all_but_gps.jerk | 0.917 | 69.9% | 1.17% | 55.5% | 62.4% | 44.8% | 87.2% | 99.4% | 66.9% |
| all_but_gps.lat_accel | 0.918 | 70.0% | 1.17% | 55.1% | 62.7% | 45.4% | 87.2% | 99.4% | 67.1% |
| all_but_gps.long_accel | 0.920 | 69.5% | 0.94% | 54.8% | 61.5% | 44.3% | 87.3% | 99.3% | 66.4% |
| all_but_gps.max_speed | 0.908 | 69.9% | 1.11% | 55.0% | 62.3% | 45.3% | 87.2% | 99.4% | 67.1% |
| all_but_gps.vel_pos_consistency | 0.917 | 69.9% | 1.14% | 55.0% | 62.8% | 45.1% | 87.2% | 99.4% | 67.1% |
| all_but_gps.yaw_rate | 0.915 | 70.1% | 1.35% | 55.4% | 61.9% | 45.9% | 87.2% | 99.7% | 67.7% |

**Harness ablation S4_base_ekfcusum, LODO calibration + combiner fitted on the 16 drives**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.914 | 66.8% | 1.44% | 55.5% | 59.4% | 54.6% | 87.2% | 92.5% | 49.4% |
| only_gps.cusum_ekf | 0.791 | 53.1% | 1.78% | 59.9% | 4.2% | 59.4% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% |
| only_gps.ekf_nis | 0.865 | 45.8% | 0.57% | 42.3% | 41.8% | 12.2% | 82.5% | 41.0% | 48.5% |
| only_gps.jerk | 0.601 | 8.4% | 0.75% | 1.0% | 2.1% | 3.3% | 12.7% | 30.0% | 1.1% |
| only_gps.lat_accel | 0.531 | 2.3% | 0.15% | 0.3% | 0.0% | 0.5% | 0.0% | 13.1% | 0.1% |
| only_gps.long_accel | 0.580 | 4.7% | 0.10% | 0.3% | 0.8% | 0.5% | 6.8% | 19.4% | 0.0% |
| only_gps.max_speed | 0.482 | 2.6% | 0.00% | 7.8% | 0.7% | 0.0% | 0.0% | 6.8% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 31.0% | 1.33% | 52.5% | 1.5% | 28.5% | 84.6% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 1.0% | 0.58% | 0.1% | 0.0% | 0.2% | 0.1% | 5.1% | 0.7% |
| all_but_gps.cusum_ekf | 0.900 | 62.8% | 1.29% | 51.6% | 65.2% | 42.6% | 86.6% | 71.8% | 55.4% |
| all_but_gps.dr_resid_10 | 0.897 | 60.0% | 1.02% | 54.2% | 31.7% | 52.2% | 86.6% | 92.5% | 41.1% |
| all_but_gps.ekf_nis | 0.893 | 61.3% | 1.57% | 55.4% | 43.5% | 54.9% | 87.7% | 90.8% | 33.1% |
| all_but_gps.jerk | 0.912 | 66.6% | 1.47% | 55.9% | 59.0% | 53.8% | 87.3% | 92.8% | 48.7% |
| all_but_gps.lat_accel | 0.914 | 66.8% | 1.44% | 55.5% | 59.5% | 54.6% | 87.2% | 92.5% | 49.2% |
| all_but_gps.long_accel | 0.916 | 66.2% | 1.30% | 55.1% | 57.7% | 53.8% | 87.3% | 92.5% | 48.3% |
| all_but_gps.max_speed | 0.909 | 66.8% | 1.41% | 55.1% | 59.4% | 54.0% | 87.2% | 94.4% | 48.6% |
| all_but_gps.vel_pos_consistency | 0.913 | 66.2% | 1.54% | 56.7% | 57.9% | 54.9% | 87.7% | 88.8% | 48.9% |
| all_but_gps.yaw_rate | 0.910 | 67.9% | 1.84% | 57.2% | 60.3% | 55.7% | 87.5% | 92.9% | 51.8% |

**Harness ablation S4_l2b_pair, LODO calibration + combiner fitted on the 16 drives**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.912 | 72.2% | 1.33% | 57.2% | 63.2% | 54.7% | 87.6% | 100.0% | 68.2% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.27% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.cusum_ekf | 0.791 | 53.1% | 1.78% | 59.9% | 4.2% | 59.4% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 53.7% | 1.53% | 45.8% | 46.6% | 33.6% | 86.6% | 71.9% | 33.1% |
| only_gps.ekf_nis | 0.865 | 45.8% | 0.57% | 42.3% | 41.8% | 12.2% | 82.5% | 41.0% | 48.5% |
| all_but_gps.cusum_dr | 0.906 | 67.5% | 1.44% | 57.3% | 56.0% | 54.9% | 87.7% | 99.3% | 47.9% |
| all_but_gps.cusum_ekf | 0.907 | 70.9% | 1.30% | 55.4% | 64.7% | 47.4% | 87.6% | 100.0% | 67.7% |
| all_but_gps.dr_resid_10 | 0.913 | 72.4% | 1.29% | 57.4% | 63.0% | 55.3% | 87.3% | 100.0% | 69.5% |
| all_but_gps.ekf_nis | 0.892 | 71.4% | 1.71% | 57.6% | 59.9% | 56.4% | 87.8% | 100.0% | 65.0% |

**Harness ablation S4_all, val-only (3 drives)**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.903 | 73.0% | 2.20% | 55.9% | 67.3% | 51.9% | 87.5% | 100.0% | 73.4% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.26% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.cusum_ekf | 0.791 | 53.3% | 1.92% | 60.4% | 4.2% | 60.0% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% |
| all_but_gps.cusum_dr | 0.893 | 68.3% | 2.14% | 55.7% | 58.2% | 51.8% | 87.5% | 99.2% | 54.9% |
| all_but_gps.cusum_ekf | 0.911 | 71.1% | 1.41% | 55.0% | 69.0% | 45.9% | 87.5% | 96.1% | 70.2% |
| all_but_gps.dr_resid_10 | 0.901 | 72.9% | 2.20% | 55.9% | 67.3% | 51.9% | 87.0% | 100.0% | 73.4% |
| all_but_gps.ekf_nis | 0.898 | 71.3% | 1.41% | 56.5% | 60.7% | 55.7% | 87.8% | 100.0% | 65.3% |
| all_but_gps.jerk | 0.902 | 73.0% | 2.08% | 55.7% | 67.3% | 51.9% | 87.5% | 100.0% | 73.4% |
| all_but_gps.lat_accel | 0.907 | 72.9% | 1.60% | 55.6% | 67.1% | 51.9% | 87.5% | 100.0% | 73.4% |
| all_but_gps.long_accel | 0.902 | 73.0% | 2.19% | 55.9% | 67.3% | 51.9% | 87.5% | 100.0% | 73.4% |
| all_but_gps.max_speed | 0.905 | 73.0% | 2.20% | 55.9% | 67.3% | 51.9% | 87.5% | 100.0% | 73.4% |
| all_but_gps.vel_pos_consistency | 0.903 | 72.7% | 2.13% | 55.1% | 67.2% | 51.0% | 87.5% | 100.0% | 73.4% |
| all_but_gps.yaw_rate | 0.904 | 73.0% | 2.07% | 55.9% | 67.3% | 51.9% | 87.5% | 100.0% | 73.3% |

**Harness ablation S4_base_dr, val-only (3 drives)**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.911 | 71.1% | 1.41% | 55.0% | 69.0% | 45.9% | 87.5% | 96.1% | 70.2% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.26% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% |
| all_but_gps.cusum_dr | 0.896 | 64.7% | 1.90% | 52.6% | 70.0% | 42.0% | 86.8% | 72.1% | 60.4% |
| all_but_gps.dr_resid_10 | 0.899 | 72.4% | 1.68% | 55.4% | 70.8% | 44.8% | 87.2% | 99.3% | 73.5% |
| all_but_gps.ekf_nis | 0.892 | 69.6% | 1.06% | 54.6% | 61.0% | 46.4% | 87.7% | 99.9% | 65.2% |
| all_but_gps.jerk | 0.894 | 71.2% | 1.92% | 52.2% | 68.5% | 41.2% | 87.3% | 100.0% | 74.4% |
| all_but_gps.lat_accel | 0.900 | 71.1% | 1.44% | 52.1% | 68.3% | 41.2% | 87.3% | 100.0% | 74.4% |
| all_but_gps.long_accel | 0.894 | 71.2% | 2.02% | 52.3% | 68.5% | 41.2% | 87.3% | 100.0% | 74.4% |
| all_but_gps.max_speed | 0.897 | 71.2% | 2.05% | 52.3% | 68.5% | 41.2% | 87.3% | 100.0% | 74.4% |
| all_but_gps.vel_pos_consistency | 0.911 | 70.6% | 1.39% | 55.2% | 68.0% | 45.7% | 87.5% | 95.4% | 68.9% |
| all_but_gps.yaw_rate | 0.896 | 71.1% | 1.80% | 52.3% | 68.5% | 41.2% | 87.3% | 100.0% | 74.0% |

**Harness ablation S4_base_ekfcusum, val-only (3 drives)**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.893 | 68.3% | 2.14% | 55.7% | 58.2% | 51.8% | 87.5% | 99.2% | 54.9% |
| only_gps.cusum_ekf | 0.791 | 53.3% | 1.92% | 60.4% | 4.2% | 60.0% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% |
| all_but_gps.cusum_ekf | 0.896 | 64.7% | 1.90% | 52.6% | 70.0% | 42.0% | 86.8% | 72.1% | 60.4% |
| all_but_gps.dr_resid_10 | 0.879 | 65.2% | 2.35% | 56.0% | 44.3% | 52.2% | 87.0% | 99.2% | 50.7% |
| all_but_gps.ekf_nis | 0.883 | 62.2% | 2.11% | 55.5% | 47.0% | 54.6% | 87.7% | 93.2% | 33.0% |
| all_but_gps.jerk | 0.908 | 70.0% | 2.17% | 56.1% | 67.6% | 54.9% | 87.3% | 94.4% | 57.2% |
| all_but_gps.lat_accel | 0.898 | 68.2% | 1.54% | 55.5% | 57.9% | 51.8% | 87.5% | 99.2% | 54.9% |
| all_but_gps.long_accel | 0.892 | 69.1% | 2.34% | 56.0% | 60.7% | 52.2% | 87.5% | 99.2% | 56.8% |
| all_but_gps.max_speed | 0.895 | 69.1% | 2.37% | 56.0% | 60.7% | 52.2% | 87.5% | 99.2% | 56.8% |
| all_but_gps.vel_pos_consistency | 0.893 | 68.6% | 2.26% | 55.1% | 60.6% | 50.4% | 87.5% | 99.2% | 56.5% |
| all_but_gps.yaw_rate | 0.895 | 69.1% | 2.13% | 56.0% | 60.7% | 52.2% | 87.5% | 99.2% | 56.4% |

**Harness ablation S4_l2b_pair, val-only (3 drives)**

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing |
|---|---|---|---|---|---|---|---|---|---|
| all | 0.913 | 74.7% | 1.93% | 56.9% | 72.2% | 53.6% | 87.7% | 100.0% | 75.3% |
| only_gps.cusum_dr | 0.846 | 69.1% | 1.26% | 55.2% | 59.9% | 44.3% | 87.2% | 100.0% | 65.2% |
| only_gps.cusum_ekf | 0.791 | 53.3% | 1.92% | 60.4% | 4.2% | 60.0% | 87.5% | 99.3% | 7.5% |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% |
| all_but_gps.cusum_dr | 0.907 | 71.5% | 1.98% | 57.3% | 67.2% | 54.6% | 87.8% | 99.3% | 60.7% |
| all_but_gps.cusum_ekf | 0.908 | 72.4% | 1.38% | 55.7% | 69.3% | 45.9% | 87.7% | 100.0% | 72.6% |
| all_but_gps.dr_resid_10 | 0.913 | 75.6% | 2.31% | 58.0% | 73.0% | 57.2% | 87.5% | 100.0% | 76.3% |
| all_but_gps.ekf_nis | 0.892 | 71.4% | 1.47% | 57.8% | 59.4% | 56.6% | 87.8% | 100.0% | 65.0% |

**UAV (EKF-based CUSUM only; threshold from the benign flight at 1%, in-sample)**

| layer | alarms before 117 s | first alarm >= 118 s | delay (s) | share of fixes from 118 s flagged | benign alarms | jamming alarms |
|---|---|---|---|---|---|---|
| cusum_ekf_nis_k1.5 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 2/248 | 48/224 |
| cusum_ekf_nis_k0.5 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 2/248 | 48/224 |
| cusum_ekf_nis_k1.0 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 2/248 | 48/224 |
| cusum_ekf_axis_k1.5 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 1/248 | 14/224 |
| cusum_ekf_axis_k0.5 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 2/248 | 46/224 |
| cusum_ekf_axis_k1.0 | 0/118 | 118.000345 | 0.00034499999999582087 | 100% | 2/248 | 36/224 |
