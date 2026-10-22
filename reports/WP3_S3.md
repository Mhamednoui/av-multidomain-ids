# WP3 S3: single-return generator fix (S2b) + object segmentation

Date: 2026-10-22    Worker: sonnet (medium, T2)

## Goal of the step
S2b: make the "add" phantom physically consistent for a single-return HDL-64E (the injected return REPLACES the real return behind it) and re-score L1 and v2 on VALIDATION. S3: ground removal, clustering and an object table per scan; sanity numbers on clean data; how phantoms appear. No detection verdict.

## Acceptance rule (notes/WP3_lidar.md, "S3 ... ACCEPTANCE RULE", written before any result)
F1 physics test (max one return per beam, every attack); F2 validation-only old-vs-fixed re-score with predictions (L1 far-add falls to <= FA+5; box cloud L1 within 5 points; v2 add within 10 points). S3: (a) match rate 10-30 m >= 60 % on val, (b) median centroid residual <= 0.5 m, (c) oversize clusters <= 5 %, (d) car-like count within +-25 % of S2, (e) >= 70 % of phantoms appear as ONE object, runtime <= 1 s/scan, tests, cache <= 3 GB.

## What was done
- lidar/singlereturn.py (nearest return per beam = laser + azimuth within 0.04 deg; injected points replace the real returns behind them, or are not reported if a nearer return exists), lidar/phantom.py (`single_return=True` default: add == replace, budget_add == budget), lidar/sr_build.py, tools/WP3_S2b_{build,eval}.py, tests/lidar/test_singlereturn.py (8 tests). Old multi-return behaviour kept behind `single_return=False` (calibration and old tests).
- lidar/ego.py (OXTS planar ego-motion), lidar/segment.py, lidar/assoc.py, tools/WP3_S3_{choose,build,stats,phantoms,runtime,tables}.py, tests/lidar/test_segment.py (6 tests). Object tables of all 4673 clean scans in ../data_extra/cache_v3/WP3/S3 (cache total 0.49 GB).
- No test attack table built, no test scoring of L1 or v2 (S2b). S3 tables were computed on test scans for sanity numbers only; no choice used them.

## Results S2b (VALIDATION only; results/WP3/S2b/val_old_vs_fixed.{json,md})
Detection in %, v2 threshold = val clean 1 % (FA check: v2 1.09 %, L1 union 0.91 %), onset timing.

| attack | v2 old | v2 fixed | L1 union old | L1 union fixed |
|---|---|---|---|---|
| calibrated add far | 21.1 | 1.1 | 60.0 | 1.5 |
| calibrated add near | 86.2 | 8.7 | 1.1 | 1.1 |
| calibrated budget_add far / near | 13.1 / 15.3 | 1.1 / 1.5 | 58.9 / 1.1 | 1.5 / 1.1 |
| calibrated replace, budget | 1.1-6.9 | unchanged | 1.1-1.8 | unchanged |
| box cloud | 65.1 | 25.7 | 45.6 | 21.0 |
| S1 generator add far (approximate fix) | 33.8 | 18.2 | 57.8 | 25.8 |

Far-add detection by L1 (60 %) collapses to the false-alarm level (1.5 %): it WAS an artefact of the multi-return assumption, as the supervisor suspected. The same holds for v2 on add: near add 86 % -> 8.7 %; the old numbers were detecting the real return kept behind the phantom. Predictions: L1 far-add <= FA+5 MET; box cloud L1 within 5 points NOT MET (45.6 -> 21.0); v2 add change < 10 points NOT MET (near add -77 points). Both misses go in the direction "the old attack was easier than physics allows" (real returns behind 150-1500 injected points are removed, injected points behind nearer real returns are not reported).
Residual: the S1 origin-ray generator after the fix still shows 18-26 % because its off-ring points fall into neighbouring-laser beams by the nearest-ring rule (not exactly physical); only the calibrated generator (exact rays) is used from now on.
F1 MET (tests: calibrated modes, S1 modes, box cloud, v2 attacks: no beam with two returns above the clean scan; a multi-return control does show conflicts).
Consequence: add == replace is a legal single-return scan; duplicate returns cannot detect it. Only density, geometry and free-space checks (S4-S6) can.

## Results S3 (results/WP3/S3/sanity.json, S3_tables.md, choice.json, phantom_appearance.json)
Chosen on val: ground = local grid, h0 = 0.30 m (ground fraction 0.42 below 40 m, flat-wide leakage 0.8 %; lower h0 or RANSAC variants fail the leakage or fraction rule or give fewer car-like clusters); clustering e0 = 0.4 m, e1 = 0 (a range-growing radius did not help: match rate 0.57-0.64 for all 9 settings, oversize rises from 1.6 % to 14 %).

| item | rule | measured (val unless noted) | verdict |
|---|---|---|---|
| (a) match rate 1 m, 10-20 / 20-30 m | >= 60 % | 60.4 / 63.8 % (train 65.8 / 68.6, test 59.3 / 61.9) | MET (borderline) |
| (b) median centroid residual | <= 0.5 m | 0.13-0.19 m (p90 0.52-0.65) | MET |
| (c) oversize clusters (> 8 m) | <= 5 % | val 1.6 %, train 2.7 %, test 2.1 % | MET |
| (d) car-like count vs S2 | within 25 % | ratio 1.09 (12.9 vs 11.9 per scan); per scan within 25 %: 63 % | MET (mean) |
| (e) phantom = ONE object | >= 70 % | ray add far 62 %, near 43 %; budget_add far 60 %, near 47 %; box cloud 19-32 % | NOT MET |
| runtime | <= 1 s | single process 0.68 s median (p90 0.92); 1.1-1.7 s inside the 4-process build on the shared machine | MET |

Objects per scan: 290 (train) / 380 (val) / 190 (test) with min 5 points, mostly small (median 10-35 points, 0.6-0.9 m: vegetation, poles, fragments); car-like 8-13 per scan. Median points per object fall with range from 35 to 9; count ratio of matched objects 1.00 (IQR 0.75-1.30).
Phantoms: 85-97 % of phantom points land in some object. The phantom is one object in 62 % (far add) but 43 % (near add): a near phantom (5-15 m, ~1300 points) touches ground-level structure within 0.4 m and merges (median merged object 9.8 m long), and the centroid of the visible faces can be 2 m from the box centre. Pure phantom objects (>= 80 % phantom points): 49 % far add, 26 % near add.

## Ablation row
No detector in S3 (data step).

## Problems, surprises, open questions
- (e) NOT MET. For S4/S5: split merged clusters (height layering / box fit) or measure density on the phantom's angular footprint instead of the Euclidean cluster.
- The cluster choice by match rate is weakly discriminating (all settings 57-64 %) and favours fragments (e1 = 0): stability alone cannot tell merging from fragmentation.
- Match rate counts only static-world matches (oncoming cars fail the 1 m gate): a lower bound.
- Question: accept add == replace as the new evaluation attack set (the separate "add" rows no longer exist)?
- L1 was not re-tested on test (second exposure reserved for S9).

## Proposed next step
S4 density vs range per object on the object table; handle merged near objects first (e).
