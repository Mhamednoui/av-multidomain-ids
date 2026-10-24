# S5 tables (final.json), variant (margin, gap, strict) = [0, 1, 0]

Clean test FA 1.63 % (pooled train+val FA 0.96 %). Per test drive: 0011 0.0, 0027 4.8, 0035 0.0
Nested LODO FA (threshold from the other 15 drives, held-out drive): 0002 0.0, 0013 13.2, 0015 0.0, 0017 0.0, 0019 0.2, 0020 0.0, 0029 1.2, 0046 0.0, 0048 0.0, 0060 0.0, 0070 2.4, 0106 0.0, 0113 0.0, 0011 0.0, 0027 100.0, 0035 0.0

## Scan-level detection (%) at the 1 % LODO operating point

| attack | n | union | tot | maxf | cnt | maxn |
|---|---|---|---|---|---|---|
| ph_replace_near | 185 | 11.4 | 8.1 | 1.6 | 5.9 | 13.0 |
| ph_replace_far | 185 | 2.2 | 3.8 | 0.0 | 5.9 | 0.0 |
| ph_budget_near | 185 | 2.2 | 4.3 | 0.0 | 5.9 | 3.2 |
| ph_budget_far | 185 | 1.6 | 4.3 | 0.0 | 5.9 | 0.0 |
| PointDrop | 185 | 0.0 | 0.5 | 0.0 | 0.5 | 0.0 |
| IntensitySpoof | 185 | 2.2 | 3.8 | 0.0 | 5.4 | 0.0 |
| cmp_boxcloud | 185 | 14.1 | 4.9 | 4.9 | 5.9 | 13.0 |
| cmp_mradd_near | 185 | 78.9 | 21.1 | 65.4 | 6.5 | 77.8 |
| cmp_mradd_far | 185 | 34.6 | 6.5 | 23.2 | 5.9 | 31.4 |
| fl_replace_near | 185 | 1.6 | 3.8 | 0.0 | 4.3 | 0.0 |
| fl_replace_far | 185 | 1.6 | 3.2 | 0.0 | 5.4 | 0.0 |
| fl_budget_near | 185 | 2.2 | 3.8 | 0.0 | 5.4 | 0.0 |
| fl_budget_far | 185 | 1.6 | 3.2 | 0.0 | 5.4 | 0.0 |

## Tile level (phantom tiles = >= 50 % injected returns; threshold = clean-scan 99th percentile of the max tile fraction 2.10)

| attack | phantom tiles | scans with a phantom tile | tile detection % | scans with a caught phantom tile % |
|---|---|---|---|---|
| ph_replace_near | 7774 | 184/185 | 0.04 | 1.6 |
| ph_replace_far | 1131 | 159/185 | 0.00 | 0.0 |
| ph_budget_near | 1187 | 181/185 | 0.00 | 0.0 |
| ph_budget_far | 773 | 161/185 | 0.00 | 0.0 |
| PointDrop | 0 | 0/185 | - | 0.0 |
| IntensitySpoof | 0 | 0/185 | - | 0.0 |
| cmp_boxcloud | 2835 | 179/185 | 0.39 | 4.9 |
| cmp_mradd_near | 6392 | 183/185 | 22.40 | 65.4 |
| cmp_mradd_far | 937 | 167/185 | 13.02 | 23.2 |
| fl_replace_near | 9844 | 182/185 | 0.00 | 0.0 |
| fl_replace_far | 1196 | 176/185 | 0.00 | 0.0 |
| fl_budget_near | 1133 | 180/185 | 0.00 | 0.0 |
| fl_budget_far | 789 | 175/185 | 0.00 | 0.0 |

## Persistent episodes (30 scans, alarm within 3 s; stat threshold 4.071; false-episode rate on clean test windows 11.8 % of 17)

| kind | episodes | detected in 3 s | median delay s | single-scan alarm rate % |
|---|---|---|---|---|

## Harness harness_L1_L2a_L2b (detection % by attack at the system 1 % budget)

| layers | FA % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.18 | 43.8 | 0.5 | 16.2 | 63.2 | 77.3 | 1.1 | 1.6 | 3.2 | 7.0 |
| only_L1 | 0.91 | 1.1 | 0.5 | 17.8 | 60.0 | 1.1 | 2.2 | 1.1 | 3.8 | 1.1 |
| only_L2a_int | 0.00 | 42.2 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| only_L2b | 0.91 | 0.5 | 0.0 | 10.8 | 32.4 | 78.4 | 1.1 | 1.6 | 1.6 | 7.0 |
| all_but_L1 | 0.00 | 44.9 | 0.0 | 5.9 | 28.6 | 77.3 | 0.0 | 0.5 | 0.0 | 3.8 |
| all_but_L2a_int | 0.91 | 0.5 | 0.5 | 32.4 | 78.4 | 78.4 | 1.6 | 3.8 | 3.8 | 11.4 |
| all_but_L2b | 0.18 | 45.4 | 0.0 | 15.1 | 60.0 | 0.0 | 0.5 | 0.0 | 2.7 | 0.0 |

## Harness harness_L1_L2b (detection % by attack at the system 1 % budget)

| layers | FA % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.91 | 0.5 | 0.5 | 32.4 | 78.4 | 78.4 | 1.6 | 3.8 | 3.8 | 11.4 |
| only_L1 | 0.91 | 1.1 | 0.5 | 17.8 | 60.0 | 1.1 | 2.2 | 1.1 | 3.8 | 1.1 |
| only_L2b | 0.91 | 0.5 | 0.0 | 10.8 | 32.4 | 78.4 | 1.1 | 1.6 | 1.6 | 7.0 |
