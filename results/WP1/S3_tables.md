### Tuning (TRAIN / VAL only)

KITTI receiver error (train clean, reported - true): phi 0.897, sigma 0.981 m; q_acc = 0.1 m/s^2 (grid on train clean, mean NIS / dim closest to 1); gate level (val) 0.99; primary variant chosen on val: **ungated**.

| gate level (val) | mean run-level detection over 6 attacks at val 1% budget |
|---|---|
| 0.0 | 0.833 |
| 0.99 | 0.828 |
| 0.999 | 0.828 |
| 0.9999 | 0.828 |

### Filter consistency (NIS)

| data | rows | mean NIS | mean dim | ratio | fraction above chi2 95% |
|---|---|---|---|---|---|
| KITTI train clean (tuned on) | 2531 | 6.17 | 5.71 | 1.08 | 8.0% |
| KITTI val clean | 540 | 4.81 | 5.66 | 0.85 | 5.4% |
| KITTI test clean runs | 1512 | 6.62 | 5.93 | 1.12 | 10.6% |
| AV-GPS train normal (tuned on) | 38356 | 10.89 | 3.30 | 3.30 | 5.0% |
| AV-GPS val normal | 7926 | 2.13 | 3.07 | 0.69 | 3.4% |
| UAV benign flight (tuned on) | 247 | 3.01 | 4.00 | 0.75 | 6.1% |

### KITTI test: run-level detection (row-level in brackets), val-calibrated 1% operating point

| layer | FA clean runs | FA all normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | drift<0.5 m/s within 30 s |
|---|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 0.38% | 0.70% | 34% (29.8%) | 41% (43.7%) | 100% (70.8%) | 89% (86.2%) | 39% (44.3%) | 40% (28.7%) | 7% of 14 |
| gps.ekf_nis | 2.59% | 2.41% | 54% (31.2%) | 56% (49.3%) | 100% (58.6%) | 81% (84.3%) | 97% (65.7%) | 79% (60.9%) | 14% of 14 |
| gps.ekf_nis_gated | 6.32% | 4.09% | 57% (40.6%) | 51% (52.6%) | 100% (100.0%) | 83% (86.2%) | 100% (82.5%) | 77% (80.2%) | 14% of 14 |

Median detection delay (s): gps.dr_resid_10: drift 5.0, accel_drift 7.0, jump 0.0, freeze 1.0, doppler_spoof 7.0, meaconing 5.0; gps.ekf_nis: drift 2.0, accel_drift 4.0, jump 0.0, freeze 1.0, doppler_spoof 1.0, meaconing 1.0; gps.ekf_nis_gated: drift 3.0, accel_drift 5.0, jump 0.0, freeze 1.0, doppler_spoof 1.0, meaconing 1.0

### KITTI test DIAGNOSTIC, equal false alarms (oracle threshold on the test clean runs, 1%; not an operating point)

| layer | FA clean runs | drift | accel_drift | jump | freeze | doppler_spoof | meaconing | drift<0.5 within 30 s |
|---|---|---|---|---|---|---|---|---|
| gps.dr_resid_10 | 0.95% | 36% | 43% | 100% | 89% | 40% | 46% | 14% |
| gps.ekf_nis | 0.95% | 39% | 44% | 100% | 79% | 87% | 71% | 14% |
| gps.ekf_nis_gated | 0.95% | 33% | 40% | 100% | 77% | 77% | 64% | 0% |

### Beat-or-not vs B2 (rule A4, as written: >= 5 points higher run-level detection AND clean-run FA <= B2 + 0.5 point)

| attack | EKF - B2 (run-level, points) | verdict by rule A4 |
|---|---|---|
| drift | +20 | more detection but at higher FA than B2: rule A4 not satisfied (see equal-FA table) |
| accel_drift | +14 | more detection but at higher FA than B2: rule A4 not satisfied (see equal-FA table) |
| jump | +0 | no difference (within 5 points) |
| freeze | -7 | worse than B2 |
| doppler_spoof | +59 | more detection but at higher FA than B2: rule A4 not satisfied (see equal-FA table) |
| meaconing | +39 | more detection but at higher FA than B2: rule A4 not satisfied (see equal-FA table) |

FA condition (EKF clean-run FA <= B2 + 0.5 point) met: False.

### Absorption: position-estimate error vs truth at onset +10 s / +30 s (median over test attack runs), ungated and gated

| attack | reported error +10 s | estimate error ungated | estimate error gated | reported +30 s | estimate ungated | estimate gated | absorbed fraction +30 s ungated / gated (runs with reported error >= 5 m) | fraction of runs in hold +30 s (gated) |
|---|---|---|---|---|---|---|---|---|
| drift | 7.7 | 3.4 | 2.0 | 45.7 | 19.7 | 2.5 | 0.43 / 0.05 (n=1) | 1.00 |
| accel_drift | 14.9 | 4.3 | 1.7 | 151.2 | 58.3 | 5.8 | 0.38 / 0.05 (n=4) | 1.00 |
| jump | 27.0 | 12.8 | 2.1 | 14.1 | 10.3 | 6.5 | 0.73 / 0.84 (n=2) | 1.00 |
| freeze | 91.1 | 34.6 | 2.7 | 378.3 | 182.0 | 13.9 | 0.49 / 0.03 (n=2) | 1.00 |
| doppler_spoof | 13.9 | 13.4 | 1.9 | 54.5 | 53.9 | 4.8 | 0.99 / 0.16 (n=6) | 1.00 |
| meaconing | 11.0 | 11.0 | 2.2 | 37.9 | 36.8 | 4.6 | 0.97 / 0.18 (n=3) | 1.00 |

Clean runs: median estimate error 1.11 m vs reported 1.18 m (ungated); gated 1.18 m.

### KITTI harness ablation (val 1% budget, test one pass; row-level)

**S3_kitti_all**


| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.896 | 64.7% | 1.90% | 52.6% | 70.0% | 42.0% | 86.8% | 72.1% | 60.4% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% | 0.0 |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% | 0.0 |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% | 1.0 |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% | 0.0 |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% | 1.0 |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% | 0.0 |
| all_but_gps.dr_resid_10 | 0.867 | 59.8% | 2.23% | 50.3% | 69.0% | 32.1% | 84.9% | 57.9% | 59.5% | 1.0 |
| all_but_gps.ekf_nis | 0.860 | 55.3% | 1.39% | 49.9% | 46.2% | 39.7% | 86.6% | 71.8% | 33.7% | 1.0 |
| all_but_gps.jerk | 0.894 | 64.7% | 1.90% | 52.3% | 70.2% | 41.6% | 86.8% | 71.9% | 61.4% | 1.0 |
| all_but_gps.lat_accel | 0.896 | 64.1% | 1.75% | 51.8% | 69.2% | 41.2% | 86.7% | 71.8% | 60.0% | 1.0 |
| all_but_gps.long_accel | 0.898 | 63.2% | 1.45% | 50.8% | 68.0% | 39.5% | 86.7% | 70.8% | 58.9% | 1.0 |
| all_but_gps.max_speed | 0.893 | 63.7% | 1.62% | 51.3% | 69.0% | 41.2% | 86.2% | 70.0% | 60.3% | 1.0 |
| all_but_gps.vel_pos_consistency | 0.895 | 64.5% | 1.80% | 52.0% | 70.2% | 41.1% | 86.8% | 71.9% | 60.6% | 1.0 |
| all_but_gps.yaw_rate | 0.894 | 64.9% | 2.07% | 53.0% | 69.3% | 42.3% | 86.8% | 72.8% | 61.4% | 1.0 |

**S3_kitti_b2_ekf**


| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.892 | 64.9% | 1.83% | 51.3% | 70.6% | 39.7% | 86.3% | 73.6% | 63.6% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |

**S3_kitti_all_gated**


| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.910 | 73.4% | 3.52% | 53.8% | 77.2% | 44.2% | 87.6% | 98.3% | 75.9% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.ekf_nis_gated | 0.902 | 74.3% | 4.09% | 52.6% | 82.5% | 40.6% | 86.2% | 100.0% | 80.2% | 1.0 |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% | 0.0 |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% | 0.0 |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% | 1.0 |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% | 0.0 |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% | 1.0 |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% | 0.0 |
| all_but_gps.dr_resid_10 | 0.902 | 73.2% | 2.89% | 51.4% | 80.6% | 40.9% | 86.2% | 97.8% | 78.6% | 1.0 |
| all_but_gps.ekf_nis_gated | 0.860 | 55.3% | 1.39% | 49.9% | 46.2% | 39.7% | 86.6% | 71.8% | 33.7% | 1.0 |
| all_but_gps.jerk | 0.909 | 73.8% | 3.56% | 54.2% | 78.2% | 44.0% | 87.6% | 98.8% | 76.7% | 1.0 |
| all_but_gps.lat_accel | 0.910 | 74.1% | 3.73% | 54.0% | 79.0% | 44.7% | 87.7% | 98.6% | 77.0% | 1.0 |
| all_but_gps.long_accel | 0.912 | 72.1% | 2.70% | 52.1% | 75.4% | 41.6% | 87.3% | 98.2% | 74.5% | 1.0 |
| all_but_gps.max_speed | 0.907 | 73.4% | 3.38% | 53.3% | 78.2% | 43.4% | 87.5% | 98.6% | 76.3% | 1.0 |
| all_but_gps.vel_pos_consistency | 0.909 | 73.4% | 3.53% | 52.7% | 78.2% | 42.6% | 87.6% | 98.8% | 77.0% | 1.0 |
| all_but_gps.yaw_rate | 0.909 | 74.3% | 4.10% | 55.6% | 78.2% | 45.3% | 87.6% | 99.0% | 76.9% | 1.0 |

**S3_kitti_ekf_pair**


| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.903 | 74.4% | 4.19% | 52.6% | 82.7% | 40.9% | 86.2% | 100.0% | 80.5% | 1.0 |
| only_gps.ekf_nis | 0.865 | 59.2% | 2.41% | 49.3% | 65.7% | 31.2% | 84.3% | 58.6% | 60.9% | 1.0 |
| only_gps.ekf_nis_gated | 0.902 | 74.3% | 4.09% | 52.6% | 82.5% | 40.6% | 86.2% | 100.0% | 80.2% | 1.0 |

### AV-GPS test (position + speed + heading only)

| variant | FA normal rows | detection attack rows | AUC | attack rows flagged / with step > 100 km | detection excluding step > 100 km rows |
|---|---|---|---|---|---|
| ungated | 3.97% (215/5415) | 26% | 0.304 | 554 / 25 | 25% (2086 rows) |
| gated | 8.42% (456/5415) | 24% | 0.319 | 516 / 25 | 24% (2086 rows) |

### UAV (noise and threshold from the benign flight)

| variant | benign FA (in-sample) | spoofing: alarms before 117 s | first alarm >= 118 s | fraction of fixes 118-138 s flagged | fraction of fixes in hold from 118 s | jamming flight alarms |
|---|---|---|---|---|---|---|
| ungated | 0.81% | 1/118 (0.85%) | 118.000 s | 63% | 0% | 18/224 |
| gated | 0.81% | 0/118 (0.00%) | 118.000 s | 58% | 100% | 11/224 |
