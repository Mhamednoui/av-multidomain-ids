# WP4 S7 tables, D23 (generated from results/WP4/s7_d23.json)

Sample rows: {'train': 400000, 'val': 429462, 'test': 651434}. D10 combiner methods: H max, O noisy_or.

## 1. Zero-shot net.tcp_flags (D10 fit and threshold) on every D23 day (flow level; the only headline layer whose inputs exist on every day)

FA 30.4 [25.2, 38.2] % overall; by day: 02-14 10.4, 02-15 15.5, 02-16 0.0, 02-20 31.6, 02-21 99.5, 02-22 19.9, 02-23 18.6, 02-28 39.3, 03-01 33.7, 03-02 25.3

| stack | FA % | macro % | Bot | HOIC | LOIC-HTTP | LOIC-UDP | GoldenEye | Slowloris | Infiltr. | SSH | Web-BF |
|---|---|---|---|---|---|---|---|---|---|---|---|
| tcp_flags zero-shot | 30.43 [25.21, 38.20] | 31.3 [26.5, 39.9] | 99 [96, 100] | 20 [0, 52] | 50 [0, 50] | 0 [0, 0] | 0 [0, 0] | 21 [19, 21] | 41 [39, 42] | 0 [0, 0] | 51 [38, 74] |


## 2. Zero-shot on Tue-20-02 (L2a layers need addresses; D10 thresholds, D10 combiner; only DDoS-LOIC-HTTP exists that day)

| rows | stack | FA % [CI] | LOIC-HTTP detection % [CI] | AUC |
|---|---|---|---|---|
| sample_rows | H | 34.69 [32.81, 36.48] | 99.4 [0.0, 100.0] | 0.734 |
| sample_rows | H without tcp_flags | 6.13 [5.19, 7.03] | 98.9 [0.0, 100.0] | 0.947 |
| sample_rows | alone scan | 3.85 | 0.0 |  |
| sample_rows | alone trw | 3.40 | 0.0 |  |
| sample_rows | alone bruteforce | 3.00 | 99.2 |  |
| sample_rows | alone tcp_flags | 31.57 | 49.8 |  |
| stage_stream | H | 23.48 [22.25, 24.70] | 99.4 [0.0, 100.0] | 0.820 |
| stage_stream | H without tcp_flags | 4.54 [3.83, 5.23] | 99.0 [0.0, 100.0] | 0.961 |
| stage_stream | alone scan | 2.54 | 0.0 |  |
| stage_stream | alone trw | 3.13 | 0.0 |  |
| stage_stream | alone bruteforce | 2.23 | 99.3 |  |
| stage_stream | alone tcp_flags | 22.63 | 50.0 |  |


## 3. On-network regime (refit on the D23 warm-up; thresholds from the D23 benign validation; combiner = noisy_or, no attack label)

Warm-up: {'tue_train_benign_flows': 4335440, 'tue_val_benign_flows': 1434152, 'sample_train_benign': 400000, 'sample_val_benign': 300000, 'tue_warmup_hours': 7.7941666666666665}

### Tue-20-02, O = tcp_flags + scan + trw + bruteforce + dos_rate + service + AE (sample rows)

| stack | FA % [CI] | LOIC-HTTP detection % [CI] | AUC |
|---|---|---|---|
| O | 1.67 [1.27, 2.13] | 100.0 [99.4, 100.0] | 1.000 |
| H layers only | 1.47 [1.11, 1.79] | 98.5 [0.0, 100.0] | nan |
| alone tcp_flags | 0.93 [0.87, 1.00] | 0.0 [0.0, 0.0] | nan |
| alone scan | 1.45 [1.01, 1.92] | 0.0 [0.0, 0.0] | nan |
| alone trw | 1.54 [1.03, 2.01] | 0.0 [0.0, 0.0] | nan |
| alone bruteforce | 1.40 [1.04, 1.77] | 99.8 [0.0, 100.0] | nan |
| alone dos_rate | 1.66 [1.24, 2.10] | 100.0 [97.5, 100.0] | nan |
| alone l3_service | 0.95 [0.84, 1.12] | 3.2 [0.6, 100.0] | nan |
| alone l3_ae | 1.05 [0.88, 1.39] | 42.1 [39.0, 100.0] | nan |


All-but-one (O, Tue): tcp_flags: FA 1.82 / LOIC 100.0; scan: FA 1.54 / LOIC 100.0; trw: FA 1.44 / LOIC 100.0; bruteforce: FA 1.68 / LOIC 100.0; dos_rate: FA 1.40 / LOIC 98.5; l3_service: FA 1.58 / LOIC 99.9; l3_ae: FA 1.52 / LOIC 100.0

### All days, O-flow = tcp_flags + service + AE (flow level, sample rows), detection %, CI in brackets

| stack | FA % | macro % | Bot | HOIC | LOIC-HTTP | LOIC-UDP | GoldenEye | Slowloris | Infiltr. | SSH | Web-BF |
|---|---|---|---|---|---|---|---|---|---|---|---|
| O-flow | 1.08 [0.92, 1.28] | 25.7 [15.9, 36.7] | 1 [0, 1] | 0 [0, 0] | 0 [0, 99] | 100 [100, 100] | 2 [0, 2] | 100 [99, 100] | 4 [3, 6] | 0 [0, 0] | 25 [17, 34] |
| alone tcp_flags | 0.96 [0.83, 1.09] | 0.5 [0.4, 0.7] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 0 [0, 0] | 4 [3, 6] | 0 [0, 0] | 0 [0, 0] |
| alone l3_service | 0.96 [0.83, 1.09] | 24.0 [14.9, 34.7] | 1 [0, 1] | 0 [0, 0] | 3 [1, 100] | 100 [100, 100] | 5 [0, 5] | 79 [79, 81] | 3 [2, 4] | 0 [0, 0] | 25 [17, 34] |
| alone l3_ae | 1.03 [0.87, 1.22] | 27.8 [18.7, 35.0] | 1 [0, 1] | 0 [0, 0] | 42 [39, 100] | 100 [100, 100] | 3 [0, 3] | 77 [70, 79] | 3 [2, 3] | 0 [0, 0] | 25 [17, 34] |
| n flows |  |  | 35623 | 1444 | 60000 | 351 | 11570 | 2326 | 18880 | 20174 | 110 |
| 10-min blocks holding the family (CI unit) |  |  | 9 | 2 | 5 | 3 | 2 | 2 | 14 | 4 | 8 |


FA by day (O-flow): 02-14 1.1, 02-15 1.0, 02-16 1.4, 02-20 1.1, 02-21 0.0, 02-22 0.7, 02-23 0.8, 02-28 3.2, 03-01 1.2, 03-02 1.3

Detection by day | family (O-flow): 2018-02-14|SSH-Patator 0; 2018-02-15|DoS-GoldenEye 2; 2018-02-15|DoS-Slowloris 100; 2018-02-20|DDoS-LOIC-HTTP 0; 2018-02-21|DDoS-HOIC 0; 2018-02-21|DDoS-LOIC-UDP 100; 2018-02-22|Web-BruteForce 33; 2018-02-23|Web-BruteForce 19; 2018-02-28|Infiltration 3; 2018-03-01|Infiltration 6; 2018-03-02|Bot 1


## 4. dos_rate warm-up length on D23 Tue (information)

| fraction of warm-up | hours | flows | known destinations | FA % (test) | LOIC detection % | AUC |
|---|---|---|---|---|---|---|
| 0.1 | 0.5 | 90381 | 4 | 44.04 | 99.9 | 0.982 |
| 0.25 | 1.4 | 798332 | 1033 | 1.58 | 100.0 | 1.000 |
| 0.5 | 3.9 | 2011827 | 2162 | 1.60 | 100.0 | 1.000 |
| 1.0 | 7.8 | 4335440 | 3778 | 1.41 | 100.0 | 1.000 |


## 5. dos_rate warm-up length on D10 validation (information)

| fraction | minutes | flows | known destinations | FA % (val benign) | Hulk % | GoldenEye % | LOIC % | AUC |
|---|---|---|---|---|---|---|---|---|
| 0.1 | 126 | 162026 | 193 | 0.58 | 100.0 | 0.0 | 100.0 | 0.991 |
| 0.25 | 315 | 381626 | 498 | 0.94 | 100.0 | 0.0 | 100.0 | 0.991 |
| 0.5 | 630 | 663831 | 840 | 1.02 | 100.0 | 0.0 | 100.0 | 0.990 |
| 1.0 | 1260 | 1151157 | 1341 | 0.93 | 100.0 | 0.0 | 100.0 | 0.989 |
