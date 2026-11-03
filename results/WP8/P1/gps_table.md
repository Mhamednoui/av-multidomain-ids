# GPS: detection vs false alarm (KITTI test drives, row level)

**re-analysis of v3 test outputs (no refit).** Source files: results/WP1/cache/s8_raw.pkl (raw layer scores, 7 KITTI test drives, 11,074 rows), results/WP1/frozen_gps (calibrators, noisy-or log, threshold), results/WP1/S8_dev.json (CUSUM selection); cross-check results/WP1/S8_kitti.json

| subset | n pos / n neg | AUC [95% CI] | det@0.5% FA | det@1% FA | det@2% FA | det@5% FA | op. point (FA / det) |
|---|---|---|---|---|---|---|---|
| ALL attacks (6) | 4395 / 6679 | 0.895 [0.823, 0.935] | 66.8% [49%, 76%] | 68.8% [51%, 77%] | 71.2% [53%, 80%] | 74.7% [58%, 82%] | 1.20% / 69.2% |
| seen by the combiner (4) | 2921 / 6679 | 0.906 [0.851, 0.937] | 71.9% [59%, 78%] | 73.5% [61%, 79%] | 75.4% [63%, 82%] | 78.7% [67%, 84%] | 1.20% / 73.8% |
| unseen by the combiner: Doppler + meaconing (2) | 1474 / 6679 | 0.874 [0.760, 0.934] | 56.6% [26%, 72%] | 59.5% [28%, 74%] | 62.9% [33%, 76%] | 66.7% [39%, 79%] | 1.20% / 60.1% |
| drift | 645 / 6679 | 0.864 [0.808, 0.907] | 43.1% [29%, 56%] | 48.4% [32%, 61%] | 53.2% [38%, 66%] | 62.2% [48%, 73%] | 1.20% / 49.1% |
| accel_drift | 766 / 6679 | 0.834 [0.736, 0.885] | 54.2% [26%, 67%] | 55.5% [29%, 68%] | 58.7% [33%, 71%] | 63.1% [39%, 73%] | 1.20% / 56.1% |
| jump | 720 / 6679 | 1.000 [1.000, 1.000] | 100.0% [100%, 100%] | 100.0% [100%, 100%] | 100.0% [100%, 100%] | 100.0% [100%, 100%] | 1.20% / 100.0% |
| freeze | 790 / 6679 | 0.924 [0.804, 0.973] | 86.8% [69%, 94%] | 87.2% [70%, 94%] | 87.3% [70%, 94%] | 88.0% [71%, 94%] | 1.20% / 87.2% |
| doppler_spoof | 756 / 6679 | 0.879 [0.794, 0.922] | 53.4% [23%, 68%] | 55.8% [26%, 70%] | 59.8% [30%, 73%] | 64.0% [37%, 76%] | 1.20% / 56.5% |
| meaconing | 718 / 6679 | 0.870 [0.730, 0.946] | 60.0% [24%, 78%] | 63.4% [27%, 80%] | 66.2% [30%, 82%] | 69.5% [38%, 84%] | 1.20% / 63.9% |

Seen vs unseen: the combiner (noisy-or log) was fitted without the Doppler and meaconing rows (WP1 S8); the layers themselves are physics rules and normal-only filters. Row-level numbers differ from the run-level headline of RESULTS_v3.md (76.2% mean run-level detection at 1.83% clean-run FA): a run counts as detected at its first alarm, a row only when it alarms itself. Check against S8_kitti.json: AUC and row-level FA/detection reproduced exactly.