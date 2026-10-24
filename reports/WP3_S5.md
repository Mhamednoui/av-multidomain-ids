# WP3 S5: L2b free space / occlusion per object

Date: 2026-10-24    Worker: sonnet (medium, T2)

## Goal of the step
Per object / tile, test whether rays through its silhouette are consistent with a solid object (CARLO, Sun et al. 2020): far returns between returns of one object = not solid.

## Acceptance rule (notes/WP3_lidar.md, "S5 ACCEPTANCE RULE", written before any result)
B1 clean test FA <= 2.5 %; B2 best-case attacker phantoms (fl_*), PointDrop, IntensitySpoof <= FA + 10 points, calibrated phantoms and box cloud reported without threshold; B3 WP targets (50-400 added points >= 60 %, near sparse > 50 %) reported; B4 tile level reported; B5 harness L1 + L2a(intensity) + L2b loses <= 3 points to the best single layer on any attack; B6 episodes within 3 s + false-episode rate; B7 tests, extra cache <= 2 GB, cost.

## What was done
- lidar/occlusion.py (sandwich search: a far return between two returns of one cluster on the same laser (row) or the same azimuth (column), tile counts, scan statistics tot / maxf / cnt / maxn, L2bUnion layer, FullCalib = best-case attacker), lidar/occlusion_build.py, lidar/occlusion_eval.py, tools/WP3_S5_{build,dev,shrink,final,tables,runtime}.py, tests/lidar/test_occlusion.py (5). Suite 454/454.
- Attacks: the nine S4 attacks (same seeds, identical scans) + four best-case attacker phantoms fl_{replace,budget}_{near,far} (a return on every ray of the silhouette, no dropout). Episodes: S4 kinds + fl replace near / far (21 each).
- Variant chosen on validation (3 drives) by the rule: margin 0.5 m, gap 0.8 deg, loose same-surface test. Threshold pooled over 16 train+val clean drives (tie-safe 1 %). Test used once (final.json); a dry run of the same code on validation drives preceded it.
- Extra cache 0.79 GB (limit 2 GB).

## Results (results/WP3/S5/final.json, S5_tables.md)
Clean test FA 0.46 % (per drive 0 / 0 / 0.7 / 1.0 / 0 / 0 / 0). Nested held-out-drive FA on train+val: 14 of 16 drives <= 2.4 %, 0013 13.2 %, 0027 100 % (a drive with so much see-through structure that its own threshold would be far higher): the threshold works for the test drives but the layer is not drive-robust in general.
| attack (scan level, %) | L2b |
|---|---|
| calibrated replace near / far | 6.3 / 0.8 |
| calibrated budget near / far | 1.0 / 0.6 |
| best-case attacker (fl_*) replace near / far, budget near / far | 0.6 / 0.6 / 0.6 / 0.6 |
| PointDrop / IntensitySpoof | 0.6 / 0.6 |
| box cloud (single-return, comparison) | 18.8 |
| multi-return add near / far (comparison, physically impossible on a single-return sensor) | 69.4 / 28.4 |
Tile level: phantom tiles caught 0.02 % (replace near), 0.00-0.03 % (others), box cloud 0.13 %, multi-return add near 22.4 %.
Episodes (3 s): replace near 3/21, all other calibrated and fl kinds 0/21; false-episode rate on clean test windows 0 / 48.
Harness (system budget 1 %): all three layers FA 1.37 %: IntensitySpoof 51.4, PointDrop 1.6, box cloud 24.1, multi-return far / near 67.6 / 65.9, calibrated phantoms 2.0-2.9 (= FA). Best single layer per attack: L2a_int 51.0 (IntensitySpoof), L1 62.5 (mr far), L2b 68.4 (mr near), L2b 16.9 (box cloud), L2b 4.3 (replace near).
Cost: tile table 0.39 s/scan (ring assignment included) on top of segmentation 0.54 s (loaded machine).
Acceptance: B1 MET; B2 MET (fl_* 0.6 %, PointDrop 0.6, IntensitySpoof 0.6); B3 NOT MET (budget 0.6-1.0 %, near 1.0 %; as predicted); B4 reported; B5 MET (worst loss 2.5 points: multi-return near 65.9 vs 68.4); B6 reported (3/21 replace near, else 0); B7 MET.

## Physics reasoning tested on data
Prediction: with single-return physics a complete phantom replaces the real returns behind it, so nothing is visible through it. Confirmed: the best-case phantoms (fl_*) are invisible (0.6 % = FA, validation 0.5 %). The calibrated generator drops rays (Beta dropout fitted on real objects); a dropped ray keeps its real, farther return, so those phantoms show see-through returns: this gives 6.3 % (near replace; 20 % on validation) and ~1 % for budget phantoms and far ones. That small gain depends on the generator letting rays fall out; an attacker who fills every ray of its silhouette removes it. The layer fires strongly only on the physically impossible multi-return phantom (69 % near), which is the case in the original CARLO paper (a real return behind the phantom). Budget-limited phantoms are not caught: the real scene outside the injected angular extent is not "inside the silhouette". Missing ground shadow was not implemented as a separate statistic (a ray-exact phantom keeps a consistent shadow).

## Ablation row
L2b alone: calibrated phantoms 0.4-4.3 %, box cloud 16.9, multi-return near 68.4. Adds to L1 only for the box cloud (24.1 vs 16.1) and the impossible multi-return add.

## Problems, surprises, open questions
- Clean scans contain thousands of see-through returns (foliage, fences, windows): the layer only works through a high threshold, and the drive spread is large (0027, 0013).
- Laser assignment is ambiguous for nearby lasers: the first loose design (gap 1 deg, column span 4) was far too noisy; tightened on a smoke test before any attack table (documented).
- The test-set attack tables were built after the validation choice, before analysis; no test number influenced any choice.
- Question for review: keep L2b in S9 only as a comparison / impossible-add layer (adds FA budget cost near zero but no real attack gain)?

## Proposed next step
S9 combiner: L2b enters as an optional layer; with L1, L2a(intensity), S6 background/tracking.
