# WP3 LiDAR brief (state after S1, 2026-10-22)

## Current state
- S1 (data layer + attack generator): REVIEW. Acceptance A1-A7 all MET (notes/WP3_lidar.md, results/WP3/S1_acceptance.json). Tables: results/WP3/S1_tables.md.
- v2 descriptor and every v2 number reproduced exactly on the v3 layer: test acc 90.19 %, AUC 0.9696; operating points; ray-cast protocol (39.1/30.2 add, 8.8/4.5 budget_add, replace = FA); retrained baseline bit-identical.

## Layout
- lidar/data.py: split (TEST 0001 0005 0095 0039 0079 0028 0052; VAL 0011 0035 0027; 13 train), drive_dir, scan_files, load (N x 4 float32, intensity 0-1), group_id "<drive>/<file>", CACHE.
- lidar/features.py: COPY of v2 (describe 211 dims incl. occlusion/patch features, temporal 218 more, attacks, raycast_ghost, box_hits).
- lidar/raycast.py: eval phantoms. eval_params(rng, band near 5-15 / far 15-40 / all, budget 50-400), phantom(pts, p, rng, mode) -> (scan, n, params used), modes add / replace / budget_add / budget, physics_report, box_surface_frac. boxcloud_ghost only to compare with v2.
- lidar/build.py: row builders (train4 = v2 4-class rows, rayv2 = v2 ray-cast protocol, rayw3 = near/far phantoms, episodes = persistent sequences). lidar/sequence.py: rolling log-odds, 3 s episode rule. lidar/train_xgb.py: v2 search (copy).
- tools/WP3_S1_{build,split,reproduce,tables}.py; tests/lidar/test_physics.py (11 tests).
- Cache ../data_extra/cache_v3/WP3/{train4,rayv2,rayw3,episodes}/<drive>.pkl = {"meta": DataFrame, "X": float32 (rows x 429)}; 0.17 GB. Columns: feature_names_temporal() order. Rebuild: python -u -W ignore tools/WP3_S1_build.py (resumable, ~1.5 h on a shared machine).

## Baseline for later steps (v2 model, test, threshold = 1% of val normal scans; per-scan, 0.8 % test FA)
- Ray-cast, onset / sustained: add far 20.6 / 14.2, add near 74.4 / 59.6; budget_add (50-400 pts) far 7.7 / 4.7, near 6.8 / 3.5; replace and budget = FA (physics bound).
- Episodes (3 s): box cloud 9/14; ray-cast budget_add near 4/21, far 2/21; budget (replace) near 2/21, far 0/21.
- Targets: ray-cast 50-400 added points >= 60 % at 1 % FA; near sparse > 50 %. Far from met: need object-level checks (S2-S6).

## Physics facts
- Phantom = first surface of a 4 x 1.8 x 1.5 m box along each real ray; ideal scene gives 385 points at 30 m, ~1/r^2 (slope -1.9), 3293 at 10 m; real KITTI median ~270 at 30 m.
- add keeps the real return behind (multi-return sensor); replace removes it (single return = physics bound, indistinguishable from a real car for a single LiDAR).
- PointDrop: random 50-100 % of points inside one sector (10-60 deg, <= 60 m); IntensitySpoof: intensity 0.8-1 in a sector (<= 40 m), xyz untouched.

## Pitfalls
- raycast_ghost(retry=True) shifts the azimuth: use lidar.raycast.phantom to get the parameters actually used.
- Near (5-15 m) full "add" phantoms are dense (median 2200 pts): only budget-limited ones are sparse.
- Scan file names repeat across drives: always "<drive>/<file>". First scan of each drive has no previous scan (skipped in train4).
- Operating point conventions: v2 quantile(1 - fpr) on val normals; "~1 % FA" of the WP file = val_fpr 0.02 (test FA 1.05 %).
- Test touched only by fixed v2 models and the retrained baseline (same protocol as v2); no choice made on test.
