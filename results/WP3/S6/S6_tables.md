## Scan level (onset: attacked scan vs clean previous scan), test, % of attacked scans

| layer | stats | FA test | worst drive FA | LODO FA mean / max (16 train+val) | ph_replace_near | ph_replace_far | ph_budget_near | ph_budget_far | PointDrop | IntensitySpoof | cmp_boxcloud | cmp_mradd_near | cmp_mradd_far |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| L2c | miss_w20 | 2.1 | 6.1 | 1.8 / 14.3 | 1.8 | 1.8 | 1.8 | 1.8 | 87.3 | 1.8 | 1.8 | 1.8 | 1.8 |
| L2d | app_cc, fix_tot | 0.2 | 0.7 | 2.4 / 28.7 | 32.5 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 2.5 | 34.5 | 0.2 |

Per-drive test FA L2c (%): 0001 0.0, 0005 0.0, 0028 0.2, 0039 6.1, 0052 0.0, 0079 0.0, 0095 2.6

LODO FA per train+val drive L2c (%): 0002 0.0, 0011 0.0, 0013 1.4, 0015 2.7, 0017 0.0, 0019 0.2, 0020 0.0, 0027 3.2, 0029 0.0, 0035 0.0, 0046 0.0, 0048 14.3, 0060 0.0, 0070 0.0, 0106 6.6, 0113 0.0

Single statistics L2c (test): FA / detection

| stat | FA | ph_replace_near | ph_replace_far | ph_budget_near | ph_budget_far | PointDrop | IntensitySpoof | cmp_boxcloud | cmp_mradd_near | cmp_mradd_far |
|---|---|---|---|---|---|---|---|---|---|---|
| miss_w20 | 2.1 | 1.8 | 1.8 | 1.8 | 1.8 | 87.3 | 1.8 | 1.8 | 1.8 | 1.8 |

Per-drive test FA L2d (%): 0001 0.0, 0005 0.0, 0028 0.7, 0039 0.0, 0052 0.0, 0079 0.0, 0095 0.0

LODO FA per train+val drive L2d (%): 0002 0.0, 0011 2.6, 0013 28.7, 0015 4.4, 0017 0.0, 0019 0.4, 0020 0.0, 0027 1.6, 0029 0.0, 0035 0.0, 0046 0.0, 0048 0.0, 0060 0.0, 0070 0.2, 0106 0.0, 0113 0.0

Single statistics L2d (test): FA / detection

| stat | FA | ph_replace_near | ph_replace_far | ph_budget_near | ph_budget_far | PointDrop | IntensitySpoof | cmp_boxcloud | cmp_mradd_near | cmp_mradd_far |
|---|---|---|---|---|---|---|---|---|---|---|
| app_cc | 0.5 | 45.5 | 0.4 | 0.6 | 0.4 | 0.4 | 0.4 | 6.1 | 47.1 | 0.4 |
| fix_tot | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## Persistent episodes (30 scans, 3 per drive and kind = 21), test


L2c: false-episode rate on 48 clean test windows 10.4 %

| group | kind | episodes | detected in 3 s | median delay (s) | onset scan alarm % | sustained scan alarm % |
|---|---|---|---|---|---|---|
| sensor_fixed | ep_budget_far | 21 | 0 | - | 0.0 | 0.2 |
| sensor_fixed | ep_budget_near | 21 | 2 | 2.63 | 0.0 | 1.0 |
| sensor_fixed | ep_replace_far | 21 | 2 | 0.93 | 0.0 | 2.0 |
| sensor_fixed | ep_replace_near | 21 | 4 | 0.10 | 4.8 | 2.0 |
| sensor_fixed_ego_moving | ep_budget_far | 13 | 0 | - | 0.0 | 0.3 |
| sensor_fixed_ego_moving | ep_budget_near | 13 | 2 | 2.63 | 0.0 | 1.6 |
| sensor_fixed_ego_moving | ep_replace_far | 11 | 0 | - | 0.0 | 0.3 |
| sensor_fixed_ego_moving | ep_replace_near | 14 | 4 | 0.10 | 7.1 | 3.0 |
| sensor_fixed_ego_slow | ep_budget_far | 8 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_slow | ep_budget_near | 8 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_slow | ep_replace_far | 10 | 2 | 0.93 | 0.0 | 3.8 |
| sensor_fixed_ego_slow | ep_replace_near | 7 | 0 | - | 0.0 | 0.0 |
| world_fixed | epW_budget_far | 21 | 1 | 0.10 | 0.0 | 0.5 |
| world_fixed | epW_budget_near | 21 | 1 | 0.10 | 4.8 | 0.3 |
| world_fixed | epW_replace_far | 21 | 1 | 1.65 | 0.0 | 0.3 |
| world_fixed | epW_replace_near | 21 | 1 | 1.14 | 0.0 | 2.1 |
| world_fixed_ego_moving | epW_budget_far | 14 | 1 | 0.10 | 0.0 | 0.7 |
| world_fixed_ego_moving | epW_budget_near | 14 | 1 | 0.10 | 7.1 | 0.5 |
| world_fixed_ego_moving | epW_replace_far | 12 | 1 | 1.65 | 0.0 | 0.6 |
| world_fixed_ego_moving | epW_replace_near | 11 | 0 | - | 0.0 | 0.6 |
| world_fixed_ego_slow | epW_budget_far | 7 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_budget_near | 7 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_replace_far | 9 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_replace_near | 10 | 1 | 1.14 | 0.0 | 3.8 |

L2d: false-episode rate on 48 clean test windows 2.1 %

| group | kind | episodes | detected in 3 s | median delay (s) | onset scan alarm % | sustained scan alarm % |
|---|---|---|---|---|---|---|
| sensor_fixed | ep_budget_far | 21 | 0 | - | 0.0 | 0.0 |
| sensor_fixed | ep_budget_near | 21 | 0 | - | 0.0 | 0.0 |
| sensor_fixed | ep_replace_far | 21 | 0 | - | 0.0 | 0.2 |
| sensor_fixed | ep_replace_near | 21 | 11 | 0.10 | 38.1 | 31.0 |
| sensor_fixed_ego_moving | ep_budget_far | 13 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_moving | ep_budget_near | 13 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_moving | ep_replace_far | 11 | 0 | - | 0.0 | 0.3 |
| sensor_fixed_ego_moving | ep_replace_near | 14 | 8 | 0.10 | 35.7 | 42.6 |
| sensor_fixed_ego_slow | ep_budget_far | 8 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_slow | ep_budget_near | 8 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_slow | ep_replace_far | 10 | 0 | - | 0.0 | 0.0 |
| sensor_fixed_ego_slow | ep_replace_near | 7 | 3 | 0.10 | 42.9 | 7.9 |
| world_fixed | epW_budget_far | 21 | 0 | - | 0.0 | 0.2 |
| world_fixed | epW_budget_near | 21 | 0 | - | 0.0 | 0.0 |
| world_fixed | epW_replace_far | 21 | 0 | - | 0.0 | 0.2 |
| world_fixed | epW_replace_near | 21 | 10 | 0.10 | 33.3 | 0.0 |
| world_fixed_ego_moving | epW_budget_far | 14 | 0 | - | 0.0 | 0.2 |
| world_fixed_ego_moving | epW_budget_near | 14 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_moving | epW_replace_far | 12 | 0 | - | 0.0 | 0.3 |
| world_fixed_ego_moving | epW_replace_near | 11 | 7 | 0.10 | 36.4 | 0.0 |
| world_fixed_ego_slow | epW_budget_far | 7 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_budget_near | 7 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_replace_far | 9 | 0 | - | 0.0 | 0.0 |
| world_fixed_ego_slow | epW_replace_near | 10 | 3 | 0.10 | 30.0 | 0.0 |

## harness_L1_L2a_int (budget 1 % on validation normals; combiner noisy_or)

| configuration | AUC | FA test % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.602 | 1.8 | 52.5 | 1.4 | 14.5 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |
| only_L1 | 0.559 | 1.6 | 1.4 | 1.4 | 16.1 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |
| only_L2a_int | 0.552 | 0.2 | 51.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

## harness_full (budget 1 % on validation normals; combiner noisy_or)

| configuration | AUC | FA test % | IntensitySpoof | PointDrop | cmp_boxcloud | cmp_mradd_far | cmp_mradd_near | ph_budget_far | ph_budget_near | ph_replace_far | ph_replace_near |
|---|---|---|---|---|---|---|---|---|---|---|---|
| all | 0.750 | 0.8 | 28.6 | 6.9 | 6.3 | 20.8 | 16.1 | 0.8 | 1.0 | 2.4 | 9.2 |
| only_L1 | 0.559 | 1.6 | 1.4 | 1.4 | 16.1 | 62.5 | 1.4 | 1.8 | 1.4 | 3.1 | 1.4 |
| only_L2a_int | 0.552 | 0.2 | 51.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| only_L2c | 0.558 | 2.1 | 1.8 | 87.5 | 1.8 | 1.8 | 1.8 | 1.8 | 1.8 | 1.8 | 1.8 |
| only_L2d | 0.669 | 0.2 | 0.2 | 0.2 | 2.2 | 0.2 | 32.4 | 0.2 | 0.2 | 0.2 | 29.2 |
| all_but_L1 | 0.717 | 0.2 | 32.7 | 4.5 | 0.6 | 0.0 | 14.3 | 0.0 | 0.0 | 0.4 | 7.6 |
| all_but_L2a_int | 0.720 | 0.8 | 1.0 | 3.7 | 6.3 | 20.6 | 18.6 | 1.4 | 1.4 | 2.4 | 12.0 |
| all_but_L2c | 0.719 | 0.9 | 46.9 | 0.8 | 7.3 | 28.6 | 20.6 | 1.6 | 1.4 | 2.9 | 16.1 |
| all_but_L2d | 0.649 | 1.1 | 52.7 | 10.6 | 8.4 | 36.9 | 1.2 | 1.4 | 1.2 | 2.4 | 1.2 |

Scoring cost: 112 ms per clean scan (L2c + L2d, image build included)
