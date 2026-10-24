# S3b: genuine TEST senders with the most alarms (variant B), what is unusual about them

## Mobile

| rank | location | alarms | messages | duration s | dt median / p95 s | share dt > 1 s | distance to rx m | speed median / max | implied speed max | speed-position mismatch > 10 m/s | GNSS jumps | pos sigma | checks alarming |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Mobile/Cologne | 13 | 393 | 234 | 0.40 / 1.00 | 16% | 5-411 | 4.4 / 13.4 | 14.4 | 0% | 0 | 2.8 | heading_rate:24,pos_heading:23,field_ranges:14,speed_change:12 |
| 2 | Mobile/Cologne | 12 | 130 | 72 | 0.40 / 1.21 | 12% | 126-354 | 6.7 / 13.3 | 14.3 | 0% | 0 | 2.9 | pos_heading:17,heading_rate:16,field_ranges:12,speed_change:1 |
| 3 | Mobile/Dusseldorf | 4 | 72 | 42 | 0.52 / 1.00 | 3% | 9-154 | 4.7 / 8.7 | 9.0 | 0% | 0 | 3.7 | pos_heading:13,heading_rate:11 |
| 4 | Mobile/Highway | 4 | 28 | 6 | 0.20 / 0.47 | 0% | - | 8.0 / 15.7 | 15.5 | 0% | 0 | 2.8 | speed_change:11,accel_consistency:6 |
| 5 | Mobile/Aachen | 4 | 12 | 5 | 0.20 / 1.05 | 9% | 229-237 | 3.9 / 6.5 | 5.7 | 0% | 0 | 16.7 | pos_heading:7,heading_rate:7,field_ranges:4 |
| 6 | Mobile/Highway | 4 | 5 | 4 | 1.00 / 1.00 | 25% | - | 31.2 / 31.7 | 0.0 | 100% | 0 | 27.8 | pos_speed:4,kf_nis:4 |

## Stationary

| rank | location | alarms | messages | duration s | dt median / p95 s | share dt > 1 s | distance to rx m | speed median / max | implied speed max | speed-position mismatch > 10 m/s | GNSS jumps | pos sigma | checks alarming |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Stationary/A44-Jackerath | 79 | 695 | 141 | 0.13 / 0.48 | 2% | 33-4094 | 41.7 / 48.9 | 64.3 | 18% | 0 | 2.8 | kf_cusum_hi:217,beacon_rate:71,implied_speed:58,kf_nis:42 |
| 2 | Stationary/Aachen-Ponttor | 42 | 141 | 90 | 0.52 / 1.04 | 22% | 1-113 | 0.6 / 10.6 | 60.1 | 4% | 0 | 2.8 | kf_cusum_hi:36,kf_nis:9,pos_speed:6,speed_change:4 |
| 3 | Stationary/A44-Jackerath | 26 | 745 | 156 | 0.10 / 0.40 | 2% | 16-4235 | 41.7 / 43.6 | 64.0 | 13% | 0 | 2.8 | kf_cusum_hi:171,kf_nis:56,implied_speed:42,pos_speed:37 |
| 4 | Stationary/A44-Jackerath | 18 | 427 | 113 | 0.20 / 0.68 | 3% | 1818-4248 | 27.9 / 32.6 | 36.7 | 5% | 0 | 2.8 | beacon_rate:18,kf_nis:4,speed_change:1 |
| 5 | Stationary/Aachen-Ponttor | 13 | 72 | 53 | 0.88 / 1.99 | 25% | 44-81 | 2.2 / 18.4 | 18.9 | 0% | 0 | 3.0 | speed_change:25,accel_consistency:8,beacon_rate:2,pos_speed:1 |
| 6 | Stationary/Aachen-Ponttor | 12 | 73 | 58 | 0.75 / 2.00 | 29% | 40-89 | 1.8 / 18.2 | 22.6 | 0% | 0 | 3.0 | speed_change:19,accel_consistency:11 |
