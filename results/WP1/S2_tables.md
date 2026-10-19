### KITTI: per layer at its operating point, test (run-level detection = fraction of attack runs with >= 1 alarm after onset; row-level in brackets)

| layer | operating point | FA clean runs | FA all normal rows | drift | accel_drift | jump | freeze | doppler_spoof | meaconing |
|---|---|---|---|---|---|---|---|---|---|
| gps.max_speed | physical limit (raw >= 1) | 0.00% | 0.00% | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) |
| gps.long_accel | physical limit (raw >= 1) | 0.00% | 0.00% | 0% (0.0%) | 0% (0.0%) | 80% (15.1%) | 14% (1.3%) | 0% (0.0%) | 0% (0.0%) |
| gps.lat_accel | physical limit (raw >= 1) | 0.00% | 0.00% | 0% (0.0%) | 0% (0.0%) | 26% (4.9%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) |
| gps.jerk | physical limit (raw >= 1) | 0.00% | 0.00% | 0% (0.0%) | 0% (0.0%) | 59% (5.7%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) |
| gps.yaw_rate | physical limit (raw >= 1) | 0.00% | 0.01% | 0% (0.0%) | 0% (0.0%) | 7% (1.4%) | 0% (0.0%) | 0% (0.0%) | 0% (0.0%) |
| gps.vel_pos_consistency | validation 1% budget, tie-safe | 1.26% | 1.11% | 70% (27.3%) | 56% (51.6%) | 100% (11.5%) | 84% (84.3%) | 16% (1.5%) | 17% (1.9%) |
| gps.dr_resid_10 | validation 1% budget, tie-safe | 0.38% | 0.70% | 34% (29.8%) | 41% (43.7%) | 100% (70.8%) | 89% (86.2%) | 39% (44.3%) | 40% (28.7%) |
| UNION physical kinematic (5 rules) |  | 0.00% | 0.01% | 0% (0.0%) | 0% (0.0%) | 86% (16.5%) | 14% (1.3%) | 0% (0.0%) | 0% (0.0%) |
| B2 OR physical union |  | 0.38% | 0.72% | 34% (29.8%) | 41% (43.7%) | 100% (70.8%) | 89% (86.2%) | 39% (44.3%) | 40% (28.7%) |
| B2 OR every L1 rule at its operating point |  | 1.64% | 1.83% | 71% (43.4%) | 57% (52.9%) | 100% (71.9%) | 89% (86.3%) | 46% (45.1%) | 49% (30.1%) |

Median delay (s) of the detected runs: gps.max_speed: ; gps.long_accel: jump 0, freeze 1; gps.lat_accel: jump 0; gps.jerk: jump 1; gps.yaw_rate: jump 0; gps.vel_pos_consistency: drift 2, accel_drift 4, jump 0, freeze 1, doppler_spoof 9, meaconing 3; gps.dr_resid_10: drift 5, accel_drift 7, jump 0, freeze 1, doppler_spoof 7, meaconing 5

### KITTI: margin to the physical limits (raw ratio, 1.0 = limit)

| rule | max on val normal | max on test clean runs | p99 on test clean runs |
|---|---|---|---|
| r_speed | 0.319 | 0.274 | 0.264 |
| r_long | 0.262 | 0.251 | 0.173 |
| r_lat | 0.215 | 0.268 | 0.183 |
| r_jerk | 0.087 | 0.103 | 0.069 |
| r_yaw | 0.868 | 0.767 | 0.444 |

### KITTI: harness ablation (budget 1% on validation normal rows; test, one pass)

**S2_kitti_all** (combiner: logistic)

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.860 | 55.3% | 1.39% | 49.9% | 46.2% | 39.7% | 86.6% | 71.8% | 33.7% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% | 0.0 |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% | 0.0 |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% | 1.0 |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% | 0.0 |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% | 1.0 |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% | 0.0 |
| all_but_gps.dr_resid_10 | 0.709 | 31.5% | 1.41% | 47.8% | 1.6% | 18.0% | 83.8% | 30.0% | 1.9% | 1.0 |
| all_but_gps.jerk | 0.858 | 55.2% | 1.38% | 50.1% | 46.8% | 39.7% | 86.6% | 71.4% | 32.7% | 1.0 |
| all_but_gps.lat_accel | 0.861 | 55.3% | 1.45% | 50.0% | 46.0% | 39.7% | 86.6% | 71.8% | 34.0% | 1.0 |
| all_but_gps.long_accel | 0.863 | 54.6% | 1.12% | 48.8% | 45.8% | 37.8% | 86.5% | 71.9% | 32.7% | 1.0 |
| all_but_gps.max_speed | 0.851 | 51.6% | 0.63% | 47.0% | 42.3% | 34.7% | 85.9% | 70.8% | 24.5% | 1.0 |
| all_but_gps.vel_pos_consistency | 0.855 | 52.9% | 0.99% | 44.3% | 45.2% | 33.0% | 86.6% | 71.7% | 32.3% | 1.0 |
| all_but_gps.yaw_rate | 0.860 | 56.2% | 1.65% | 50.3% | 47.8% | 40.9% | 86.6% | 71.7% | 35.9% | 1.0 |

**S2_kitti_b2_kinematic** (combiner: logistic)

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.855 | 52.9% | 0.99% | 44.3% | 45.2% | 33.0% | 86.6% | 71.7% | 32.3% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.jerk | 0.601 | 8.6% | 0.87% | 1.4% | 2.2% | 3.9% | 12.7% | 30.3% | 1.1% | 0.0 |
| only_gps.lat_accel | 0.531 | 4.6% | 3.70% | 2.9% | 1.9% | 4.3% | 0.1% | 16.4% | 2.5% | 0.0 |
| only_gps.long_accel | 0.580 | 5.1% | 0.19% | 0.4% | 1.5% | 0.9% | 7.3% | 20.0% | 0.1% | 1.0 |
| only_gps.max_speed | 0.482 | 1.9% | 0.00% | 5.0% | 0.0% | 0.0% | 0.0% | 6.2% | 0.0% | 0.0 |
| only_gps.yaw_rate | 0.506 | 4.9% | 4.16% | 3.4% | 4.0% | 4.3% | 1.0% | 12.1% | 5.2% | 0.0 |
| all_but_gps.dr_resid_10 | 0.579 | 8.8% | 1.38% | 5.7% | 1.3% | 2.3% | 12.3% | 29.7% | 1.1% | 0.0 |
| all_but_gps.jerk | 0.853 | 53.5% | 1.41% | 45.4% | 46.6% | 34.0% | 86.6% | 71.4% | 32.5% | 1.0 |
| all_but_gps.lat_accel | 0.857 | 52.4% | 0.82% | 43.6% | 44.4% | 32.4% | 86.5% | 71.2% | 32.0% | 1.0 |
| all_but_gps.long_accel | 0.858 | 52.7% | 0.90% | 44.4% | 44.7% | 32.4% | 86.6% | 72.1% | 31.2% | 1.0 |
| all_but_gps.max_speed | 0.846 | 49.5% | 0.46% | 41.5% | 41.7% | 27.3% | 85.9% | 70.8% | 24.7% | 1.0 |
| all_but_gps.yaw_rate | 0.855 | 53.7% | 0.97% | 45.2% | 45.9% | 34.1% | 86.5% | 71.7% | 34.7% | 1.0 |

**S2_kitti_b2_velpos** (combiner: noisy_or)

| configuration | AUC | detection | false alarms | det accel_drift | det doppler_spoof | det drift | det freeze | det jump | det meaconing | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.847 | 53.4% | 1.42% | 53.9% | 40.1% | 44.0% | 85.8% | 69.6% | 23.5% | 1.0 |
| only_gps.dr_resid_10 | 0.847 | 51.4% | 0.70% | 43.7% | 44.3% | 29.8% | 86.2% | 70.8% | 28.7% | 1.0 |
| only_gps.vel_pos_consistency | 0.703 | 30.6% | 1.11% | 51.6% | 1.5% | 27.3% | 84.3% | 11.5% | 1.9% | 1.0 |


### AV-GPS (test, physical-limit alarms; thresholds not fitted)

| rule | artefact? | FA normal rows | normal rows flagged | detection attack rows | AUC (calibrated score) |
|---|---|---|---|---|---|
| gps.max_speed | no | 0.00% | 0 | 4.6% | 0.101 |
| gps.long_accel | no | 0.50% | 27 | 9.5% | 0.118 |
| gps.lat_accel | no | 0.00% | 0 | 0.0% | 0.123 |
| gps.jerk | no | 0.15% | 8 | 13.1% | 0.160 |
| gps.yaw_rate | no | 0.11% | 6 | 0.0% | 0.499 |
| gps.sat_low | YES | 0.04% | 2 | 98.8% | 0.994 |
| gps.hdop_high | YES | 0.11% | 6 | 99.4% | 0.999 |
| gps.sat_jump | YES | 0.28% | 15 | 0.8% | 0.381 |
| gps.hdop_jump | YES | 1.68% | 91 | 1.0% | 0.396 |

Union of the five kinematic rules: FA 0.61% (33 of 5415 normal rows), detection 13.7%. Attack rows with a step over 100 km: 1.18%, normal rows: 0.00%.

### UAV live flights (alarm counts; spoofing flight: first spoofed fix 118.0 s)

| rule | operating point | raw threshold | benign alarms | spoof alarms before 117 s | spoof alarms from 118 s | first spoof alarm (s) | jamming alarms |
|---|---|---|---|---|---|---|---|
| gps.fix_invalid | physical limit (raw >= 1) | - | 0 / 248 | 0 / 118 | 0 / 19 | None | 1 / 224 |
| gps.sat_low | physical limit (raw >= 1) | - | 0 / 248 | 0 / 118 | 0 / 19 | None | 0 / 224 |
| gps.hdop_high | physical limit (raw >= 1) | - | 0 / 248 | 0 / 118 | 0 / 19 | None | 0 / 224 |
| gps.sat_jump | benign flight 1% budget | 1 | 0 / 248 | 0 / 118 | 2 / 19 | 118.000345 | 6 / 224 |
| gps.hdop_jump | benign flight 1% budget | 0.17 | 0 / 248 | 0 / 118 | 5 / 19 | 118.000345 | 4 / 224 |
| gps.noise_jump | benign flight 1% budget | 7 | 1 / 248 | 1 / 118 | 3 / 19 | 119.006003 | 17 / 224 |
| gps.jam_ind_jump | benign flight 1% budget | 35 | 1 / 248 | 2 / 118 | 0 / 19 | None | 1 / 224 |
| gps.vel_pos_consistency | benign flight 1% budget | 0.462 | 2 / 248 | 0 / 118 | 12 / 19 | 119.006003 | 20 / 224 |

Union of the UAV rules, spoofing flight: alarms before 117 s 3 (FA 2.54%); first alarm 118.000345 s (delay 0.000 s); fixes flagged from 118 s: 68.4%; rules firing within 2 s: gps.sat_jump, gps.hdop_jump, gps.noise_jump, gps.vel_pos_consistency. Benign flight: 4 / 248 alarms (in-sample for the calibrated rules). Jamming flight (no onset label): 32 / 224 alarms, times [26.0, 39.0, 151.0, 167.0, 172.0, 173.0, 174.0, 175.0, 176.0, 177.0, 178.0, 179.0, 185.0, 186.0, 188.0, 189.0, 190.0, 191.0, 193.0, 194.0, 195.0, 197.0, 202.0, 203.0, 209.0].
