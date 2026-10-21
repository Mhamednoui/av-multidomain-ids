# WP1 S8: domain combiner, full ablation, external tests -> milestone M1-GPS

Date: 2026-10-21    Worker: sonnet (WP1, high, T3)

## Goal of the step
Combine the default GPS stack (B2 + L1 + L2a + L2b + 6 instantaneous L2d), calibrate everything by nested LODO over the 16 train+val drives (15 with runs), run the full ablation, the external tests (UAV flight, AV-GPS sessions), freeze the deployable GPS domain output and write the milestone report. Milestone report (self-contained, numbers with intervals): `reports/M1_GPS.md`. Long tables: `results/WP1/S8_tables.md`.

## Acceptance rule (notes/WP1_gps.md "S8", written before any S8 result) and verdicts (results/WP1/S8_acceptance.json)
| criterion | value | verdict |
|---|---|---|
| G1 tests | 194 pass (9 new: tests/gps/test_stack.py, test_domain.py) | MET |
| G2 combined clean-run FA <= 1.5% on test and nested dev | test 1.83% [0.78, 2.76]; nested dev 1.24% | NOT MET on test |
| G3 Doppler spoof and meaconing >= 75% (not lowered) | 68.6% [51, 86] / 61.4% [29, 89] (zero-shot combiner) | NOT MET (pre-registered expectation) |
| G4 beats B2: mean run-level +10 points, no attack > 5 points worse, FA <= B2 + 0.5 | +16.2 points [+10, +22], worst attack 0, FA 1.83% vs 1.58% | MET |
| G5 combining helps: AUC >= best single - 0.005 and mean >= best single - 2 points | AUC 0.895 vs 0.865 (ekf_nis); mean 76.2 vs 74.5 (lidar_z_3 / cusum_dr); gain over cusum_dr +1.7 [-1, +4] not significant | MET (no significant gain over the best member) |
| G5 ablation expectation (no single drop >= 2 points) | max drop 1.2 points (dr_resid_10, ekf_nis, cusum_dr) | as expected |
| G6 shuffled-label control, 5 seeds, mean AUC <= 0.55 | 0.440 (max 0.519) | MET |
| G7 intervals (bootstrap over 7 drives and over runs) and delay distributions | S8_kitti.json deployed.bootstrap, summary.delays | MET |
| G8 UAV: alarm within 5 s of 118.0 s and pre-onset FA <= 2% | alarm 118.0003 s; pre-onset 3/118 = 2.54% (Wilson [0.9, 7.2]) | NOT MET (FA) |
| G9 AV-GPS (expected: nothing usable) | combined FA 17.5%, AUC 0.883 = 95th percentile of the permutation null; only the placeholder artefact separates | as pre-registered |
| G10 frozen GPSDomain reload reproduces scores to 1e-9 | max difference 0.0, 0 alarm disagreements on 11,074 rows | MET |
| G11 side by side with v2 | M1_GPS.md section 2, S8_tables.md section 8 | reported |
Slow drift 0.2-0.5 m/s within 30 s: untestable on KITTI (no run has a 30 s window); 3 of 14 runs flagged in the available window.

## What was done
- `gps/stack.py` (matrix-level LODO pieces: MatrixCombiner equal to common DomainCombiner, noisy_or_log, RunIndex), `gps/domain.py` (GPSDomain: 16 layers + combiner, save/load, GPS MotionEstimate), `gps/b2.py` (B2 inside gps/, copy of the S1 tool code), tests `tests/gps/test_stack.py` (5), `tests/gps/test_domain.py` (4); tools `WP1_S8_scores.py` (raw score matrix, cached), `_check.py`, `_lib.py`, `_dev.py` (nested LODO, dev rows only), `_test.py` (one test pass after a dry run on val rows), `_control.py` (5-seed shuffled labels), `_noise.py` (nested receiver noise model), `_freeze.py`, `_external.py`, `_tables.py`.
- Results: `results/WP1/S8_dev.json, S8_kitti.json, S8_control.json, S8_noise_nested.json, S8_external.json, S8_freeze.json, S8_acceptance.json, S8_tables.md`, frozen object `results/WP1/frozen_gps/` (1.9 MB). Cache `results/WP1/cache/s8_raw.pkl` (gitignored). Logs in `results/WP1/logs/S8_*`.
- Pipeline check: the new score matrix reproduces S4 dev summaries exactly (J, FA) and the S7 test harness numbers of B2, EKF NIS, cusum_ekf, cusum_dr, lidar_z_1 exactly (max difference 0.0).

## Ablation rows
Every layer alone, all, all-but-one, + L2e / cusum_lidar / L3 / L4: `S8_tables.md` sections 1, 4 (test and nested dev). Summary: no single layer is essential (max drop 1.2 points), the weak kinematic rules slightly dilute the sum, none of the optional layers adds (+0.2 to +1.0 point, within noise).

## Problems, surprises, open questions
- common `noisy_or` saturates at 1.0 (0 alarms): `reports/REQUEST_WP1_combiner_noisy_or.md` (request only; I used a rank-equivalent log form inside gps/).
- Deviation after the first dev pass (before any test number; logged in the notes): the deployed combiner is fitted without the Doppler / meaconing rows (RULES 5.7); the six-attack logistic is a side row (81.0% vs 76.2% mean, 89 / 70% on the two types).
- S4-S7 combiner halves were by run id, not by drive (selection only; S8 is by drive).
- UAV: the combination has 3 pre-onset alarms where EKF-CUSUM alone has 0 (post-hoc observation, not used to choose anything; a UAV subset of EKF NIS + EKF-CUSUM would reproduce v2).
- Question: accept the PARTIAL milestone as is (G2, G3, UAV FA, slow drift not met), or ask for a specific follow-up (for example prune the weak kinematic rules in the deployed stack, which the ablation suggests would raise the mean by about 1 point; not done because it would be a post-hoc choice on test)?

## Proposed next step
M1-GPS review. Then WP6 reads the frozen GPS domain output (`reports/M1_GPS.md` section 8) and the LiDAR / GPS MotionEstimates.
