# WP8 P1: paper analysis of saved v3 test scores

All numbers: **re-analysis of v3 test outputs (no refit)**. No model was fitted, no threshold chosen, no test data re-scored. Script: `tools/WP8_P1_curves.py` (resumable, one output set per domain). Outputs: `results/WP8/P1/`.

## Summary (read this first)
- Available per-sample saved test scores: GPS (row level, 7 KITTI test drives), LiDAR (scan level, 7 drives), CAN (only the raw S3 rule/skew columns, partial). Network, V2X, fusion/system: per-sample scores were never stored or lived in the caches deleted on 2026-10-25: listed in `results/WP8/P1/not_available.md`, not recomputed.
- GPS: the saved raw layer scores (`results/WP1/cache/s8_raw.pkl`) pushed through the frozen calibrators and noisy-or log (`results/WP1/frozen_gps`) reproduce `S8_kitti.json` exactly (row AUC 0.89527, row FA 1.198%, identical).
- LiDAR: `results/WP3/S9/test_scores.csv.gz`; FA equals `S9/final.json` (1.18%); per-attack AUC matches final.json to 6e-5.
- GPS (row level, all six attacks pooled): AUC 0.895 [0.823, 0.935] (bootstrap over 7 drives); detection 66.8 / 68.8 / 71.2 / 74.7% at FA 0.5 / 1 / 2 / 5%; operating point FA 1.20%, detection 69.2%.
- GPS seen by the combiner (drift, accel. drift, jump, freeze): AUC 0.906, det@1% 73.5%. Unseen (Doppler, meaconing): AUC 0.874 [0.760, 0.934], det@1% 59.5% [28, 74].
- LiDAR (9 scan-level attacks pooled, includes 3 comparator attacks): AUC 0.750 [0.722, 0.784]; det@1% 18.3%, det@5% 38.5%; operating point FA 1.18%, det 21.2%.
- LiDAR tamper (PointDrop + IntensitySpoof): AUC 0.944; det@1% 28.7%, det@5% 81.0%. PointDrop alone AUC 0.975 but det@1% only 5.9% (det@5% 94.3%): the stack score has its mass of ties/saturation near the 1% budget (v3 operating point detects 27.6%; the stored threshold sits where alarms are counted with ties, curve reading is strictly-above, see caveat 3).
- LiDAR physical phantoms (4): AUC 0.630; far and budget phantoms 0.53 to 0.61 (physics limit, as stated in v3); near replace 0.835.
- CAN (partial, raw S3 rule columns, not the final stack): ROAD best single column l1_period AUC 0.824, l1_bus_load 0.677; Car-Hacking l1_period AUC 0.996 (det@1% 92% at 2% FA). Final stack curves not available.
- Network: operating-point seen vs leave-one-attack-out table only (`net_seen_unseen.*`); no curve. V2X, fusion: nothing curve-able.
- Pre-registered operating point is marked (black star) on GPS and LiDAR curves.

## Caveats
1. Row/scan level, not run/episode level. The v3 headline numbers (76.2% run-level GPS detection at 1.83% clean-run FA) use a different unit; the two sets must not be mixed in a paper table. Both are reported with their unit.
2. "Detection at FA x%" reads the saved test curve: the threshold is the quantile of the test negatives. It is a descriptive reading, not an operating point v3 chose (v3's own choice is the starred point, set on validation / dev).
3. Ties: PointDrop and many CAN rule columns saturate (many identical scores). The detection reading uses "strictly above the threshold" so it is a conservative lower bound at the stated FA; the v3 alarm rule (score >= threshold) can sit at a different FA/detection pair, shown as the star.
4. Bootstrap = resample test groups (7 drives; for CAN, clean captures and attack captures within their kind), 1000 draws, seed 42. With 7 drives the intervals are wide; per-attack CIs for LiDAR rest on the same 7 drives.
5. GPS negatives = all label-0 rows (clean runs plus pre-onset rows), as in v3's row-level FA.
6. LiDAR episodes (ep_*, epW_*) are in the file but not pooled (v3 scores them per episode, R4).

## Files
Per domain `<dom>_table.{md,csv}` (AUC, CI, det at 0.5/1/2/5% FA with CI, operating point), `<dom>_curve_points.csv`, `<dom>_roc.{png,pdf}` (linear + log-FA panels, greyscale-safe linestyles); `can_roc_road`, `can_roc_carhacking`; `net_seen_unseen.{md,csv}`; `summary.md`; `not_available.md`; `*_summary.json` (sources, checks against saved v3 numbers).

## Tables (copied from results/WP8/P1/summary.md and *_table.md)
See `results/WP8/P1/gps_table.md`, `lidar_table.md`, `can_table.md`, `net_seen_unseen.md`.

## Not available without a re-run
CAN final stack (L3c, L3d), network, V2X, fusion/system per-sample scores; see `results/WP8/P1/not_available.md`.

## Problems
None blocking. Fusion/system and V2X/network ROC cannot be drawn; if the paper needs them, a new scoring pass (new test exposure) must be approved.
