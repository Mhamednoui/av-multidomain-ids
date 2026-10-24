# S3b real genuine traffic (TEST, scored once); thresholds from validation of the same environment

## Mobile: 4338 genuine messages, 92 senders, 76 recordings, 0.60 receiver-hours (validation: 7440 msgs, 96 senders)

| configuration | FA per message [95% CI by recordings] | alarms / receiver-hour | alarm events / hour | senders k=3 | senders k val (k) |
|---|---|---|---|---|---|
| A_physics | 92.30% [87.97%, 97.17%] | 6676 | 177 | 89.1% (82/92) | n/a |
| physics | 1.15% [0.50%, 1.93%] | 83 | 23 | 7.6% (7/92) | 0.0% (k=18) |
| L1 | 0.37% [0.05%, 0.89%] | 27 | 8 | 2.2% (2/92) | 0.0% (k=20) |
| L2 | 1.34% [0.59%, 2.26%] | 97 | 25 | 7.6% (7/92) | 0.0% (k=20) |
| L3 | 0.55% [0.30%, 1.02%] | 40 | 28 | 3.3% (3/92) | 0.0% (k=36) |
| fresh | 0.00% [0.00%, 0.00%] | 0 | 0 | 0.0% (0/92) | 0.0% (k=75) |
| physics+fresh | 1.15% [0.50%, 1.93%] | 83 | 23 | 7.6% (7/92) | 0.0% (k=83) |
| range | 0.51% [0.00%, 1.53%] | 37 | 5 | 1.1% (1/92) | 0.0% (k=40) |
| range_loc | 1.04% [0.00%, 2.51%] | 75 | 8 | 3.3% (3/92) | 0.0% (k=40) |
| physics+range | 1.27% [0.51%, 2.16%] | 92 | 23 | 6.5% (6/92) | 1.1% (k=16) |
| rx | 0.55% [0.00%, 1.58%] | 40 | 8 | 1.1% (1/92) | 0.0% (k=40) |
| physics+rx | 1.31% [0.58%, 2.22%] | 95 | 27 | 6.5% (6/92) | 1.1% (k=16) |

Appearance (data-driven 1% of evaluable first messages): evaluable genuine first messages in this set 32, alarms 2 (per evaluable first message 6.25%, per message 0.046%); physical 300 m design value alarms 62.50% of them.
Range with receiver position: messages 2955; pooled FA among them 0.74%; per-location FA 1.52%.
Row kinds: {'scored': 0.9144767173812817, 'unscored_first_or_gap': 0.029276164130935915, 'exact_repeat': 0.05624711848778239}; FA of B physics on scored rows 1.11%.

Per check FA, A (frozen VeReMi) vs B (V2AIX validation):

| check | A | B |
|---|---|---|
| beacon_rate | 88.77% | 0.35% |
| field_ranges | 51.80% | 2.47% |
| pos_speed | 0.74% | 0.58% |
| pos_heading | 0.00% | 1.57% |
| speed_change | 0.16% | 1.15% |
| implied_speed | 56.15% | 0.58% |
| heading_rate | 0.81% | 1.43% |
| accel_consistency | 0.28% | 0.60% |
| overlap | 0.12% | 0.12% |
| kf_nis | 2.49% | 0.48% |
| kf_cusum_hi | 7.81% | 0.00% |
| track_birth | 0.25% | 0.25% |

| location | messages | recordings | hours | FA B physics | alarms/h B | FA A physics | FA range pooled | FA range per-location |
|---|---|---|---|---|---|---|---|---|
| Mobile/Aachen | 264 | 5 | 0.05 | 1.89% | 107 | 92.80% | 0.00% | 8.71% |
| Mobile/Cologne | 1229 | 3 | 0.21 | 2.03% | 121 | 83.24% | 0.00% | 0.00% |
| Mobile/Dusseldorf | 242 | 3 | 0.06 | 1.65% | 65 | 83.06% | 0.00% | 0.00% |
| Mobile/Highway | 2595 | 64 | 0.28 | 0.62% | 56 | 97.42% | 0.85% | 0.85% |
| Mobile/Rural | 8 | 1 | 0.00 | 0.00% | 0 | 87.50% | 0.00% | 0.00% |

B physics false alarms by distance to the receiver / by gap since the sender's previous CAM:

| bin | messages | FA |
|---|---|---|
| <100 m | 1215 | 0.25% |
| 100-300 m | 1372 | 2.19% |
| 0.3-1 km | 319 | 1.57% |
| 1-2 km | 27 | 0.00% |
| 2-5 km | 0 | - |
| >5 km | 22 | 0.00% |
| <0.2 s | 1037 | 1.74% |
| 0.2-0.5 s | 2345 | 0.94% |
| 0.5-1 s | 464 | 0.43% |
| 1-2 s | 290 | 0.69% |
| 2-5 s | 75 | 5.33% |
| no predecessor (first / after gap) | 127 | 1.57% |

Senders with >= 1 B alarm: 12 of 92; with >= 3: 7; their share of all B alarms 88%; kinds among the k>=3 senders: {'no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs)': 7}.

| rank | location | messages | alarms B | alarms A | v max | implied speed max | jump max (m) | kind | top checks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Mobile/Cologne | 393 | 13 | 308 | 13.4 | 14.4 | 43 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | heading_rate:24,pos_heading:23,field_ranges:14 |
| 2 | Mobile/Cologne | 130 | 12 | 113 | 13.3 | 14.3 | 16 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:17,heading_rate:16,field_ranges:12 |
| 3 | Mobile/Dusseldorf | 72 | 4 | 66 | 8.7 | 9.0 | 16 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:13,heading_rate:11 |
| 4 | Mobile/Highway | 28 | 4 | 27 | 15.7 | 15.5 | 7 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:11,accel_consistency:6 |
| 5 | Mobile/Aachen | 12 | 4 | 11 | 6.5 | 5.7 | 6 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:7,heading_rate:7,field_ranges:4 |
| 6 | Mobile/Highway | 5 | 4 | 5 | 31.7 | 0.0 | 0 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:4,kf_nis:4 |
| 7 | Mobile/Highway | 6 | 3 | 4 | 16.0 | 16.2 | 27 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | overlap:3,track_birth:1 |
| 8 | Mobile/Highway | 30 | 2 | 30 | 32.0 | 34.9 | 121 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:3 |
| 9 | Mobile/Highway | 53 | 1 | 53 | 43.1 | 63.7 | 32 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | implied_speed:10,beacon_rate:2,kf_nis:2 |
| 10 | Mobile/Aachen | 96 | 1 | 88 | 12.9 | 13.8 | 35 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:2 |
| 11 | Mobile/Highway | 43 | 1 | 43 | 34.8 | 40.4 | 17 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:1,kf_nis:1 |
| 12 | Mobile/Highway | 23 | 1 | 18 | 17.7 | 17.2 | 76 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_speed:1 |

## Stationary: 43087 genuine messages, 303 senders, 228 recordings, 3.82 receiver-hours (validation: 33845 msgs, 284 senders)

| configuration | FA per message [95% CI by recordings] | alarms / receiver-hour | alarm events / hour | senders k=3 | senders k val (k) |
|---|---|---|---|---|---|
| A_physics | 95.12% [92.16%, 96.77%] | 10740 | 96 | 87.1% (264/303) | n/a |
| physics | 0.97% [0.61%, 1.51%] | 110 | 30 | 13.2% (40/303) | 1.0% (k=22) |
| L1 | 0.49% [0.22%, 0.82%] | 56 | 15 | 5.3% (16/303) | 0.7% (k=25) |
| L2 | 0.78% [0.57%, 1.13%] | 88 | 32 | 13.5% (41/303) | 1.0% (k=14) |
| L3 | 1.11% [0.48%, 1.93%] | 125 | 36 | 9.2% (28/303) | 1.3% (k=15) |
| fresh | 1.16% [0.74%, 1.48%] | 131 | 27 | 12.9% (39/303) | 2.3% (k=22) |
| physics+fresh | 2.12% [1.59%, 2.72%] | 240 | 52 | 23.4% (71/303) | 1.3% (k=38) |
| range | 0.49% [0.23%, 0.76%] | 56 | 8 | 5.3% (16/303) | 0.7% (k=25) |
| range_loc | 0.48% [0.29%, 0.70%] | 54 | 18 | 5.0% (15/303) | 0.3% (k=25) |
| physics+range | 0.83% [0.54%, 1.31%] | 93 | 31 | 12.2% (37/303) | 0.3% (k=22) |
| rx | 0.49% [0.23%, 0.76%] | 56 | 8 | 5.3% (16/303) | 0.7% (k=25) |
| physics+rx | 0.83% [0.54%, 1.31%] | 93 | 31 | 12.2% (37/303) | 0.3% (k=22) |

Appearance (data-driven 1% of evaluable first messages): evaluable genuine first messages in this set 262, alarms 0 (per evaluable first message 0.00%, per message 0.000%); physical 300 m design value alarms 40.08% of them.
Range with receiver position: messages 43087; pooled FA among them 0.49%; per-location FA 0.48%.
Row kinds: {'scored': 0.936454150903985, 'unscored_first_or_gap': 0.012672035648803584, 'exact_repeat': 0.05087381344721146}; FA of B physics on scored rows 0.86%.

Per check FA, A (frozen VeReMi) vs B (V2AIX validation):

| check | A | B |
|---|---|---|
| beacon_rate | 92.00% | 0.79% |
| field_ranges | 65.96% | 1.17% |
| pos_speed | 1.26% | 1.05% |
| pos_heading | 0.00% | 0.60% |
| speed_change | 0.21% | 0.96% |
| implied_speed | 76.07% | 1.03% |
| heading_rate | 0.17% | 0.55% |
| accel_consistency | 0.58% | 0.95% |
| overlap | 0.05% | 0.08% |
| kf_nis | 4.69% | 1.01% |
| kf_cusum_hi | 43.59% | 1.62% |
| track_birth | 0.13% | 0.13% |

| location | messages | recordings | hours | FA B physics | alarms/h B | FA A physics | FA range pooled | FA range per-location |
|---|---|---|---|---|---|---|---|---|
| Stationary/A44-Jackerath | 33100 | 60 | 1.75 | 0.66% | 125 | 99.92% | 0.64% | 0.37% |
| Stationary/Aachen-Heinrichsallee | 396 | 30 | 0.09 | 0.00% | 0 | 73.48% | 0.00% | 0.25% |
| Stationary/Aachen-Monheimsallee | 622 | 16 | 0.08 | 0.00% | 0 | 91.80% | 0.00% | 0.96% |
| Stationary/Aachen-Ponttor | 4463 | 61 | 0.89 | 2.42% | 122 | 77.46% | 0.00% | 0.74% |
| Stationary/Aachen-Theaterstrasse | 4506 | 61 | 1.00 | 2.02% | 91 | 79.69% | 0.00% | 0.98% |

B physics false alarms by distance to the receiver / by gap since the sender's previous CAM:

| bin | messages | FA |
|---|---|---|
| <100 m | 9891 | 1.53% |
| 100-300 m | 5082 | 1.34% |
| 0.3-1 km | 11143 | 0.88% |
| 1-2 km | 4399 | 0.95% |
| 2-5 km | 12491 | 0.47% |
| >5 km | 81 | 0.00% |
| <0.2 s | 15990 | 1.34% |
| 0.2-0.5 s | 19450 | 0.46% |
| 0.5-1 s | 4148 | 0.87% |
| 1-2 s | 2383 | 0.34% |
| 2-5 s | 570 | 1.93% |
| no predecessor (first / after gap) | 546 | 10.99% |

Senders with >= 1 B alarm: 74 of 303; with >= 3: 40; their share of all B alarms 89%; kinds among the k>=3 senders: {'no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs)': 34, 'parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill': 6}.

| rank | location | messages | alarms B | alarms A | v max | implied speed max | jump max (m) | kind | top checks |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Stationary/A44-Jackerath | 695 | 79 | 695 | 48.9 | 64.3 | 124 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_cusum_hi:217,beacon_rate:71,implied_speed:58 |
| 2 | Stationary/Aachen-Ponttor | 141 | 42 | 139 | 10.6 | 60.1 | 21 | parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill | kf_cusum_hi:36,kf_nis:9,pos_speed:6 |
| 3 | Stationary/A44-Jackerath | 745 | 26 | 745 | 43.6 | 64.0 | 131 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_cusum_hi:171,kf_nis:56,implied_speed:42 |
| 4 | Stationary/A44-Jackerath | 427 | 18 | 427 | 32.6 | 36.7 | 91 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | beacon_rate:18,kf_nis:4,speed_change:1 |
| 5 | Stationary/Aachen-Ponttor | 72 | 13 | 47 | 18.4 | 18.9 | 15 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:25,accel_consistency:8,beacon_rate:2 |
| 6 | Stationary/Aachen-Ponttor | 73 | 12 | 51 | 18.2 | 22.6 | 12 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:19,accel_consistency:11 |
| 7 | Stationary/Aachen-Theaterstrasse | 72 | 12 | 68 | 8.9 | 25.4 | 12 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | heading_rate:10,field_ranges:8,pos_heading:7 |
| 8 | Stationary/A44-Jackerath | 875 | 11 | 875 | 44.6 | 63.7 | 103 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | speed_change:21,accel_consistency:19,pos_speed:3 |
| 9 | Stationary/Aachen-Ponttor | 120 | 8 | 119 | 9.4 | 62.1 | 9 | parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill | overlap:4,kf_nis:3,pos_speed:2 |
| 10 | Stationary/Aachen-Theaterstrasse | 127 | 8 | 120 | 12.1 | 35.2 | 21 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | pos_heading:10,heading_rate:9,pos_speed:2 |
| 11 | Stationary/A44-Jackerath | 941 | 8 | 941 | 50.7 | 93.6 | 177 | no kinematic anomaly found (alarm from noise statistics, sparse or irregular CAMs) | kf_cusum_hi:263,beacon_rate:95,implied_speed:53 |
| 12 | Stationary/Aachen-Theaterstrasse | 40 | 8 | 33 | 2.2 | 58.4 | 8 | parked / queuing sender (median speed < 1 m/s): heading and speed noise at standstill | pos_speed:13,kf_cusum_hi:10,kf_nis:5 |

## Speeds above 70 m/s (all splits, left in the data)

| env | split | location | speed (m/s) | prev / next speed | pos sigma | L1 field_ranges (B) | physics A | physics B | checks alarming (B) |
|---|---|---|---|---|---|---|---|---|---|
| Stationary | train | Stationary/Aachen-Ponttor | 163.82 | 0.02 / 108.46000000000001 | 2.5 | True | True | True | field_ranges,pos_speed,speed_change,implied_speed,accel_consistency,kf_nis |
| Stationary | train | Stationary/Aachen-Ponttor | 108.46 | 163.82 / 108.46000000000001 | 3.3 | True | True | True | field_ranges,speed_change,implied_speed,accel_consistency,kf_nis |
| Stationary | train | Stationary/Aachen-Ponttor | 108.46 | 108.46000000000001 / 8.17 | 4.2 | True | True | True | field_ranges,pos_speed,pos_heading,accel_consistency,kf_nis,kf_cusum_hi |