# WP3 S4: L2a density / intensity versus range

Date: 2026-10-24    Worker: sonnet (medium, T2)

## Goal of the step
Per-object density-vs-range and intensity-vs-range check (HDL-64E angular resolution x calibrated return probability), scored as improbability, on the S3 object table; evaluation attacks = single-return phantoms + PointDrop + IntensitySpoof (old multi-return add and box cloud: v2-comparison rows only, physically impossible).

## Acceptance rule (notes/WP3_lidar.md, "S4 ... ACCEPTANCE RULE", written before any result)
A1 test FA <= 2.5 %; A2 IntensitySpoof >= 50 %, PointDrop >= 30 %, box cloud >= 50 %; A3 calibrated replace/budget phantoms <= FA + 10 points (physics bound; higher = artefact); A4 object level reported; A5 harness combination not > 3 points below best single layer; A6 episodes reported with false-episode rate; A7 tests, cache <= 3 GB.

## What was done
- lidar/density.py (ObjectModel: conditional empirical CDFs of clean units per range bin x slots bin, intensity per range x point-count bin; L2aStat/L2aUnion Layers, layer "L2a"), lidar/s4_build.py (attack tables, tiles, episodes), lidar/s4_eval.py, lidar/segment.py (+ optional tight near link, S3 default unchanged), tools/WP3_S4_{variants,build,dev,final,tables}.py, tests/lidar/test_density.py (4), test_tiles.py (3). Suite 406/406. Cache 1.3 GB.
- Choices on validation (results/WP3/S4/variants.json, dev.json): segmentation variant (best near gain +9.6 < 10 points: S3 kept); unit = TILE (cluster x 2 deg azimuth x 8 lasers x 2 m range cell) because the injected object is a merged giant cluster in most near cases (cluster-level L2a: IntensitySpoof 17-49 %, others at FA; dev rounds in notes); tail extension and point-count conditioning; count statistics (tiles with p < 1 %) added to the union; tile nmin 8; LODO primary (worst drive FA 13.6 % > 3 %).
- Test: one verdict run (after a crash in reporting code before any output; fixed, same pipeline). 510 attacked scans per attack (every 3rd scan, 7 test drives), 21 episodes per kind.

## Results (results/WP3/S4/final.json, S4_tables.md; primary = LODO threshold)
Clean test FA 1.63 % (per drive 0 / 0 / 1.9 / 2.8 / 0 / 1.0 / 1.9). Val-only threshold: FA 20.4 % (per drive 1.9-64 %; count of dense tiles drifts between drives) - not usable.
| attack (scan level, %) | L2a LODO |
|---|---|
| phantom replace near / far | 1.0 / 1.2 |
| phantom budget near / far | 1.2 / 1.2 |
| PointDrop | 1.2 |
| IntensitySpoof | 56.5 |
| box cloud (single-return, comparison) | 3.9 |
| multi-return add near / far (comparison, impossible) | 29.2 / 4.3 |
Tile level: calibrated phantoms 0.0 % of phantom tiles caught; box cloud 0.1 %; multi-return add near 0.5 %. Episodes (LODO): replace near 0/21, far 2/21, budget near 2/21, far 5/21 within 3 s; false-episode rate on clean test windows 16.7 % (48 windows): at chance. Scoring 2 ms/scan (segmentation, 0.7 s, dominates).
Harness (val-only L2a, 20 % FA, as pre-declared): L1 alone FA 1.63 %, detection IntensitySpoof 1.4, box cloud 16.1, multi-return far 62.5; L1 + L2a_int (all_but_L2a_dens) FA 2.61 %, IntensitySpoof 62.5, box cloud 16.9; adding the density part only adds false alarms (FA 11-21 %). See results/WP3/S4/harness_*.md.
Acceptance: A1 MET (1.63 %); A2 PARTLY (IntensitySpoof 56.5 MET; PointDrop 1.2 and box cloud 3.9 NOT MET); A3 MET (phantoms 1.0-1.2 %, density-matched, physics bound as stated); A4 reported; A5 NOT MET for the harness as run (combination loses 0 to best on IntensitySpoof but carries the density layer's 20 % FA; the pre-declared val-only calibration was the flaw); A6 reported, chance level; A7 MET.
WP-file targets (50-400 added points >= 60 %, near sparse > 50 %): NOT MET, as predicted (physics bound).

## Ablation row
L1 union: scan detection of calibrated phantoms 1-3 %; L2a LODO: 1.0-1.2 %. Neither sees a density-matched single-return phantom. L2a adds IntensitySpoof only (L1 1.4 % -> 56.5 %).

## Problems, surprises, open questions
- Cluster-level objects are useless for near phantoms (merged giant clusters, 1k-25k points); tiles fix the unit but not the physics.
- PointDrop invisible: removal makes tiles fall below the validity threshold instead of looking sparse; the removed returns are what S6 (background model per ring/azimuth) must catch.
- The count statistics drift between drives (val-only FA 20 %): the LODO threshold fixes it, but I did not re-run the harness with the LODO layer (test already used once).
- Mixed validation size (3 drives, 552 scans) makes 1 % thresholds noisy; the nmin choice rests on IntensitySpoof alone.

## Proposed next step
S5 free space / occlusion per object (CARLO) and S6 background model for removal; L2a kept as a small IntensitySpoof/crude-spoof layer (union with LODO threshold).
