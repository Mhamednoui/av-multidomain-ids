# WP3 S6: L2c background model (removal) and L2d ego-compensated tracking

Date: 2026-10-24    Worker: sonnet (medium, T2); S5 ran in parallel in separate files

## Goal of the step
Background model per ring x azimuth with OXTS ego-motion for removal attacks (L2c); tracking of surfaces across scans with ego-motion compensation to catch sensor-fixed and appearing / vanishing phantoms (L2d).

## Acceptance rule (notes/WP3_lidar.md, "S6 design and ACCEPTANCE RULE", written before any validation or test result)
A1 test FA of each layer <= 2.5 %; A2 PointDrop >= 30 %; A3 L2c on phantoms / IntensitySpoof within FA + 10, L2d predicted to see large near replace phantoms (>= 30 %) and nothing far / budget; A4 sensor-fixed persistent episodes >= 50 % within 3 s when the car moves, world-fixed reported (predicted: first scan only); A5 false-episode rate <= 10 %; A6 harness: full combination not > 3 points below best single layer, FA <= 3 %; A7 tests, cache <= 2 GB.

## What was done
- lidar/background.py (L2c: Img, moved, miss_stats, StatUnion), lidar/track.py (L2d), lidar/background_build.py, tools/WP3_S6_{build,lib,dev,probe,final,tables}.py, tests test_background.py (6) + test_track.py (5). Suite 422/422. Cache 3 MB.
- Method. Previous scan moved into the current frame (planar OXTS), binned 64 elevation rings x 1 deg. L2c: observed / expected returns in 20 deg windows, miss = 1 - min ratio / median ratio (removal makes returns missing where the static background expects them; scored directly, not through tile validity). L2d: non-ground cells explained as static (prediction within 0.3 m), sensor-fixed (same range as the UNmoved previous image, prediction disagrees: follows the car), new (nearer than anything the compensated previous scan showed along the ray, not explained by a nearer neighbour = no occluder to emerge from), gone.
- Attacks: the S4 attack set (same seeds), attacked scan vs clean previous scan (onset); persistent episodes S4 sensor-fixed plus NEW world-fixed ones (box moved with the ego-motion = parked-car-like persistent phantom), previous scan = attacked previous scan.
- Validation choices (results/WP3/S6/dev_round1.*, dev.*): L2c = miss_w20 (PointDrop 91 % val); ring-group variants saturate (ties) and were dropped; L2d = app_cc + fix_tot after fixing my selection objective to include sustained episode steps (before any test scoring). Thresholds: pooled clean train+val (16 drives), 1 %, tie-safe; statistics have no learned parameters, so pooling is out of fold; leave-one-drive-out FA reported.
- Test touched once (final.json).

## Results (results/WP3/S6/final.json; tables results/WP3/S6/S6_tables.md)
Scan level (onset), test %, FA = clean test scans:
| layer | FA | worst drive | LODO FA mean / max | PointDrop | IntensitySpoof | replace near / far | budget near / far | box cloud | multi-return add near / far |
|---|---|---|---|---|---|---|---|---|---|
| L2c miss_w20 | 2.1 | 6.1 (0039) | 1.8 / 14.3 (0048, 21 scans) | 87.3 | 1.8 | 1.8 / 1.8 | 1.8 / 1.8 | 1.8 | 1.8 / 1.8 |
| L2d app_cc + fix_tot | 0.2 | 0.7 | 2.4 / 28.7 (0013) | 0.2 | 0.2 | 32.5 / 0.2 | 0.2 / 0.2 | 2.5 | 34.5 / 0.2 |
Persistent episodes (21 per kind, 3 s rule, v2 rolling log-odds, threshold = 99th percentile of clean windows of train+val): false-episode rate L2c 10.4 %, L2d 2.1 %.
| kind | L2c detected / median delay | L2d detected / median delay | L2d onset scan % | L2d sustained scan % |
|---|---|---|---|---|
| sensor-fixed replace near | 4 / 0.10 s | 11 / 0.10 s (8 of 14 with ego moving) | 38.1 | 31.0 |
| sensor-fixed replace far | 2 | 0 | 0.0 | 0.2 |
| sensor-fixed budget near / far | 2 / 0 | 0 / 0 | 0.0 | 0.0 |
| world-fixed replace near | 1 | 10 / 0.10 s | 33.3 | 0.0 |
| world-fixed replace far, budget near / far | 1 / 1 / 1 | 0 / 0 / 0 | 0 | 0.0-0.2 |
Harness ablation on top of L1 + L2a(intensity) (noisy_or, 1 % on the 3 validation drives): L1 + L2a_int: FA 1.8 %, IntensitySpoof 52.5, PointDrop 1.4, box cloud 14.5. Adding L2c and L2d: FA 0.8 %, AUC 0.60 -> 0.75, but PointDrop only 6.9 (L2c alone 87.5) and IntensitySpoof 28.6 (L2a_int alone 51): the label-free noisy_or of four layers dilutes a strong single layer; all_but_L2d near replace 1.2, with L2d 9.2 (L2d alone 29.2). Full table: S6_tables.md.
Scoring cost 112 ms per scan (image building dominates).

Acceptance: A1 MET (2.1 / 0.2 %); A2 MET (87.3 %); A3 MET (L2c at FA; L2d near replace 32.5 %, far / budget at FA); A4 NOT MET (only near replace sensor-fixed reaches 57 % of moving-ego episodes; other kinds 0; world-fixed sustained steps at FA as predicted); A5 L2c 10.4 % NOT MET (marginal), L2d MET; A6 NOT MET (combination loses 80 points on PointDrop vs L2c alone); A7 MET.

## Ablation row(s)
L2c alone = removal detector (PointDrop 87.3 %, nothing else). L2d alone = near large phantom appearance / sensor-fixed near phantom only. On top of L1 + L2a_int the layers add PointDrop and near replace to the single-layer view but the pre-declared combiner hides them.

## Problems, surprises, open questions
- PointDrop is the one clear win (4 % -> 87 %, vs 1.2 % for L2a). Caveat: v2 PointDrop removes 50-100 % of points in a 10-60 deg sector, which is easy; a smaller, thinner removal would be harder.
- Physics, as predicted: a persistent phantom that is placed in the world (parked-car-like, or any plausible trajectory) is a normal static / moving surface for the tracker; it is only visible in its first scan as an appearance, and only when large and near. Tracking alone cannot catch it; far or budget-limited phantoms are at FA even at the first scan. The sensor-fixed phantom is caught only when dense (near replace); sparse ones give too few fixed cells against clean noise.
- The appearance statistic is a "new surface in free space" test: real cars appearing from side streets are the clean false alarms; the 1 % threshold absorbs them. Near replace phantoms are denser than reality (documented S2 gap), so 32 % may be optimistic.
- LODO FA has drive-level shifts (0048: 21 scans; 0013); worst test drive 0039 6.1 % for L2c.
- Harness combiner: noisy_or dilutes. Question for S9: choose max vs noisy_or on validation (rule of 2026-10-22), not re-tested here (test already used).
- Shared notes file notes/WP3_lidar.md holds S5 and S6 text interleaved; committed whole.

## Proposed next step
S7 (L3 normal-only statistics, L4) then S9 combiner with LODO recalibration of every layer; keep L2c (miss_w20) and L2d (app_cc) as cheap parameter-free layers, drop fix_tot unless S9 validation keeps it.
