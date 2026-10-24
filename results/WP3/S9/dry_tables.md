# S9 tables (dryrun_val); combiner max; detection and FA in %; * = physically impossible on a single-return sensor (comparison)

## Headline stack, per attack (95 % CI = bootstrap over test drives)

| attack | detection | 95 % CI | n scans | per-drive range | AUC |
|---|---|---|---|---|---|
| replace near | 30.3 | [29.5, 30.8] | 185 | 29.5-30.8 | 0.877 |
| replace far | 5.9 | [0.0, 14.3] | 185 | 0.0-14.3 | 0.591 |
| budget near | 5.4 | [0.0, 14.3] | 185 | 0.0-14.3 | 0.598 |
| budget far | 5.4 | [0.0, 14.3] | 185 | 0.0-14.3 | 0.571 |
| PointDrop | 29.7 | [25.0, 32.1] | 185 | 25.0-32.1 | 0.969 |
| IntensitySpoof | 45.4 | [25.6, 65.1] | 185 | 25.6-65.1 | 0.825 |
| box cloud* | 15.1 | [10.3, 20.6] | 185 | 10.3-20.6 | 0.717 |
| multi-return add near* | 25.4 | [20.5, 31.7] | 185 | 20.5-31.7 | 0.828 |
| multi-return add far* | 62.2 | [50.0, 67.9] | 185 | 50.0-67.9 | 0.840 |


FA clean scans 1.09 [0.43, 1.60], threshold from reference FA 0.99; LODO FA (16 train+val drives) mean 1.31, worst 3.58 (0070).


## False alarms per drive (test clean scans) and leave-one-drive-out on the reference

| drive | test FA |
|---|---|
| 0011 | 0.43 |
| 0027 | 1.60 |
| 0035 | 1.54 |

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
| all four | 1.09 | 30.3 | 5.9 | 5.4 | 5.4 | 29.7 | 45.4 | 15.1 | 25.4 | 62.2 |
| all but L1 | 1.09 | 34.6 | 5.4 | 5.4 | 5.4 | 37.3 | 45.4 | 9.2 | 26.5 | 5.4 |
| all but L2a | 0.55 | 31.4 | 1.6 | 1.1 | 1.1 | 35.1 | 1.1 | 10.8 | 23.8 | 60.0 |
| all but L2c | 0.73 | 34.6 | 5.4 | 4.9 | 4.9 | 3.2 | 45.4 | 14.6 | 25.9 | 62.2 |
| all but L2d | 0.91 | 4.3 | 5.4 | 4.9 | 4.9 | 36.8 | 44.9 | 10.8 | 4.9 | 62.2 |
| L1 alone (own 1 %) | 0.00 | 0.0 | 0.5 | 0.0 | 0.0 | 0.0 | 0.0 | 5.9 | 0.0 | 60.0 |
| L2a alone (own 1 %) | 2.73 | 5.9 | 6.5 | 6.5 | 6.5 | 4.9 | 54.1 | 7.0 | 7.0 | 7.0 |
| L2c alone (own 1 %) | 0.91 | 0.5 | 0.5 | 0.5 | 0.5 | 91.4 | 0.5 | 0.5 | 0.5 | 0.5 |
| L2d alone (own 1 %) | 1.09 | 46.5 | 1.1 | 1.1 | 1.1 | 1.1 | 1.1 | 9.2 | 30.3 | 1.1 |
| each layer at its own 1 %, union | 4.74 | 49.7 | 8.6 | 8.1 | 8.1 | 92.4 | 54.6 | 22.7 | 35.1 | 64.3 |


## Does each layer earn its place? (largest detection loss when removed, rule: >= 3 points)

| layer | largest loss | on | earns |
|---|---|---|---|
| L1 | 0.5 | replace far | False |
| L2a | 44.3 | IntensitySpoof | True |
| L2c | 26.5 | PointDrop | True |
| L2d | 25.9 | replace near | True |


## Combiners and budgets

| configuration | FA | replace near | replace far | budget near | budget far | PointDrop | IntensitySpoof | box cloud* | multi-return add near* | multi-return add far* |
|---|---|---|---|---|---|---|---|---|---|---|
| max 1 % (chosen) | 1.09 | 30.3 | 5.9 | 5.4 | 5.4 | 29.7 | 45.4 | 15.1 | 25.4 | 62.2 |
| split 1 % | 1.09 | 29.7 | 5.4 | 5.4 | 5.4 | 18.4 | 45.4 | 15.1 | 23.8 | 62.2 |
| noisy_or 1 % | 0.55 | 17.3 | 1.6 | 1.6 | 1.1 | 28.6 | 11.4 | 8.1 | 22.7 | 38.9 |
| max total 2 % | 2.19 | 40.5 | 6.5 | 5.9 | 5.9 | 73.0 | 48.1 | 17.3 | 29.7 | 62.7 |
| max total 4 % | 4.74 | 49.7 | 8.6 | 8.1 | 8.1 | 92.4 | 54.6 | 22.7 | 35.1 | 64.3 |


## Dilution: stack versus the best single layer per attack (that layer at its own 1 %)

| attack | best layer | layer alone | stack | loss |
|---|---|---|---|---|
| replace near | L2d | 46.5 | 30.3 | 16.2 |
| replace far | L2a | 6.5 | 5.9 | 0.5 |
| budget near | L2a | 6.5 | 5.4 | 1.1 |
| budget far | L2a | 6.5 | 5.4 | 1.1 |
| PointDrop | L2c | 91.4 | 29.7 | 61.6 |
| IntensitySpoof | L2a | 54.1 | 45.4 | 8.6 |


## Optional rows (never headline)

| configuration | FA | replace near | replace far | budget near | budget far | PointDrop | IntensitySpoof | box cloud* | multi-return add near* | multi-return add far* |
|---|---|---|---|---|---|---|---|---|---|---|
| density in L2a | 1.28 | 30.8 | 5.9 | 5.4 | 5.4 | 22.7 | 44.9 | 15.7 | 32.4 | 62.2 |


## Which layer carries the alarms of the stack (count of alarmed scans by dominant layer)

| attack | L1 | L2a | L2c | L2d |
|---|---|---|---|---|
| replace near | 0 | 6 | 0 | 50 |
| replace far | 1 | 8 | 1 | 1 |
| budget near | 0 | 8 | 1 | 1 |
| budget far | 0 | 8 | 1 | 1 |
| PointDrop | 0 | 5 | 49 | 1 |
| IntensitySpoof | 0 | 83 | 0 | 1 |
| box cloud* | 11 | 8 | 1 | 8 |
| multi-return add near* | 0 | 6 | 1 | 40 |
| multi-return add far* | 111 | 4 | 0 | 0 |


## Persistent world-fixed episodes (3 s rule; false-episode rate stack 17.6 % of 17 clean windows)

| detector | kind | detected | exact 95 % CI | median first alert (s) | onset scan | sustained scan | false-episode rate |
|---|---|---|---|---|---|---|---|
| stack | epW_replace_near | 5/6 | [36, 100] | 0.10 | 50.0 | 9.8 | 17.6 |
| L1 | epW_replace_near | 0/6 | [0, 46] | - | 0.0 | 0.0 | 0.0 |
| L2a | epW_replace_near | 2/6 | [4, 78] | 0.10 | 33.3 | 12.1 | 11.8 |
| L2c | epW_replace_near | 1/6 | [0, 64] | 1.44 | 0.0 | 2.9 | 5.9 |
| L2d | epW_replace_near | 4/6 | [22, 96] | 0.10 | 33.3 | 0.0 | 5.9 |
| density in L2a | epW_replace_near | 3/6 | [12, 88] | 0.10 | 50.0 | 10.3 | 17.6 |
