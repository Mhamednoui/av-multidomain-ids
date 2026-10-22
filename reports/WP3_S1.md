# WP3 S1: LiDAR data layer + attack generator

Date: 2026-10-22    Worker: sonnet (medium, T2)

## Goal of the step
Build the LiDAR data layer (23 KITTI drives, WP1 split, groups "<drive>/<file>") and a physically consistent ray-cast attack generator; reproduce the v2 descriptor and baseline numbers on it.

## Acceptance rule (notes/WP3_lidar.md, written 2026-10-21 before any v3 result)
A1 v3 rows identical to v2 splits; A2 v2 model on v3 rows: acc 90.19 +-0.05, AUC 0.9696 +-0.001, operating points +-0.5; A3 retrained baseline acc +-1.5 / AUC +-0.01; A4 v2 ray-cast numbers +-1 point; A5 split saved, 23 drives, disjoint; A6 physics tests; A7 cache <= 5 GB.

## What was done
- lidar/{data,features(copy),raycast,build,sequence,train_xgb(copy)}.py; tools/WP3_S1_{build,split,reproduce,tables}.py; tests/lidar/test_physics.py (11 tests).
- Data: D04 KITTI, 23 drives (TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; 13 train). Cache 0.17 GB.
- Evaluation phantoms ray-cast only (add / replace / budget_add / budget, near 5-15 m, far 15-40 m, budget 50-400, onset and sustained, persistent episodes of 40 scans); box cloud kept only for the v2 comparison.

## Results (results/WP3/S1_reproduction.json; tables results/WP3/S1_tables.md)
| item | v3 layer | v2 |
|---|---|---|
| descriptor rows (train / val / test) | identical, max abs diff 0.0 | 18025 / 2196 / 6104 |
| v2 model test accuracy / AUC | 90.19 % / 0.9696 | 90.19 % / 0.9696 |
| retrained baseline (deployed temporal) acc / AUC | 90.19 % / 0.9696 | same |
| val-1% point (test FA 0.8 %): PD / IS / box cloud | 82.2 / 99.9 / 46.4 | same |
| val-2% point (test FA 1.0 %): PD / IS / box cloud | 83.9 / 99.9 / 51.4 | same |
| ray-cast add onset / sustained | 39.1 / 30.2 | same |
| ray-cast budget_add onset / sustained | 8.8 / 4.5 | same |
| ray-cast replace, budget | 1.05 (= FA) | same |
| box-cloud episodes within 3 s | 9 / 14 | 9 / 14 |

New WP3 baselines (v2 model, val-1% threshold, test): budget_add near 6.8 / 3.5, far 7.7 / 4.7; add near 74.4 / 59.6, far 20.6 / 14.2; ray-cast episodes within 3 s: budget_add near 4/21, far 2/21; replace near 2/21, far 0/21.
Acceptance: MET (A1-A7, results/WP3/S1_acceptance.json). Targets of WP3 (>= 60 % at 1 % FA for 50-400-point phantoms; near sparse > 50 %) are far from the baseline, as expected before S2-S6.

## Ablation row(s)
None (data step). Baseline row for the later table: v2 descriptor model alone.

## Problems, surprises, open questions
- A first train4 cache had the wrong width (218 instead of 429 columns); caught by the shape check before any result; fixed and rebuilt.
- "~1% FA" in the WP file is the val-2% operating point (test FA 1.05 %); the val-1% point has test FA 0.79 %. Both stored.
- Ideal-scene point count at 30 m is 385 vs ~270 measured on real KITTI; the test band is 150-450.
- PointDrop in v2 thins randomly 50-100 % inside a sector, not whole rays; kept for reproduction, tested as "only the sector is touched; frac 1 empties it".
- Build is slow on the shared machine (about 1.5 h); the cache makes later steps fast.

## Proposed next step
S2 L1 sensor geometry (64 rings, range / intensity limits, returns per direction), using the cached eval tables and the physics tests as the oracle.
