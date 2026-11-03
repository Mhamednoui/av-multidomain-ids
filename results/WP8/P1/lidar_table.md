# LiDAR: detection vs false alarm (KITTI test scans, scan level)

**re-analysis of v3 test outputs (no refit).** Source files: results/WP3/S9/test_scores.csv.gz (11,156 test scans, 7 KITTI test drives), threshold/FA from results/WP3/S9/final.json headline

| subset | n pos / n neg | AUC [95% CI] | det@0.5% FA | det@1% FA | det@2% FA | det@5% FA | op. point (FA / det) |
|---|---|---|---|---|---|---|---|
| ALL scan-level attacks (9) | 4590 / 1526 | 0.750 [0.722, 0.784] | 16.8% [16%, 33%] | 18.3% [16%, 36%] | 26.9% [18%, 40%] | 38.5% [32%, 48%] | 1.18% / 21.2% |
| physical phantoms (4: ph_*) | 2040 / 1526 | 0.630 [0.601, 0.668] | 3.7% [3%, 10%] | 4.6% [3%, 13%] | 6.7% [5%, 15%] | 14.6% [10%, 22%] | 1.18% / 5.0% |
| tamper (PointDrop + IntensitySpoof) | 1020 / 1526 | 0.944 [0.918, 0.969] | 25.5% [21%, 75%] | 28.7% [21%, 80%] | 60.4% [26%, 83%] | 81.0% [69%, 88%] | 1.18% / 39.6% |
| ph_replace_near | 510 / 1526 | 0.835 [0.784, 0.901] | 14.9% [13%, 37%] | 16.7% [14%, 50%] | 21.8% [18%, 58%] | 45.9% [29%, 71%] | 1.18% / 17.8% |
| ph_replace_far | 510 / 1526 | 0.549 [0.535, 0.577] | 0.0% [0%, 1%] | 0.6% [0%, 1%] | 1.8% [1%, 3%] | 4.5% [3%, 7%] | 1.18% / 0.8% |
| ph_budget_near | 510 / 1526 | 0.606 [0.566, 0.663] | 0.0% [0%, 0%] | 0.6% [0%, 1%] | 1.6% [1%, 2%] | 4.1% [3%, 6%] | 1.18% / 0.8% |
| ph_budget_far | 510 / 1526 | 0.528 [0.517, 0.547] | 0.0% [0%, 0%] | 0.6% [0%, 1%] | 1.6% [1%, 2%] | 3.9% [3%, 5%] | 1.18% / 0.8% |
| PointDrop | 510 / 1526 | 0.975 [0.962, 0.992] | 0.0% [0%, 86%] | 5.9% [0%, 94%] | 63.3% [7%, 95%] | 94.3% [82%, 98%] | 1.18% / 27.6% |
| IntensitySpoof | 510 / 1526 | 0.914 [0.867, 0.951] | 51.0% [41%, 66%] | 51.6% [42%, 72%] | 57.5% [43%, 75%] | 67.6% [56%, 80%] | 1.18% / 51.6% |
| cmp_boxcloud | 510 / 1526 | 0.649 [0.606, 0.703] | 4.7% [4%, 6%] | 5.1% [4%, 9%] | 6.1% [6%, 13%] | 13.1% [9%, 20%] | 1.18% / 5.3% |
| cmp_mradd_near | 510 / 1526 | 0.851 [0.798, 0.917] | 19.4% [16%, 35%] | 22.4% [16%, 49%] | 26.3% [21%, 59%] | 48.6% [31%, 75%] | 1.18% / 23.5% |
| cmp_mradd_far | 510 / 1526 | 0.840 [0.822, 0.883] | 61.6% [58%, 68%] | 61.8% [58%, 68%] | 62.7% [59%, 69%] | 64.1% [61%, 71%] | 1.18% / 62.2% |

Seen vs unseen: not applicable. The v3 LiDAR stack has no layer trained on attack data in its headline (L1 geometry rules, L2a/L2c/L2d normal-only or physics layers, combiner max), so every attack here is unseen. Episode frames (ep_*, epW_*) are in the test file but are scored per episode in v3 (RESULTS_v3.md section 6, R4); they are not pooled here. Known physics limit: calibrated far / budget phantoms are invisible to single-return physics (AUC about 0.5). Cross-check: per-attack AUC equals results/WP3/S9/final.json headline.auc.