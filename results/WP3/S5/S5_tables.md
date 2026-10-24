# S5 tables (final.json), variant (margin, gap, strict) = [0, 1, 0]

Clean test FA 0.46 % (pooled train+val FA 0.96 %). Per test drive: 0001 0.0, 0005 0.0, 0028 0.7, 0039 1.0, 0052 0.0, 0079 0.0, 0095 0.0
Nested LODO FA (threshold from the other 15 drives, held-out drive): 0002 0.0, 0013 13.2, 0015 0.0, 0017 0.0, 0019 0.2, 0020 0.0, 0029 1.2, 0046 0.0, 0048 0.0, 0060 0.0, 0070 2.4, 0106 0.0, 0113 0.0, 0011 0.0, 0027 100.0, 0035 0.0

## Scan-level detection (%) at the 1 % LODO operating point

| attack | n | union | tot | maxf | cnt | maxn |
|---|---|---|---|---|---|---|
| ph_replace_near | 510 | 6.3 | 3.3 | 1.2 | 0.6 | 15.5 |
| ph_replace_far | 510 | 0.8 | 0.2 | 0.8 | 0.2 | 1.6 |
| ph_budget_near | 510 | 1.0 | 0.0 | 0.8 | 0.2 | 1.8 |
| ph_budget_far | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 1.2 |
| PointDrop | 510 | 0.6 | 0.0 | 0.8 | 0.0 | 0.8 |
| IntensitySpoof | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 1.0 |
| cmp_boxcloud | 510 | 18.8 | 0.2 | 2.4 | 0.2 | 23.9 |
| cmp_mradd_near | 510 | 69.4 | 17.5 | 58.4 | 0.6 | 70.4 |
| cmp_mradd_far | 510 | 28.4 | 0.6 | 21.4 | 0.2 | 31.0 |
| fl_replace_near | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 0.8 |
| fl_replace_far | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 1.0 |
| fl_budget_near | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 1.0 |
| fl_budget_far | 510 | 0.6 | 0.0 | 0.8 | 0.2 | 1.0 |

## Tile level (phantom tiles = >= 50 % injected returns; threshold = clean-scan 99th percentile of the max tile fraction 2.10)

| attack | phantom tiles | scans with a phantom tile | tile detection % | scans with a caught phantom tile % |
|---|---|---|---|---|
| ph_replace_near | 18027 | 483/510 | 0.02 | 0.6 |
| ph_replace_far | 2443 | 442/510 | 0.00 | 0.0 |
| ph_budget_near | 2922 | 469/510 | 0.03 | 0.2 |
| ph_budget_far | 1759 | 438/510 | 0.00 | 0.0 |
| PointDrop | 0 | 0/510 | - | 0.0 |
| IntensitySpoof | 0 | 0/510 | - | 0.0 |
| cmp_boxcloud | 7086 | 493/510 | 0.13 | 1.6 |
| cmp_mradd_near | 18537 | 477/510 | 22.37 | 58.2 |
| cmp_mradd_far | 2245 | 433/510 | 12.78 | 20.8 |
| fl_replace_near | 23121 | 492/510 | 0.00 | 0.0 |
| fl_replace_far | 3293 | 472/510 | 0.00 | 0.0 |
| fl_budget_near | 2751 | 480/510 | 0.00 | 0.0 |
| fl_budget_far | 2101 | 470/510 | 0.00 | 0.0 |

## Persistent episodes (30 scans, alarm within 3 s; stat threshold 4.071; false-episode rate on clean test windows 0.0 % of 48)

| kind | episodes | detected in 3 s | median delay s | single-scan alarm rate % |
|---|---|---|---|---|
| ep_budget_far | 21 | 0 | - | 0.3 |
| ep_budget_near | 21 | 0 | - | 0.0 |
| ep_replace_far | 21 | 0 | - | 0.0 |
| ep_replace_near | 21 | 3 | 0.10 | 4.0 |
| epfl_replace_far | 21 | 0 | - | 0.2 |
| epfl_replace_near | 21 | 0 | - | 0.3 |

## Harness harness_L1_L2a_L2b (detection % by attack at the system 1 % budget)

| layers | FA % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 1.37 | 51.4 | 1.6 | 24.1 | 67.6 | 65.9 | 2.0 | 2.0 | 2.9 | 2.9 |
| only_L1 | 1.63 | 1.4 | 1.4 | 16.1 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |
| only_L2a_int | 0.20 | 51.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| only_L2b | 0.26 | 0.4 | 0.4 | 16.9 | 27.3 | 68.4 | 0.4 | 0.6 | 0.4 | 4.3 |
| all_but_L1 | 0.33 | 53.5 | 0.6 | 14.5 | 24.3 | 66.1 | 0.6 | 0.8 | 1.0 | 2.4 |
| all_but_L2a_int | 1.83 | 1.8 | 1.8 | 31.2 | 75.7 | 67.8 | 2.2 | 2.0 | 3.7 | 4.9 |
| all_but_L2b | 1.83 | 52.5 | 1.4 | 14.5 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |

## Harness harness_L1_L2b (detection % by attack at the system 1 % budget)

| layers | FA % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 1.83 | 1.8 | 1.8 | 31.2 | 75.7 | 67.8 | 2.2 | 2.0 | 3.7 | 4.9 |
| only_L1 | 1.63 | 1.4 | 1.4 | 16.1 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |
| only_L2b | 0.26 | 0.4 | 0.4 | 16.9 | 27.3 | 68.4 | 0.4 | 0.6 | 0.4 | 4.3 |
