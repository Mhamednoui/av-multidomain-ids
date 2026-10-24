# WP3 S9: combiner + ablation + sequence evaluation + frozen domain (M1-LiDAR)

Date: 2026-10-25    Worker: sonnet (high, T3)

The full milestone report is `reports/M1_LiDAR.md` (self-contained). This file is the step summary.

## Goal of the step
Combine the physics layers label-free, ablate, evaluate persistent episodes, freeze the deployable LiDAR domain, close M1-LiDAR.

## Acceptance rule (notes/WP3_lidar.md, "S9 design and ACCEPTANCE RULE", written before any S9 result)
R1 FA <= 2.5 % (worst drive <= 5 %); R2 PointDrop >= 30 %, IntensitySpoof >= 50 % at 1 % total; R3 far / budget phantoms <= FA + 10; R4 false-episode rate <= 10 % and sensor-fixed near replace >= 50 %; R5 every layer earns its place; R6 WP targets; R7 freeze reproduces test scores; R8 tests, cache, cost. Validation rules V1 (combiner) and V2 (density part).

## What was done
lidar/combine.py, lidar/domain.py, lidar/s9_build.py; tools/WP3_S9_*.py; tests test_combine / test_domain / test_s9_analysis; results/WP3/S9/ (dev.json, final.json, S9_tables.md, acceptance.json, freeze_check.json, frozen_lidar/, fixtures). Score frames of S7 re-used (recomputed layers identical, max diff 0.0); world-fixed episode tables rebuilt for L1 / L2a (n_inj equal to S6 on 2520 / 2520 test scans).

## Results (results/WP3/S9/acceptance.json, final.json)
Validation: combiner max, density part not kept. Test (one run, 7th exposure): FA 1.18 % (worst drive 2.54 %); replace near 17.8, far / budget phantoms 0.8 (= FA), PointDrop 27.6, IntensitySpoof 51.6; sensor-fixed near replace 11/21, false-episode rate 6.2 %; freeze check exact (max diff 1.1e-16, 0 alarm differences on 2381 scans).
Acceptance: R1 MET, R2 NOT MET (PointDrop 27.6 < 30, predicted), R3 MET, R4 MET (11/21 marginal), R5 NOT MET (L1 does not earn its place, predicted), R6 NOT MET (physics bound, predicted), R7 MET, R8 MET (469 tests, cache 0.14 GB).

## Ablation row(s)
Full ablation in reports/M1_LiDAR.md section 3 and results/WP3/S9/S9_tables.md.

## Problems, surprises, open questions
- The shared 1 % budget dilutes strong layers (PointDrop 87 -> 28, 68 % at 2 % total). Question for the supervisor: accept a 2 % LiDAR budget at system level, or keep 1 %?
- L1 earns nothing on the single-return set and costs budget (removing it: PointDrop 36 %). Kept by decision; consider moving it out of the budget-shared stack.
- Scoring 1.8 s per scan (segmentation): not real time.
- S6 used 2 world-fixed episodes per kind on validation (3 on test); noted.

## Proposed next step
WP6 S5b and WP7 S2 use the frozen domain (interface in M1_LiDAR.md section 9).
