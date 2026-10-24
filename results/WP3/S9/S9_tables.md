# S9 tables (final); combiner max; detection and FA in %; * = physically impossible on a single-return sensor (comparison)

## Headline stack, per attack (95 % CI = bootstrap over test drives)

| attack | detection | 95 % CI | n scans | per-drive range | AUC |
|---|---|---|---|---|---|
| replace near | 17.8 | [15.2, 21.9] | 510 | 13.3-27.8 | 0.835 |
| replace far | 0.8 | [0.0, 1.6] | 510 | 0.0-2.3 | 0.549 |
| budget near | 0.8 | [0.0, 1.6] | 510 | 0.0-2.3 | 0.607 |
| budget far | 0.8 | [0.0, 1.6] | 510 | 0.0-2.3 | 0.528 |
| PointDrop | 27.6 | [25.1, 29.1] | 510 | 19.4-31.4 | 0.975 |
| IntensitySpoof | 51.6 | [42.0, 62.3] | 510 | 30.8-70.6 | 0.914 |
| box cloud* | 5.3 | [3.8, 6.9] | 510 | 3.0-8.3 | 0.649 |
| multi-return add near* | 23.5 | [18.8, 30.1] | 510 | 0.0-36.1 | 0.851 |
| multi-return add far* | 62.2 | [58.5, 68.5] | 510 | 51.5-84.6 | 0.840 |


FA clean scans 1.18 [0.26, 2.02], threshold from reference FA 0.99; LODO FA (16 train+val drives) mean 1.31, worst 3.58 (0070).


## False alarms per drive (test clean scans) and leave-one-drive-out on the reference

| drive | test FA |
|---|---|
| 0001 | 1.87 |
| 0005 | 0.00 |
| 0028 | 0.23 |
| 0039 | 2.54 |
| 0052 | 0.00 |
| 0079 | 0.00 |
| 0095 | 1.87 |

| drive | LODO FA |
|---|---|
| 0002 | 0.00 |
| 0011 | 0.43 |
| 0013 | 2.80 |
| 0015 | 1.69 |
| 0017 | 0.00 |
| 0019 | 0.21 |
| 0020 | 0.00 |
| 0027 | 1.60 |
| 0029 | 0.47 |
| 0035 | 1.54 |
| 0046 | 0.00 |
| 0048 | 0.00 |
| 0060 | 0.00 |
| 0070 | 3.58 |
| 0106 | 3.54 |
| 0113 | 0.00 |


## Ablation (same combiner, 1 % total budget)

| configuration | FA | replace near | replace far | budget near | budget far | PointDrop | IntensitySpoof | box cloud* | multi-return add near* | multi-return add far* |
|---|---|---|---|---|---|---|---|---|---|---|
| all four | 1.18 | 17.8 | 0.8 | 0.8 | 0.8 | 27.6 | 51.6 | 5.3 | 23.5 | 62.2 |
| all but L1 | 1.11 | 20.8 | 0.8 | 0.8 | 0.8 | 36.3 | 51.6 | 1.8 | 25.1 | 0.8 |
| all but L2a | 1.05 | 20.8 | 0.8 | 0.8 | 0.8 | 36.3 | 0.8 | 5.7 | 25.1 | 62.2 |
| all but L2c | 0.39 | 20.0 | 0.0 | 0.0 | 0.0 | 0.0 | 51.0 | 5.1 | 24.5 | 62.0 |
| all but L2d | 1.18 | 0.8 | 0.8 | 0.8 | 0.8 | 36.3 | 51.6 | 4.7 | 0.8 | 62.2 |
| L1 alone (own 1 %) | 0.13 | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | 0.0 | 4.1 | 0.0 | 62.2 |
| L2a alone (own 1 %) | 0.98 | 0.8 | 0.8 | 0.8 | 0.8 | 0.6 | 65.3 | 0.8 | 0.8 | 0.8 |
| L2c alone (own 1 %) | 2.10 | 1.8 | 1.8 | 1.8 | 1.8 | 87.3 | 1.8 | 1.8 | 1.8 | 1.8 |
| L2d alone (own 1 %) | 0.20 | 32.5 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 | 2.5 | 34.5 | 0.2 |
| each layer at its own 1 %, union | 3.41 | 34.3 | 2.9 | 2.7 | 2.7 | 87.5 | 66.5 | 8.8 | 36.7 | 63.5 |


## Does each layer earn its place? (largest detection loss when removed, rule: >= 3 points)

| layer | largest loss | on | earns |
|---|---|---|---|
| L1 | 0.0 | replace far | False |
| L2a | 50.8 | IntensitySpoof | True |
| L2c | 27.6 | PointDrop | True |
| L2d | 17.1 | replace near | True |


## Combiners and budgets

| configuration | FA | replace near | replace far | budget near | budget far | PointDrop | IntensitySpoof | box cloud* | multi-return add near* | multi-return add far* |
|---|---|---|---|---|---|---|---|---|---|---|
| max 1 % (chosen) | 1.18 | 17.8 | 0.8 | 0.8 | 0.8 | 27.6 | 51.6 | 5.3 | 23.5 | 62.2 |
| split 1 % | 1.18 | 16.9 | 0.8 | 0.8 | 0.8 | 15.9 | 51.6 | 5.3 | 22.5 | 61.8 |
| noisy_or 1 % | 0.07 | 3.7 | 0.6 | 0.0 | 0.0 | 3.7 | 8.4 | 1.6 | 5.9 | 23.3 |
| max total 2 % | 2.03 | 24.7 | 1.8 | 1.6 | 1.6 | 68.0 | 57.5 | 6.7 | 28.8 | 62.7 |
| max total 4 % | 3.41 | 34.3 | 2.9 | 2.7 | 2.7 | 87.6 | 66.5 | 8.8 | 36.7 | 63.5 |


## Dilution: stack versus the best single layer per attack (that layer at its own 1 %)

| attack | best layer | layer alone | stack | loss |
|---|---|---|---|---|
| replace near | L2d | 32.5 | 17.8 | 14.7 |
| replace far | L2c | 1.8 | 0.8 | 1.0 |
| budget near | L2c | 1.8 | 0.8 | 1.0 |
| budget far | L2c | 1.8 | 0.8 | 1.0 |
| PointDrop | L2c | 87.3 | 27.6 | 59.6 |
| IntensitySpoof | L2a | 65.3 | 51.6 | 13.7 |


## Optional rows (never headline)

| configuration | FA | replace near | replace far | budget near | budget far | PointDrop | IntensitySpoof | box cloud* | multi-return add near* | multi-return add far* |
|---|---|---|---|---|---|---|---|---|---|---|
| L2b alone | 0.46 | 6.3 | 0.8 | 1.0 | 0.6 | 0.6 | 0.6 | 18.8 | 69.4 | 28.4 |
| L4 alone | 0.72 | 19.2 | 0.6 | 0.8 | 0.6 | 90.8 | 100.0 | 5.7 | 15.1 | 1.0 |
| headline + L2b (optional) | 1.18 | 17.3 | 1.0 | 1.0 | 1.0 | 6.3 | 52.0 | 18.6 | 69.0 | 74.7 |
| headline + L4 (seen families, never headline) | 1.51 | 22.4 | 1.0 | 1.0 | 1.0 | 85.7 | 99.4 | 7.3 | 24.9 | 62.0 |
| density part added to L2a | 1.97 | 18.2 | 1.4 | 1.4 | 1.4 | 19.2 | 50.4 | 7.1 | 44.1 | 64.7 |


## Which layer carries the alarms of the stack (count of alarmed scans by dominant layer)

| attack | L1 | L2a | L2c | L2d |
|---|---|---|---|---|
| replace near | 0 | 0 | 4 | 87 |
| replace far | 0 | 0 | 4 | 0 |
| budget near | 0 | 0 | 4 | 0 |
| budget far | 0 | 0 | 4 | 0 |
| PointDrop | 0 | 0 | 141 | 0 |
| IntensitySpoof | 0 | 260 | 3 | 0 |
| box cloud* | 21 | 0 | 3 | 3 |
| multi-return add near* | 0 | 0 | 3 | 117 |
| multi-return add far* | 316 | 0 | 1 | 0 |


## Persistent sensor-fixed episodes (3 s rule; false-episode rate stack 6.2 % of 48 clean windows)

| detector | kind | detected | exact 95 % CI | median first alert (s) | onset scan | sustained scan | false-episode rate |
|---|---|---|---|---|---|---|---|
| stack | ep_budget_far | 1/21 | [0, 24] | 1.96 | 0.0 | 0.5 | 6.2 |
| stack | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.3 | 6.2 |
| stack | ep_replace_far | 2/21 | [1, 30] | 1.08 | 0.0 | 2.1 | 6.2 |
| stack | ep_replace_near | 11/21 | [30, 74] | 0.10 | 23.8 | 27.4 | 6.2 |
| L1 | ep_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.0 | 0.0 |
| L1 | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.0 | 0.0 |
| L1 | ep_replace_far | 0/21 | [0, 16] | - | 0.0 | 0.7 | 0.0 |
| L1 | ep_replace_near | 0/21 | [0, 16] | - | 0.0 | 0.3 | 0.0 |
| L2a | ep_budget_far | 2/21 | [1, 30] | 1.60 | 0.0 | 2.5 | 6.2 |
| L2a | ep_budget_near | 2/21 | [1, 30] | 2.84 | 0.0 | 1.6 | 6.2 |
| L2a | ep_replace_far | 0/21 | [0, 16] | - | 0.0 | 0.0 | 6.2 |
| L2a | ep_replace_near | 0/21 | [0, 16] | - | 0.0 | 0.2 | 6.2 |
| L2c | ep_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.2 | 10.4 |
| L2c | ep_budget_near | 2/21 | [1, 30] | 2.63 | 0.0 | 1.0 | 10.4 |
| L2c | ep_replace_far | 2/21 | [1, 30] | 0.93 | 0.0 | 2.0 | 10.4 |
| L2c | ep_replace_near | 4/21 | [5, 42] | 0.10 | 4.8 | 2.0 | 10.4 |
| L2d | ep_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.0 | 2.1 |
| L2d | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.0 | 2.1 |
| L2d | ep_replace_far | 0/21 | [0, 16] | - | 0.0 | 0.2 | 2.1 |
| L2d | ep_replace_near | 11/21 | [30, 74] | 0.10 | 38.1 | 31.0 | 2.1 |
| L2b alone | ep_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.3 | 6.2 |
| L2b alone | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.0 | 6.2 |
| L2b alone | ep_replace_far | 0/21 | [0, 16] | - | 0.0 | 0.0 | 6.2 |
| L2b alone | ep_replace_near | 3/21 | [3, 36] | 0.10 | 0.0 | 4.1 | 6.2 |
| L4 alone | ep_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.0 | 4.2 |
| L4 alone | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.2 | 4.2 |
| L4 alone | ep_replace_far | 1/21 | [0, 24] | 2.37 | 0.0 | 0.7 | 4.2 |
| L4 alone | ep_replace_near | 8/21 | [18, 62] | 0.10 | 28.6 | 2.1 | 4.2 |
| headline + L2b (optional) | ep_budget_far | 1/21 | [0, 24] | 1.96 | 0.0 | 0.7 | 4.2 |
| headline + L2b (optional) | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.3 | 4.2 |
| headline + L2b (optional) | ep_replace_far | 1/21 | [0, 24] | 1.96 | 0.0 | 1.3 | 4.2 |
| headline + L2b (optional) | ep_replace_near | 9/21 | [22, 66] | 0.10 | 19.0 | 27.3 | 4.2 |
| headline + L4 (seen families, never headline) | ep_budget_far | 1/21 | [0, 24] | 1.96 | 0.0 | 0.5 | 8.3 |
| headline + L4 (seen families, never headline) | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.3 | 8.3 |
| headline + L4 (seen families, never headline) | ep_replace_far | 1/21 | [0, 24] | 1.96 | 0.0 | 2.5 | 8.3 |
| headline + L4 (seen families, never headline) | ep_replace_near | 12/21 | [34, 78] | 0.10 | 23.8 | 27.6 | 8.3 |
| density part added to L2a | ep_budget_far | 3/21 | [3, 36] | 0.41 | 4.8 | 1.3 | 8.3 |
| density part added to L2a | ep_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.7 | 8.3 |
| density part added to L2a | ep_replace_far | 1/21 | [0, 24] | 1.86 | 0.0 | 2.6 | 8.3 |
| density part added to L2a | ep_replace_near | 12/21 | [34, 78] | 0.10 | 23.8 | 27.9 | 8.3 |


## Persistent world-fixed episodes (3 s rule; false-episode rate stack 6.2 % of 48 clean windows)

| detector | kind | detected | exact 95 % CI | median first alert (s) | onset scan | sustained scan | false-episode rate |
|---|---|---|---|---|---|---|---|
| stack | epW_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.5 | 6.2 |
| stack | epW_budget_near | 2/21 | [1, 30] | 0.15 | 0.0 | 0.5 | 6.2 |
| stack | epW_replace_far | 2/21 | [1, 30] | 1.81 | 0.0 | 2.0 | 6.2 |
| stack | epW_replace_near | 8/21 | [18, 62] | 0.10 | 23.8 | 2.1 | 6.2 |
| L1 | epW_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.3 | 0.0 |
| L1 | epW_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.5 | 0.0 |
| L1 | epW_replace_far | 1/21 | [0, 24] | 2.37 | 0.0 | 1.5 | 0.0 |
| L1 | epW_replace_near | 0/21 | [0, 16] | - | 0.0 | 0.8 | 0.0 |
| L2a | epW_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.3 | 6.2 |
| L2a | epW_budget_near | 1/21 | [0, 24] | 0.10 | 4.8 | 0.2 | 6.2 |
| L2a | epW_replace_far | 1/21 | [0, 24] | 1.14 | 0.0 | 1.3 | 6.2 |
| L2a | epW_replace_near | 1/21 | [0, 24] | 0.93 | 0.0 | 1.3 | 6.2 |
| L2c | epW_budget_far | 1/21 | [0, 24] | 0.10 | 0.0 | 0.5 | 10.4 |
| L2c | epW_budget_near | 1/21 | [0, 24] | 0.10 | 4.8 | 0.3 | 10.4 |
| L2c | epW_replace_far | 1/21 | [0, 24] | 1.65 | 0.0 | 0.3 | 10.4 |
| L2c | epW_replace_near | 1/21 | [0, 24] | 1.14 | 0.0 | 2.1 | 10.4 |
| L2d | epW_budget_far | 0/21 | [0, 16] | - | 0.0 | 0.2 | 2.1 |
| L2d | epW_budget_near | 0/21 | [0, 16] | - | 0.0 | 0.0 | 2.1 |
| L2d | epW_replace_far | 0/21 | [0, 16] | - | 0.0 | 0.2 | 2.1 |
| L2d | epW_replace_near | 10/21 | [26, 70] | 0.10 | 33.3 | 0.0 | 2.1 |
| density part added to L2a | epW_budget_far | 1/21 | [0, 24] | 0.10 | 4.8 | 0.7 | 8.3 |
| density part added to L2a | epW_budget_near | 1/21 | [0, 24] | 0.10 | 0.0 | 0.7 | 8.3 |
| density part added to L2a | epW_replace_far | 2/21 | [1, 30] | 1.86 | 0.0 | 2.8 | 8.3 |
| density part added to L2a | epW_replace_near | 8/21 | [18, 62] | 0.10 | 23.8 | 3.0 | 8.3 |


## v2 model (retrained v2 descriptor, box-cloud class) on the same single-return attacks, threshold val 1 % (test FA 0.79 %)

| attack | v2 detection | 95 % CI | v2 AUC | v3 stack detection | v3 AUC |
|---|---|---|---|---|---|
| replace near | 1.0 | [0.1, 2.2] | 0.710 | 17.8 | 0.835 |
| replace far | 1.0 | [0.1, 2.2] | 0.494 | 0.8 | 0.549 |
| budget near | 1.0 | [0.1, 2.2] | 0.529 | 0.8 | 0.607 |
| budget far | 1.0 | [0.1, 2.2] | 0.494 | 0.8 | 0.528 |
| PointDrop | 88.6 | [85.0, 92.6] | 0.994 | 27.6 | 0.975 |
| IntensitySpoof | 100.0 | [100.0, 100.0] | 1.000 | 51.6 | 0.914 |
| box cloud* | 18.8 | [14.5, 23.6] | 0.875 | 5.3 | 0.649 |
| multi-return add near* | 63.7 | [44.1, 81.6] | 0.958 | 23.5 | 0.851 |
| multi-return add far* | 10.4 | [6.3, 15.0] | 0.659 | 62.2 | 0.840 |


Pooled AUC over the six single-return attacks: v2 0.704, v3 stack 0.735.
