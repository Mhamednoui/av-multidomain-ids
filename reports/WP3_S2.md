# WP3 S2: generator density calibration + L1 sensor geometry

Date: 2026-10-22    Worker: sonnet (medium, T2)

## Goal of the step
Part A (supervisor fix): calibrate the ray-cast phantom generator to real KITTI object point counts / intensity, regenerate attacks, re-run the v2 baseline, old vs calibrated. Part B: L1 sensor geometry layers (64 rings, range/intensity limits, one return per direction), one verdict run on test.

## Acceptance rule (notes/WP3_lidar.md, "ACCEPTANCE RULE S2", written before any result)
A1-A5 (calibration fitted on train, chosen on val; KS D <= 0.20 per range bin for q and intensity; count ratio 0.8-1.25; 30 m count within 20 %; unit tests; old vs calibrated v2 baseline). B1 test FA <= 2.0 %; B2 predictions (box cloud >= 90 %; add caught by duplicates; replace/budget <= FA+3; PointDrop/IntensitySpoof <= FA+5); B3 harness ablation; B4 tests, cache <= 3 GB.

## What was done
- lidar/geometry.py (ring table from train, common mode, 5 L1 statistics), objects.py, phantom.py, calibration.py, l1.py, l1_build.py; tools/WP3_S2_*.py; tests/lidar/test_geometry.py (14 tests; suite 275/275).
- No tracklets exist: real objects = 6453 (train) / 2176 (val) car-like clusters (ground removal + connected components, documented limits in lidar/objects.py).
- Generator fix: S1 shortened rays from the sensor origin, which leaves the laser's ring by up to ~0.1 m (old far replace: ring-sector alarm 11 % vs 2 % calibrated). New generator uses the laser ray, keeps the real residual, Beta return probability (p 0.59-0.73, kappa 7.2), intensity from real objects of the same range band.
- Cache 0.25 GB. Test touched once (results/WP3/S2/final.json); tables results/WP3/S2/tables.md, L1_ablation.md.

## Results (all from results/WP3/S2/*.json)
Part A (VAL, calib_report.json):
| item | real | S1 phantom | calibrated |
|---|---|---|---|
| median points 30-35 m | 53 | 113 (x2.1) | 80 (x1.5) |
| KS D occupancy q, worst bin | - | 0.76 | 0.22 |
| KS D intensity, worst bin | - | 0.38 | 0.16 |
| count ratio at equal angular size | 1 | 1.3-3.7 | 0.8-1.3 in 16/19 strata |
A2 PARTLY MET: D_int <= 0.20 yes; D_q 0.216 in the 6-12 m bin (limit 0.20) just missed; unconditional count ratio 1.28-1.75 NOT MET (real clusters are partial, smaller views; at equal size it matches). A3 NOT MET (+50 % vs real 53 at 30 m). The "~270 real at 30 m" of v2 is not reproduced by clusters (53); it was probably a complete-car figure.
A5 (v2 model, test, threshold val 1 %, onset): add near 75.3 -> 61.9, add far 20.5 -> 13.0, budget_add near 5.4 -> 6.5, far 6.9 -> 5.2; replace, budget = FA. Densest cases lose 10-15 points: the old numbers were inflated by density.

Part B (TEST, final.json), L1 union alarm %: 
| attack | v2 alone | L1 union | v2 OR L1 |
|---|---|---|---|
| FA clean test | 0.8 | 1.6 | 2.4 |
| PointDrop / IntensitySpoof | 82.0 / 99.9 | 1.4 / 1.6 | 81.5 / 99.9 |
| box cloud | 46.3 | 46.9 | 65.7 |
| calibrated add near / far | 61.6 / 12.8 | 1.7 / 60.2 | 61.2 / 70.0 |
| calibrated budget_add near / far | 6.4 / 5.1 | 1.7 / 58.3 | 7.8 / 62.3 |
| calibrated replace, budget (near, far) | 0.9-1.0 | 1.7-2.4 | 2.5-3.1 |
Per-drive FA of L1 union: 1.9, 5.9, 0, 2.8, 0, 0, 0.7 % (0001 0005 0028 0039 0052 0079 0095). Ablation (harness, 8 configs) in L1_ablation.md: L1 alone AUC 0.59; v2 0.74; all 0.77 at FA 2.36 %.
Acceptance B1 MET (1.57 % <= 2.0 %). B2: replace/budget/PointDrop/IntensitySpoof MET; box cloud >= 90 % NOT MET (47 %); add caught only far.

## Physics statement
A phantom on its laser ring that replaces the real return is a legal single-return scan: L1 cannot see it (1.7-2.4 % = FA), as expected. L1 sees (a) off-ring points, but only about 40 % of a random box cloud because ring spacing at 20-40 m (12-20 cm) is close to the 6 cm tolerance; (b) a phantom ADDED beside a surviving real return (duplicate direction), but only where the laser is unambiguous (>= ~20 m); near duplicates are invisible (neighbouring lasers fire at the same azimuth). The ADD result is therefore an artefact of the multi-return assumption, not a general detector.

## Ablation row(s)
L1 union: alone 16.5 % mean detection at FA 1.6 %; adds box cloud +19 pts and add/budget_add far +50 to v2; adds nothing on PD/IS/near/replace.

## Problems, surprises, open questions
- Count calibration is incomplete: unconditional phantoms remain ~1.5x denser than real car-like clusters because a phantom is a full box. Question: accept (size-matched agreement) or add a partial-view/occlusion size distribution? Real-cluster table is unlabelled (bushes/fragments pass the shape filter); KITTI tracklets (D20) would fix it.
- ring_sector rule fires on drives 0005/0039 (FA 5.9/2.8 %): per-drive FA spread above budget; no retune (test already used).
- Duplicate rule needed a design fix on clean train/val (near-range ambiguity) before any attack result.
- v2 model/threshold on test was already exposed in S1; L1 is a first exposure.

## Proposed next step
S3 object segmentation (reuse lidar/objects.py) then S4 density-vs-range per object using the real-cluster table as normal reference.
