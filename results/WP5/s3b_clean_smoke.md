# S3b real genuine traffic (VALIDATION stand-in (smoke)); thresholds from validation of the same environment

## Mobile: 7440 genuine messages, 96 senders, 76 recordings, 0.74 receiver-hours (validation: 7440 msgs, 96 senders)

| configuration | FA per message [95% CI by recordings] | alarms / receiver-hour | alarm events / hour | senders k=3 | senders k val (k) |
|---|---|---|---|---|---|
| A_physics | 96.67% [93.16%, 98.24%] | 9719 | 132 | 84.4% (81/96) | n/a |
| physics | 0.95% [0.50%, 1.83%] | 96 | 32 | 8.3% (8/96) | 0.0% (k=18) |
| L1 | 0.95% [0.39%, 2.29%] | 96 | 23 | 6.2% (6/96) | 0.0% (k=20) |
| L2 | 0.94% [0.39%, 1.98%] | 95 | 28 | 7.3% (7/96) | 0.0% (k=20) |
| L3 | 0.99% [0.35%, 2.17%] | 100 | 43 | 4.2% (4/96) | 0.0% (k=36) |
| fresh | 0.99% [0.00%, 4.47%] | 100 | 4 | 1.0% (1/96) | 0.0% (k=75) |
| physics+fresh | 1.83% [0.50%, 5.60%] | 184 | 32 | 8.3% (8/96) | 0.0% (k=83) |
| range | 0.73% [0.00%, 1.44%] | 73 | 3 | 2.1% (2/96) | 0.0% (k=40) |
| range_loc | 0.67% [0.00%, 1.28%] | 68 | 4 | 3.1% (3/96) | 0.0% (k=40) |
| physics+range | 0.91% [0.50%, 1.63%] | 92 | 32 | 7.3% (7/96) | 0.0% (k=16) |
| rx | 0.73% [0.00%, 1.44%] | 73 | 3 | 2.1% (2/96) | 0.0% (k=40) |
| physics+rx | 0.91% [0.50%, 1.63%] | 92 | 32 | 7.3% (7/96) | 0.0% (k=16) |

Appearance (data-driven 1% of evaluable first messages): evaluable genuine first messages in this set 29, alarms 0 (per evaluable first message 0.00%, per message 0.000%); physical 300 m design value alarms 34.48% of them.
Range with receiver position: messages 5446; pooled FA among them 0.99%; per-location FA 0.92%.
Row kinds: {'scored': 0.9600806451612903, 'unscored_first_or_gap': 0.018682795698924733, 'exact_repeat': 0.021236559139784946}; FA of B physics on scored rows 0.97%.

Per check FA, A (frozen VeReMi) vs B (V2AIX validation):

| check | A | B |
|---|---|---|
| beacon_rate | 93.43% | 0.90% |
| field_ranges | 64.60% | 0.98% |
| pos_speed | 1.33% | 0.99% |
| pos_heading | 0.00% | 0.99% |
| speed_change | 0.19% | 0.99% |
| implied_speed | 73.27% | 0.99% |
| heading_rate | 0.39% | 0.99% |
| accel_consistency | 0.58% | 0.97% |
| overlap | 0.05% | 0.17% |
| kf_nis | 7.58% | 0.99% |
| kf_cusum_hi | 51.90% | 0.99% |
| track_birth | 0.16% | 0.16% |

| location | messages | recordings | hours | FA B physics | alarms/h B | FA A physics | FA range pooled | FA range per-location |
|---|---|---|---|---|---|---|---|---|
| Mobile/Aachen | 398 | 5 | 0.06 | 4.27% | 268 | 80.40% | 0.00% | 0.75% |
| Mobile/Cologne | 291 | 3 | 0.04 | 0.34% | 28 | 84.88% | 0.00% | 0.00% |
| Mobile/Dusseldorf | 125 | 3 | 0.02 | 7.20% | 518 | 82.40% | 0.00% | 0.00% |
| Mobile/Highway | 6623 | 64 | 0.62 | 0.66% | 71 | 98.46% | 0.82% | 0.71% |
| Mobile/Rural | 3 | 1 | 0.00 | 0.00% | 0 | 33.33% | 0.00% | 0.00% |

Senders with >= 1 B alarm: 16 of 96; with >= 3: 8; their share of all B alarms 83%; kinds among the k>=3 senders: {'no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs)': 8}.

| rank | location | messages | alarms B | alarms A | v max | implied speed max | jump max (m) | kind | top checks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mobile/Aachen | 180 | 17 | 158 | 15.5 | 16.9 | 7 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | heading_rate:50,pos_heading:43,field_ranges:25 |
| 2 | Mobile/Highway | 39 | 9 | 39 | 64.8 | 85.0 | 52 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | field_ranges:39,implied_speed:31,kf_nis:11 |
| 3 | Mobile/Highway | 552 | 8 | 552 | 44.5 | 60.4 | 37 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_cusum_hi:74,beacon_rate:18,kf_nis:12 |
| 4 | Mobile/Dusseldorf | 120 | 7 | 102 | 16.4 | 18.0 | 60 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:14,heading_rate:9,accel_consistency:8 |
| 5 | Mobile/Highway | 634 | 6 | 608 | 40.6 | 54.7 | 163 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:7,accel_consistency:7,speed_change:6 |
| 6 | Mobile/Highway | 1099 | 5 | 1081 | 40.6 | 53.5 | 45 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:29,accel_consistency:24,beacon_rate:17 |
| 7 | Mobile/Highway | 490 | 4 | 490 | 45.2 | 54.7 | 196 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_nis:16,pos_speed:15,accel_consistency:6 |
| 8 | Mobile/Highway | 552 | 3 | 552 | 30.8 | 33.6 | 29 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | overlap:5,speed_change:4 |
| 9 | Mobile/Highway | 584 | 2 | 584 | 45.8 | 61.0 | 137 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | implied_speed:22,field_ranges:9,pos_speed:4 |
| 10 | Mobile/Dusseldorf | 4 | 2 | 1 | 8.6 | 8.4 | 13 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:3,heading_rate:1 |
| 11 | Mobile/Highway | 40 | 2 | 40 | 29.9 | 29.4 | 61 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:3,beacon_rate:2 |
| 12 | Mobile/Highway | 40 | 2 | 40 | 29.0 | 34.4 | 88 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:4,kf_nis:1 |

## Stationary: 33845 genuine messages, 284 senders, 228 recordings, 2.95 receiver-hours (validation: 33845 msgs, 284 senders)

| configuration | FA per message [95% CI by recordings] | alarms / receiver-hour | alarm events / hour | senders k=3 | senders k val (k) |
|---|---|---|---|---|---|
| A_physics | 94.76% [90.99%, 96.93%] | 10888 | 108 | 83.8% (238/284) | n/a |
| physics | 0.99% [0.57%, 1.56%] | 114 | 32 | 9.9% (28/284) | 0.7% (k=22) |
| L1 | 1.00% [0.28%, 2.09%] | 115 | 14 | 5.3% (15/284) | 0.7% (k=25) |
| L2 | 0.99% [0.52%, 1.71%] | 113 | 34 | 10.2% (29/284) | 0.7% (k=14) |
| L3 | 1.00% [0.39%, 2.04%] | 115 | 38 | 7.0% (20/284) | 0.7% (k=15) |
| fresh | 1.00% [0.53%, 1.38%] | 115 | 34 | 11.3% (32/284) | 0.7% (k=22) |
| physics+fresh | 1.98% [1.30%, 2.76%] | 227 | 62 | 19.4% (55/284) | 0.7% (k=38) |
| range | 1.00% [0.43%, 1.87%] | 115 | 12 | 7.0% (20/284) | 0.7% (k=25) |
| range_loc | 0.99% [0.53%, 1.79%] | 114 | 25 | 8.5% (24/284) | 0.7% (k=25) |
| physics+range | 0.99% [0.60%, 1.48%] | 113 | 34 | 9.9% (28/284) | 0.7% (k=22) |
| rx | 1.00% [0.44%, 1.88%] | 115 | 13 | 7.0% (20/284) | 0.7% (k=25) |
| physics+rx | 0.99% [0.61%, 1.48%] | 114 | 34 | 9.9% (28/284) | 0.7% (k=22) |

Appearance (data-driven 1% of evaluable first messages): evaluable genuine first messages in this set 217, alarms 2 (per evaluable first message 0.92%, per message 0.006%); physical 300 m design value alarms 38.71% of them.
Range with receiver position: messages 33845; pooled FA among them 1.00%; per-location FA 0.99%.
Row kinds: {'scored': 0.9339636578519722, 'unscored_first_or_gap': 0.013886837051263111, 'exact_repeat': 0.052149505096764665}; FA of B physics on scored rows 0.95%.

Per check FA, A (frozen VeReMi) vs B (V2AIX validation):

| check | A | B |
|---|---|---|
| beacon_rate | 91.80% | 0.97% |
| field_ranges | 58.73% | 1.00% |
| pos_speed | 1.18% | 1.00% |
| pos_heading | 0.00% | 1.00% |
| speed_change | 0.18% | 0.99% |
| implied_speed | 72.45% | 1.00% |
| heading_rate | 0.28% | 1.00% |
| accel_consistency | 0.54% | 1.00% |
| overlap | 0.06% | 0.11% |
| kf_nis | 5.09% | 1.00% |
| kf_cusum_hi | 44.19% | 1.00% |
| track_birth | 0.16% | 0.16% |

| location | messages | recordings | hours | FA B physics | alarms/h B | FA A physics | FA range pooled | FA range per-location |
|---|---|---|---|---|---|---|---|---|
| Stationary/A44-Jackerath | 24933 | 60 | 1.16 | 0.76% | 163 | 99.83% | 1.36% | 1.00% |
| Stationary/Aachen-Heinrichsallee | 460 | 30 | 0.11 | 0.43% | 19 | 77.83% | 0.00% | 0.87% |
| Stationary/Aachen-Monheimsallee | 550 | 16 | 0.10 | 0.73% | 42 | 89.64% | 0.00% | 0.91% |
| Stationary/Aachen-Ponttor | 3568 | 61 | 0.68 | 1.54% | 81 | 79.82% | 0.00% | 0.98% |
| Stationary/Aachen-Theaterstrasse | 4334 | 61 | 0.90 | 1.96% | 94 | 80.36% | 0.00% | 0.99% |

Senders with >= 1 B alarm: 70 of 284; with >= 3: 28; their share of all B alarms 82%; kinds among the k>=3 senders: {'no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs)': 26, 'parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill': 1, 'GNSS position jump (position moved at > 70 m/s between two CAMs, by >= 15 m)': 1}.

| rank | location | messages | alarms B | alarms A | v max | implied speed max | jump max (m) | kind | top checks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Stationary/A44-Jackerath | 464 | 67 | 464 | 68.5 | 94.2 | 130 | GNSS position jump (position moved at > 70 m/s between two CAMs, by >= 15 m) | field_ranges:165,implied_speed:138,accel_consistency:71 |
| 2 | Stationary/A44-Jackerath | 726 | 40 | 726 | 37.8 | 68.7 | 178 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_cusum_hi:235,kf_nis:38,pos_speed:26 |
| 3 | Stationary/Aachen-Ponttor | 73 | 21 | 72 | 14.1 | 34.3 | 7 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | heading_rate:24,pos_heading:22,field_ranges:20 |
| 4 | Stationary/A44-Jackerath | 304 | 11 | 304 | 43.9 | 63.6 | 73 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_nis:16,implied_speed:14,pos_speed:13 |
| 5 | Stationary/Aachen-Ponttor | 90 | 10 | 59 | 10.2 | 9.4 | 11 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | accel_consistency:18,speed_change:14,pos_speed:2 |
| 6 | Stationary/A44-Jackerath | 233 | 10 | 232 | 31.3 | 41.8 | 99 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | beacon_rate:10,accel_consistency:6,speed_change:5 |
| 7 | Stationary/A44-Jackerath | 652 | 10 | 652 | 42.4 | 55.5 | 142 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | overlap:10,implied_speed:3,pos_speed:2 |
| 8 | Stationary/A44-Jackerath | 868 | 9 | 868 | 41.7 | 52.5 | 173 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | beacon_rate:87,kf_nis:19,accel_consistency:15 |
| 9 | Stationary/A44-Jackerath | 150 | 9 | 150 | 30.3 | 36.9 | 65 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | beacon_rate:6,overlap:3,kf_nis:3 |
| 10 | Stationary/Aachen-Theaterstrasse | 111 | 7 | 103 | 8.6 | 106.4 | 20 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:5,kf_nis:5,beacon_rate:1 |
| 11 | Stationary/Aachen-Theaterstrasse | 62 | 6 | 55 | 9.8 | 13.6 | 19 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:14,heading_rate:12,speed_change:6 |
| 12 | Stationary/A44-Jackerath | 451 | 6 | 451 | 32.5 | 52.9 | 136 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:34,kf_nis:30,overlap:6 |

## Speeds above 70 m/s (all splits, left in the data)

| env | split | location | speed (m/s) | prev / next speed | pos sigma | L1 field_ranges (B) | physics A | physics B | checks alarming (B) |
|---|---|---|---|---|---|---|---|---|---|
| Stationary | train | Stationary/Aachen-Ponttor | 163.82 | 0.02 / 108.46000000000001 | 2.5 | True | True | True | field_ranges,pos_speed,speed_change,implied_speed,accel_consistency,kf_nis |
| Stationary | train | Stationary/Aachen-Ponttor | 108.46 | 163.82 / 108.46000000000001 | 3.3 | True | True | True | field_ranges,speed_change,implied_speed,accel_consistency,kf_nis |
| Stationary | train | Stationary/Aachen-Ponttor | 108.46 | 108.46000000000001 / 8.17 | 4.2 | True | True | True | field_ranges,pos_speed,pos_heading,accel_consistency,kf_nis,kf_cusum_hi |