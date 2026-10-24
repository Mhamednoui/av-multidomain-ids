# WP3 S4 tables (final.json). nmin = 8, primary threshold = lodo; budget 1 % of clean validation scans

## Mode lodo (PRIMARY): clean test FA 1.6 %, scoring 2 ms/scan

Per-drive FA (%): 0001 0.0, 0005 0.0, 0028 1.9, 0039 2.8, 0052 0.0, 0079 1.0, 0095 1.9

Single-stat FA (%): dens_hi 1.1, dens_lo 2.0, int_hi 0.0, int_lo 0.8, cnt_dens_hi 3.5, cnt_dens_lo 2.4, cnt_int_hi 2.0, cnt_int_lo 0.0

### Scan-level detection (%)

| attack | n | union | dens_hi | dens_lo | int_hi | int_lo | cnt_dens_hi | cnt_dens_lo | cnt_int_hi | cnt_int_lo |
|---|---|---|---|---|---|---|---|---|---|---|
| ph_replace_near | 510 | 1.0 | 1.0 | 2.0 | 0.0 | 0.8 | 3.3 | 2.4 | 2.5 | 0.0 |
| ph_replace_far | 510 | 1.2 | 1.0 | 2.4 | 0.0 | 0.8 | 3.5 | 1.8 | 2.4 | 0.0 |
| ph_budget_near | 510 | 1.2 | 1.0 | 2.5 | 0.0 | 0.8 | 3.3 | 2.0 | 2.4 | 0.0 |
| ph_budget_far | 510 | 1.2 | 1.0 | 2.4 | 0.0 | 0.8 | 3.5 | 2.0 | 2.4 | 0.0 |
| PointDrop | 510 | 1.2 | 1.0 | 1.8 | 0.0 | 0.8 | 2.0 | 2.5 | 1.8 | 0.0 |
| IntensitySpoof | 510 | 56.5 | 1.0 | 2.4 | 6.7 | 0.4 | 3.5 | 2.0 | 71.4 | 0.0 |
| cmp_boxcloud | 510 | 3.9 | 6.5 | 2.4 | 0.0 | 0.6 | 2.7 | 2.7 | 2.4 | 0.0 |
| cmp_mradd_near | 510 | 29.2 | 29.2 | 2.4 | 0.0 | 0.8 | 4.3 | 2.5 | 2.4 | 0.0 |
| cmp_mradd_far | 510 | 4.3 | 4.1 | 2.4 | 0.0 | 0.8 | 3.5 | 2.0 | 2.4 | 0.0 |

### Tile level (phantom tiles = tiles with >= 50 % injected returns)

| attack | scans | with phantom tile | phantom tiles | tile detection % | scans with caught phantom tile % |
|---|---|---|---|---|---|
| ph_replace_near | 510 | 483 | 18027 | 0.0 | 0.0 |
| ph_replace_far | 510 | 442 | 2443 | 0.0 | 0.0 |
| ph_budget_near | 510 | 469 | 2922 | 0.0 | 0.0 |
| ph_budget_far | 510 | 438 | 1759 | 0.0 | 0.0 |
| cmp_boxcloud | 510 | 493 | 7086 | 0.1 | 1.4 |
| cmp_mradd_near | 510 | 477 | 18537 | 0.5 | 8.4 |
| cmp_mradd_far | 510 | 433 | 2245 | 0.0 | 0.2 |

### Persistent episodes (30 scans, rolling log-odds W=10, stat threshold 3.348); false-episode rate on 48 clean test windows: 16.7 %

| kind | episodes | detected in 3 s | median delay of alarmed (s) | single-scan alarm % |
|---|---|---|---|---|
| ep_budget_far | 21 | 5 | 0.31 | 2.7 |
| ep_budget_near | 21 | 2 | 1.39 | 1.4 |
| ep_replace_far | 21 | 2 | 1.08 | 0.5 |
| ep_replace_near | 21 | 0 | - | 0.5 |

## Mode val_only: clean test FA 20.4 %, scoring 2 ms/scan

Per-drive FA (%): 0001 25.0, 0005 13.6, 0028 1.9, 0039 14.7, 0052 5.1, 0079 22.0, 0095 64.2

Single-stat FA (%): dens_hi 2.3, dens_lo 1.3, int_hi 0.2, int_lo 0.7, cnt_dens_hi 24.9, cnt_dens_lo 0.8, cnt_int_hi 1.3, cnt_int_lo 0.0

### Scan-level detection (%)

| attack | n | union | dens_hi | dens_lo | int_hi | int_lo | cnt_dens_hi | cnt_dens_lo | cnt_int_hi | cnt_int_lo |
|---|---|---|---|---|---|---|---|---|---|---|
| ph_replace_near | 510 | 19.0 | 2.2 | 1.2 | 0.2 | 0.8 | 24.3 | 0.6 | 1.6 | 0.0 |
| ph_replace_far | 510 | 20.2 | 2.4 | 1.6 | 0.2 | 0.8 | 24.3 | 0.8 | 1.4 | 0.0 |
| ph_budget_near | 510 | 19.8 | 2.2 | 1.6 | 0.2 | 0.8 | 24.5 | 0.8 | 1.4 | 0.0 |
| ph_budget_far | 510 | 20.4 | 2.4 | 1.6 | 0.2 | 0.8 | 24.3 | 0.8 | 1.4 | 0.0 |
| PointDrop | 510 | 16.7 | 2.2 | 1.0 | 0.2 | 0.8 | 21.2 | 0.2 | 1.4 | 0.0 |
| IntensitySpoof | 510 | 68.0 | 2.4 | 1.6 | 7.1 | 0.4 | 24.5 | 0.8 | 64.1 | 0.0 |
| cmp_boxcloud | 510 | 22.7 | 7.8 | 1.6 | 0.2 | 0.6 | 25.7 | 1.0 | 1.4 | 0.0 |
| cmp_mradd_near | 510 | 43.9 | 30.8 | 1.6 | 0.2 | 0.8 | 29.0 | 1.0 | 1.4 | 0.0 |
| cmp_mradd_far | 510 | 22.5 | 5.7 | 1.6 | 0.2 | 0.8 | 24.9 | 0.8 | 1.6 | 0.0 |

### Tile level (phantom tiles = tiles with >= 50 % injected returns)

| attack | scans | with phantom tile | phantom tiles | tile detection % | scans with caught phantom tile % |
|---|---|---|---|---|---|
| ph_replace_near | 510 | 483 | 18027 | 0.0 | 0.0 |
| ph_replace_far | 510 | 442 | 2443 | 0.0 | 0.0 |
| ph_budget_near | 510 | 469 | 2922 | 0.0 | 0.0 |
| ph_budget_far | 510 | 438 | 1759 | 0.0 | 0.0 |
| cmp_boxcloud | 510 | 493 | 7086 | 0.1 | 1.4 |
| cmp_mradd_near | 510 | 477 | 18537 | 0.5 | 8.4 |
| cmp_mradd_far | 510 | 433 | 2245 | 0.0 | 0.2 |

### Persistent episodes (30 scans, rolling log-odds W=10, stat threshold 2.727); false-episode rate on 48 clean test windows: 56.2 %

| kind | episodes | detected in 3 s | median delay of alarmed (s) | single-scan alarm % |
|---|---|---|---|---|
| ep_budget_far | 21 | 16 | 0.41 | 32.1 |
| ep_budget_near | 21 | 13 | 0.10 | 24.9 |
| ep_replace_far | 21 | 14 | 0.93 | 20.5 |
| ep_replace_near | 21 | 13 | 0.21 | 20.6 |

## Harness ablation harness_L1_L2a (val-only L2a model; test FA and detection in %)

Budget 1.0% false alarms on validation normal data. Domain: harness_L1_L2a.

| configuration | AUC | detection | false alarms | det IntensitySpoof | det PointDrop | det cmp_boxcloud | det cmp_mradd_far | det cmp_mradd_near | det ph_budget_far | det ph_budget_near | det ph_replace_far | det ph_replace_near | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.594 | 35.4% | 21.33% | 66.5% | 17.6% | 34.1% | 71.8% | 43.7% | 21.8% | 20.8% | 22.5% | 20.0% | 0.0 |
| only_L1 | 0.558 | 10.0% | 1.63% | 1.4% | 1.4% | 16.1% | 62.5% | 1.4% | 1.8% | 1.4% | 3.1% | 1.4% | 0.0 |
| only_L2a | 0.552 | 28.1% | 20.35% | 68.0% | 16.7% | 22.7% | 22.5% | 43.9% | 20.4% | 19.8% | 20.2% | 19.0% | 0.0 |

## Harness ablation harness_L1_dens_int (val-only L2a model; test FA and detection in %)

Budget 1.0% false alarms on validation normal data. Domain: harness_L1_dens_int.

| configuration | AUC | detection | false alarms | det IntensitySpoof | det PointDrop | det cmp_boxcloud | det cmp_mradd_far | det cmp_mradd_near | det ph_budget_far | det ph_budget_near | det ph_replace_far | det ph_replace_near | median delay (s) |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.595 | 22.7% | 11.29% | 51.2% | 8.8% | 23.7% | 54.5% | 19.8% | 11.6% | 11.2% | 12.7% | 10.6% | 0.0 |
| only_L1 | 0.558 | 10.0% | 1.63% | 1.4% | 1.4% | 16.1% | 62.5% | 1.4% | 1.8% | 1.4% | 3.1% | 1.4% | 0.0 |
| only_L2a_dens | 0.515 | 22.4% | 20.03% | 19.8% | 16.3% | 22.4% | 22.2% | 43.5% | 20.0% | 19.4% | 19.8% | 18.6% | 0.0 |
| only_L2a_int | 0.548 | 7.9% | 1.04% | 62.0% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 1.2% | 0.0 |
| all_but_L1 | 0.555 | 28.5% | 20.35% | 71.6% | 16.7% | 22.0% | 22.4% | 43.7% | 20.6% | 20.0% | 20.4% | 19.2% | 0.0 |
| all_but_L2a_dens | 0.598 | 17.8% | 2.61% | 62.5% | 2.5% | 16.9% | 63.1% | 2.5% | 2.9% | 2.5% | 4.1% | 2.5% | 0.0 |
| all_but_L2a_int | 0.560 | 30.2% | 21.14% | 21.0% | 17.3% | 34.1% | 71.8% | 43.5% | 21.4% | 20.4% | 22.4% | 19.6% | 0.0 |
