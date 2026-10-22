# WP2 S7: combined CAN stack, ablation, fresh checks, cross-vehicle tests (closes M1-CAN)

Date: 2026-10-22    Worker: sonnet (high)

## Summary
Verdict: **PARTIAL / items 1, 2, 4 MET, item 3 (false alarms) NOT MET.** Full milestone report: `reports/M1_CAN.md`. Rule written before any S7 result: notes/WP2_can.md "S7 start" (2026-10-22).
- Stack (decided on LOCO + train/val only, `results/WP2/s7_select.json`): **L1 + L3c + L3d**, combiner `max` (auto-selected). L2b relations-only was DROPPED by the pre-registered rule (road block 3 alarms in 100% of its windows for linear-only check sets, 6.4-6.6% for sets with rate / value checks; limit 5% per fold). L3c FA-transfer design chosen among 8 by the rule: model M1 (inner folds for sigma / R2 include the real-road blocks = regime-aware scale), R2 filter 0.9, threshold pool = dyno folds (regime-averaged threshold-LOCO FA 1.37%; the S5 design M0 would have 24% on a new road session). The 3 s in-situ mute of S4 is removed (no onset-free definition accepted).
- **ROAD test, 6th exposure (S2, S3, S4 x2, S5 before)**, ONE run of the frozen domain: masquerade **5/5** (0.48-1.02 s, exact CI 48-100%), injected 6/6 (0.17-1.02 s), clean-window FA **3.20%** [0.00, 5.65] = 115 false alerts/h (limit 2%; WP2 target <= 1/h), per capture benign_anomaly 2.8%, extended_short **6.7%** (> 5%), reverse 0/51, highway diagnostics 1.7% (S5: 20.4%). All 44 combined false alarms come from L1 (bus load, period); L3c + L3d alone: 1.16% FA, masquerade 5/5, injected 5/6 (fuzzing missed).
- Fresh: 4 accelerator captures, whole-capture check only (injection precedes the capture, no labels): alarm fraction 11.6 / 4.2 / 4.7 / 0.0% vs clean 0.0-6.7%: no evidence either way. No fresh labelled ROAD holdout exists.
- Car-Hacking (L1, S2 numbers re-read): 99.5-100% recall, FA 1.0% [0.0, 2.2]. D11: known vehicles zero-shot FA 1.63%, unknown vehicles zero-shot **100%**, on-vehicle calibration 2.76% (known) / 3.28% (unknown) at recall 97-99%.
- v2 side-by-side: v2 timing at 0.1% has 0 false alerts and misses all masquerade captures and the coolant capture; v3 gets 11/11 at 115 alerts/h.

## Acceptance rule (as written before the result, notes/WP2_can.md "S7 start")
1 Process (frozen CanDomain with Evidence + MotionEstimate, tests, choices on LOCO / validation only, test scored once, caches <= 3 GB, own files committed). 2 Detection: >= 4 of 5 masquerade and the five v2-detected plain captures at delay <= 2 s. 3 FA: clean ROAD test windows <= 2% pooled, no clean ambient test capture above 5%; <= 1 false alert/h stated. 4 Reverse driving <= 2% of windows. 5 Reported without gate.
Acceptance: 1 MET (303 tests pass; S7 cache 646 MB before cleanup); 2 MET (5/5, 6/6, all <= 1.02 s); 3 **NOT MET** (3.20% > 2%; extended_short 6.7% > 5%; 115/h vs <= 1/h); 4 MET (0/51); 5 reported.

## What was done
- Code: `can/stack_core.py` (model container + per-window raws of all layers, one code path for experiments and deployment), `can/stack_eval.py` (threshold-LOCO, intervals), `can/domain.py` (CanDomain: Evidence per layer and combined, MotionEstimate from wheel speeds, save / load), `tools/WP2_S7_{lib,fit,tables,select,final,others,diag,summary,fixtures}.py`, tests `tests/can/test_stack.py` (7), `test_domain.py` (2).
- Data: ROAD train/val (selection), ROAD test (once), accelerator (once), Car-Hacking and D11 from the S2 results. Cache `../data_extra/WP2_S7_cache` (rebuild: `WP2_S7_fit.py prep|fold|weights|loo`, `WP2_S7_tables.py folds|val`).
- Results: `results/WP2/s7_*.json|md` (see M1_CAN.md), frozen domain `results/WP2/s7_domain/`.

## Results (copied from results/WP2/s7_test.json; full tables in s7_summary.md and s7_test_tables.md)
| configuration | clean FA [95% CI] | alerts/h | masquerade of 5 | injected of 6 |
|---|---|---|---|---|
| all (L1 + L3c + L3d, max) | 3.20% [0.00, 5.65] | 115 | 5 | 6 |
| only L1 | 4.73% [2.26, 8.04] | 170 | 0 | 6 |
| only L3c | 0.80% [0.00, 1.88] | 29 | 3 | 3 |
| only L3d | 0.00% | 0 | 2 | 2 |
| all but L1 (noisy-or) | 1.16% [0.00, 2.59] | 42 | 5 | 5 |
| all but L3c | 4.73% | 170 | 2 | 6 |
| all but L3d | 3.20% | 115 | 3 | 6 |
| optional: all + L2b (K3) | 5.16% [2.46, 9.33] | 186 | 5 | 6 |

## What changed after seeing results (honest list)
Nothing in the design. After the test: descriptive diagnostics (`s7_diag_test.json`, which L1 rule fires) and the observation that the all-but-L1 row is cleaner; neither feeds a choice. The Car-Hacking / D11 numbers were not re-scored.

## Problems, surprises, open questions
- FA is the unsolved part: the calibration predicts 2.06% (dyno) / 1.24% (all) for a new session; the test gives 3.20% with one capture at 6.7%. The specification rules (bus load, period) are the cause; the physics layers alone are at 1.16% but lose fuzzing. Decision wanted: keep L1 in the deployable CAN stack (detects injection, 4.7% FA alone) or use it only as a flag / first stage, with the physics pair as the alarm source.
- L2b was dropped by my own pre-registered 5% per-fold rule (fold 6.4-6.6%): a looser rule would have kept it; on the test it adds FA (5.16%) and nothing in detection.
- The supervisor note calls the Car-Hacking exposure "second"; the reports show S2, S3, S6 each scored it (at least fourth). I did not re-score it.
- Machine at 100% CPU: model fits took 17 min each under contention; a kill of my own slow process was denied; a second process was started (a duplicated fold, identical output).
- Wheel-speed unit for MotionEstimate (0.01 km/h) is an assumption of the anonymised DBC.

## Proposed next step
Close M1-CAN (partial). WP6 can use `CanDomain` as the CAN witness: Evidence (alarm source: physics pair) and the wheel-speed MotionEstimate (to be cross-checked against GPS / LiDAR).
