# WP3 LiDAR brief (state after S2, 2026-10-22)

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

## S2 state (2026-10-22, REVIEW)
- New modules: lidar/geometry.py (RingTable: 64 lines z = v_k + s_k*rho fitted on train; per-azimuth common mode; l1_stats = n_off_ring, sector_off_ring, n_range, n_intensity, n_dup), lidar/objects.py (car-like clusters), lidar/phantom.py (calibrated ray-cast: exact laser rays, Beta dropout, intensity library), lidar/calibration.py, lidar/l1.py (Layers: 5 rules + union), lidar/l1_build.py. Tools WP3_S2_{ringtable,calib_collect,calib_fit,build,eval,tables}.py. Tests tests/lidar/test_geometry.py (14).
- Model files: results/WP3/S2/ring_table.json, calibration_beta.npz (chosen on val), calib_choice.json. Cache ../data_extra/cache_v3/WP3/S2 (0.25 GB total with S1).
- Use lidar.phantom.phantom (exact rays + calibration) for all future attacks; lidar.raycast (S1) only for old comparison. Real car-like clusters have median 53 points at 30-35 m (not 270); calibrated phantoms are still ~1.5x denser unconditionally (full 4 m box vs partial views) but match at equal angular size.
- L1 result (test, once): FA 1.57 %; catches box cloud 47 %, ray-cast add/budget_add FAR 58-60 % (duplicate direction, only valid for unambiguous lasers >= ~20 m), nothing else; replace/budget/near/PointDrop/IntensitySpoof at FA (physics bound).
- Pitfalls: nearby lasers fire at the same azimuth (duplicate test only on unambiguous lasers); KITTI max range 80 m; ring residual needs the common mode; v2l1 rows depend on the exact rng path of build.drive_rows.

## S2b / S3 state (2026-10-22, REVIEW)
- S2b: lidar/singlereturn.py (one return per beam: laser + azimuth within 0.04 deg, nearest return survives); lidar.phantom.phantom(single_return=True default): add == replace, budget_add == budget; single_return=False only for calibration and old tests. VAL old vs fixed: results/WP3/S2b/val_old_vs_fixed.md. L1 far add 60 -> 1.5 % (artefact confirmed); v2 near add 86 -> 8.7 %; box cloud v2 65 -> 26 %, L1 46 -> 21 %. L1 test NOT re-scored (second exposure in S9). Cache ../data_extra/cache_v3/WP3/S2b (val only).
- S3: lidar/ego.py (OXTS planar poses, between()), lidar/segment.py (segment(pts, table, params) -> DataFrame, COLUMNS: cx cy cz range az length width heading height z_bottom n_points az_span elev_span n_rings ring_min ring_max ring_fill int_mean int_std carlike), lidar/assoc.py (mutual nearest centroid after ego-motion). Params in results/WP3/S3/choice.json: grid ground h0 0.30, e0 0.4, e1 0, min 5 points. Object tables of all 4673 clean scans: ../data_extra/cache_v3/WP3/S3/objects_<drive>.pkl = {objects, scans, params}; rebuild tools/WP3_S3_build.py (~35 min, 4 procs).
- Sanity: match 60-64 % (10-30 m, static lower bound), residual 0.13-0.19 m, oversize 1.6 %, 290-380 objects/scan (mostly small fragments), car-like 8-13/scan, 0.68 s/scan. Phantoms: one object only 62 % (far add) / 43 % (near add): near phantoms merge with ground-level structure (open for S4).

## S4 state (2026-10-24, REVIEW)
- lidar/density.py (ObjectModel, L2aStat/L2aUnion, layer "L2a"), lidar/s4_build.py, lidar/s4_eval.py; segment.cluster has optional tight near link (default off). Tools WP3_S4_{variants,build,dev,final,tables}.py; tests test_density.py, test_tiles.py (406 total). Cache ../data_extra/cache_v3/WP3/S4/{S3,S3_t} (1.3 GB total WP3). Unit = tile (cluster x 2 deg x 8 lasers x 2 m range), not cluster: near phantoms merge into giant clusters. Score = max + count of tiles with p<1 % (8 stats), thresholds by LODO over 16 train+val drives (val-only drifts: test FA 20 %).
- Test (LODO): FA 1.63 %; IntensitySpoof 56.5; PointDrop 1.2; calibrated phantoms 1.0-1.2 (= FA, physics bound); box cloud 3.9; episodes at chance. See reports/WP3_S4.md.
- Evaluation attack tables: S4 builders `drive_attacks`, `drive_episodes` (seeds [83,d,i], [89,d]); names ph_{replace,budget}_{near,far}, PointDrop, IntensitySpoof, cmp_*.

## S6 state (2026-10-24, REVIEW)
- New modules: lidar/background.py (Img 64 ring-bins x 360 az, moved() with OXTS, miss_stats, StatUnion Layer), lidar/track.py (cell-level hypotheses static / sensor-fixed / new / gone: app_*, fix_*, van_*), lidar/background_build.py (clean, attacks, episodes incl. NEW world-fixed persistent phantoms world_params). Tools WP3_S6_{build,lib,dev,probe,final,tables}.py; tests test_background.py (6), test_track.py (5); suite 422. Cache ../data_extra/cache_v3/WP3/S6 (3 MB of statistic tables; rebuild ~45 min with 4 procs).
- Chosen on validation: L2c = miss_w20, L2d = app_cc + fix_tot. Layers are parameter-free (thresholds pooled over 16 train+val clean drives = LODO by construction); results/WP3/S6/final.json.
- Test: L2c FA 2.1 %, PointDrop 87.3 %; L2d FA 0.2 %, near replace phantom (new surface in free space) 32.5 %, sensor-fixed near replace episodes 11/21; all small / far / world-fixed phantoms at FA (physics bound: world-fixed persistent phantom is caught at its first scan only, never later).
- Pitfalls: ring-group stats saturate (ties); small drives give 14-29 % LODO FA; noisy_or over 4 layers dilutes PointDrop (87 -> 7 %): S9 must choose max vs noisy_or on validation; attacked scans use the CLEAN previous scan (onset), episodes the attacked previous scan.

## S7 state (2026-10-24, REVIEW)
- New modules: lidar/learned.py (L3 object features + cov / iforest / AE normal models, track class from lidar.assoc), lidar/learned_l4.py (descriptor rows of the physical attack set: train_rows, eval_rows = S4 seeds, episode_rows; XGBoost fit_xgb, null_aucs, importance_table, feature_group), lidar/learned_eval.py (rank combiners max / noisy_or, evaluate_stack, LODO FA, paired bootstrap, episodes). Tools WP3_S7_*.py (build_l3, build_l4, l1train, dev_l3, dev_l4, dev_stack, oof, final, analysis, objects, cost, tables); tests test_learned.py, test_learned_analysis.py. Cache ../data_extra/cache_v3/WP3/S7 (0.23 GB: l3_* feature tables, l4_* descriptor rows, l1_* train L1 statistics, models/, final_frames.pkl = the frozen test score store).
- Reusable: S7 cache holds descriptor rows (429 cols) of the S4 evaluation attacks (val + test, 9 attacks) and episodes for ANY detector on the same attacked scans; final_frames.pkl holds per-scan raw scores of L1, L2a(int), L2c, L2d, L3, L4 (+variants) for ref / clean test / attacks / episodes.
- Results: reports/WP3_S7.md. L3 (AE on base features) adds nothing (FA drift: drive 0001 21.5 %). L4 (depth 8, 18 trees): PointDrop 90.8, IntensitySpoof 100, near replace 19.2 (generator-dependent), far / budget phantoms at FA; leave-one-type-out collapses. Max combiner at 1 % total FA dilutes PointDrop 87 -> 27.6 % (S9).
- Pitfalls: fit_xgb must remap labels when a class is missing; L1 statistics of the S4 clean tables exist only for val / test drives (train: tools/WP3_S7_l1train.py); rank-of-rank on a small reference (549 scans) is coarse.

## S5 state (2026-10-24, REVIEW)
- lidar/occlusion.py (sandwich / see-through returns per tile, L2bUnion, FullCalib), occlusion_build.py, occlusion_eval.py; tools WP3_S5_{build,dev,shrink,final,tables,runtime}.py; tests/lidar/test_occlusion.py. Cache ../data_extra/cache_v3/WP3/S5 (0.79 GB; tile tables, only chosen-variant columns for test / most files).
- Result: single-return calibrated phantoms 0.6-6.3 % (= FA to small gain, only through generator dropout holes), best-case attacker (fl_*) = FA, multi-return add near 69 % (impossible case, comparison), box cloud 18.8, FA test 0.46 %; episodes 3/21 replace near. Drives 0027 / 0013 have huge clean see-through counts (nested LODO FA 100 / 13 %).
- Extra attacks fl_* (every ray filled) and tile builders usable by S9: occlusion_build.drive_attacks / drive_episodes.

## S9 state (2026-10-24, REVIEW) = milestone M1-LiDAR (PARTIAL), report reports/M1_LiDAR.md
- New modules: lidar/combine.py (Stack: label-free max / noisy_or / split of ECDF ranks, tie-safe budget, lodo_fa, drive_bootstrap), lidar/domain.py (LidarDomain, LidarStream, IntensityModel = intensity half of ObjectModel, MotionEstimate passthrough of gps.lidar_odom), lidar/s9_build.py (S4-style L1 / tile tables of the world-fixed S6 episodes). Tools WP3_S9_{lib,build_epw,check_epw,dev,dryrun,final,analysis,tables,freeze,replay,accept,report}.py; tests test_combine.py (7), test_domain.py (5), test_s9_analysis.py (3). Cache ../data_extra/cache_v3/WP3/S9 (0.14 GB: world-fixed episode tables, dev / final score frames, ref_frame.pkl).
- Choices on validation (results/WP3/S9/dev.json): combiner max (noisy_or eliminated by worst-drive LODO FA 9.5 %), density part of L2a NOT kept (-1.2 points). Headline stack L1 + L2a(intensity) + L2c + L2d, thresholds from the out-of-fold clean reference of 16 drives (3124 scans) at 1 % TOTAL.
- Test (one run, results/WP3/S9/final.json, tables S9_tables.md): FA 1.18 % (worst drive 2.54 %), replace near 17.8, far / budget phantoms 0.8 (= FA), PointDrop 27.6, IntensitySpoof 51.6, episodes sensor-fixed near replace 11/21 (L2d), world-fixed first scan only, false-episode rate 6.2 %. Dilution: shared budget costs PointDrop 87 -> 28 (2 % total: 68 %). L1 does not earn its place on the single-return set (removing it raises PointDrop to 36 %).
- Reuse: ../data_extra/cache_v3/WP3/S9/final_frames_s9.pkl (test score frames of L1, L2a, L2aF, L2c, L2d, L2b, L4 incl. world-fixed episodes) and dev_frames.pkl (validation); tools/WP3_S9_analysis.analyse(frames, method, optional) is a pure function of frames.
- Frozen domain results/WP3/S9/frozen_lidar (9 MB); load with LidarDomain.load; stream().push(points, pose, t, sample_id) -> (combined Evidence, {layer: Evidence}); pose = planar (x, y, yaw) of the scan (KITTI: lidar.ego.poses from OXTS). Freeze check results/WP3/S9/freeze_check.json (replay from raw scans = stored scores).
- Pitfalls: S6 used 2 world-fixed episodes per kind on validation, 3 on test (my first validation build used 3: only the first kind has identical draws); *.pkl / *.npz are git-ignored (frozen files are force-added); the ObjectModel pickle is 110 MB because of the density tables, IntensityModel drops them (5 MB, identical intensity scores).
