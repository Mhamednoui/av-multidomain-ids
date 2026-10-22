# WP2 CAN brief (state at 2026-10-22, after S7: M1-CAN reported PARTIAL, step in REVIEW)

## State
- S0 data inventory, S1 adapters/splits/frames: APPROVED. S2 (L1 rules): done, verdict NOT MET (ROAD false alerts 3.4% > 1%).
- S3-S6 outcomes below; S7 (combined stack, M1-CAN) done: see the S7 section and reports/M1_CAN.md. WP2 has no further planned steps.

## S3 (L2a clock skew) outcome
- NOT MET: skew does not catch ROAD masquerade (run 1: 0/5, FA 3.9%; revised run 2b: FA 35%). Rate difference attacker vs ECU about 60 ppm median, logger jitter 12-28% of period.
- ROAD masquerade logs = attack log minus legit frames of the injected ID; injected timestamps are real attacker times (identical to the non-masquerade log).
- Car-Hacking: no gain; D11: weaker than L1. Keep L2a out of the default stack. Code: can/l2a_skew.py, can/l2a_exp.py, tools/WP2_S3_*.py, report reports/WP2_S3.md.
- Next: S4 signal physics on decoded signals; masquerade must come from payload/signal layers.

## S4 (L2b signal physics) outcome
- NOT MET: masquerade 4/5 detected on test (wheel speeds, speedometer, coolant via linear relations; reverse_light_on via joint reverse-bit vs gear; reverse_light_off missed) but clean-window FA 38% (limit 2%): rare legitimate discrete states (benign drives).
- Decoder can/signals.py exact vs CSV; DBC anonymous (meaning from train metadata + correlation). Model/code: can/l2b_signals.py; tools/WP2_S4_run.py (stages stats|fold|final|weights|score), WP2_S4_eval.py (select|report).
- Design needed: LOCO weights per check + in-situ 3 s baseline (mute checks violated in the first 3 s). Cache ../data_extra/WP2_S4_cache (673 MB: payload bytes, stats, models, sparse scores).
- Next: S5 per-signal predictors on continuous signals; consider L2b "relations only" (linear/range/rate on continuous + named gear-reverse rule) in the default stack. R1 (second exposure) FA 32%.

## S5 (L3 per-signal predictors) outcome
- NOT MET (FA): L3 detects 5/5 ROAD test masquerade (0.48-1.02 s), incl. reverse_light_off via the lag-aware gear-contradiction rule L3d (flag 0 while 2 of 3 gear copies say R, longer than the longest clean contradiction = one 0.05 s step); clean test FA 7.6% (highway diagnostics 20.4%, others 0-2.2%, reverse 0).
- L3c = ridge per continuous signal (138) on a 0.05 s grid, cross + own lags, sigma = max per-capture OOF RMSE, sliding 1 s CUSUM; Gram-matrix ridge, nested LOCO; fit-only captures: exercise_all_bits + highway drive (6 dyno folds). Highway left out: 32% alarms (unseen regime).
- Harness (test): L1 5.2%/1, L2b-rel 31.2%/4 (range checks on continuous signals fire on benign sessions; its test number was exposed here), L3 7.6%/5, L1+L2b+L3 40.6%/5.
- Code: can/l3_predictors.py; tools/WP2_S5_{grids,run,eval,report,tables,l2b,highway,diag_test}.py; cache ../data_extra/WP2_S5_cache (165 MB, grids + models + scores; rebuild: grids, grams, fold, score loco/attack/test, WP2_S5_l2b.py).
- Next: S6; S7 must decide L2b range checks and regime-aware calibration.

## S6 (L4 timing + payload retrained in the harness) outcome
- NOT MET (leakage controls, reverse-driving, Car-Hacking FA): details reports/WP2_S6.md, results/WP2/s6_summary.md. ROAD test NOT scored; ROAD judged on validation + 13-fold out-of-fold (8 ambient captures, 5 attack families).
- L4 does NOT add on top of L1 + L2b + L3 (ROAD val: base 9/9 captures, L4 only +0.7..1.4 points FA), nor on Car-Hacking (L1 ~100% already), D11 adds in 1 of 32 cells. L4 timing alone matches L1 on known D11 vehicles with lower FA (0.7% vs 2.5%); zero-shot to unknown vehicles = 100% FA for every layer.
- Payload model: reverse-bit windows 5.9% alarms (exercise_all_bits, highway), unseen-family recall 0% on correlated/speedometer/fuzzing; Car-Hacking-trained models on ROAD val: 1.3% / 0% window recall at ROAD-calibrated 1%.
- Controls: window shuffled-label AUC bound (0.55) failed in 11/12 cases (max-type window score of a noise model rises in sparse regions); frame bound met (but < 0.5); timing model dominated (>50% gain) by dt_id_ratio / n_id_win on Car-Hacking and D11 (timing relations, not identifiers).
- Code: can/l4_features.py, can/l4_exp.py; tools/WP2_S6_*.py; tests/can/test_l4.py. Caches ../data_extra/WP2_S6_cache = 1.7 GB (raw features ROAD train+val and Car-Hacking, models, window tables, D11 run); rebuild: WP2_S6_cache.py road|carhacking, WP2_S6_road.py p1|oof|ctrl, WP2_S6_ch.py fit|test|ctrl, WP2_S6_d11.py fit|test <set>.
- S7 hint: keep L4 timing as optional low-FA single-vehicle layer at most; L3/L3d carry the ROAD masquerade; ROAD test (single labelled run + fresh holdout) still to be done in S7.

## S7 (combined stack, ablation, fresh checks, M1-CAN) outcome
- PARTIAL: ROAD test (6th exposure) masquerade 5/5 (0.48-1.02 s), injected 6/6, clean-window FA 3.20% [0.00, 5.65] (limit 2%; 115 alerts/h vs target <= 1/h; extended_short 6.7%), reverse 0/51. Report reports/M1_CAN.md, step report reports/WP2_S7.md, tables results/WP2/s7_summary.md, s7_test_tables.md, s7_others.md.
- Default stack: L1 + L3c + L3d (DomainCombiner auto -> max, threshold = 1% of 7,198 pooled LOCO normal windows). L2b relations-only DROPPED by the pre-registered LOCO rule (a road block alarms in 100% of its windows at the linear-only threshold; 6.4-6.6% with rate / value checks; limit 5%). L2a, L4 out (S3, S6). 3 s mute removed.
- FA-transfer design (rule on LOCO): inner folds of the L3c fit (sigma, R2, lambda) include the real-road blocks (M1), R2 >= 0.9, threshold pool = dyno folds. Highway drive split in 4 time blocks (30 s cut) = LOCO folds of the real-road regime. M0 (S5) gives 24% FA on a new road session in LOCO.
- All 44 combined false alarms of the test are L1 (bus load, period); L3c + L3d alone: 1.16% FA, 5/5 masquerade, fuzzing missed. Open decision for the supervisor: L1 as alarm source or as a first-stage flag.
- Accelerator captures: whole-capture check only (injection precedes the capture; no labels): 11.6 / 4.2 / 4.7 / 0.0% alarm windows vs 0.0-6.7% clean. No fresh labelled ROAD holdout exists.
- Car-Hacking / D11: L1 only (no DBC), S2 numbers re-read, no new scoring. D11 unknown vehicles zero-shot 100% FA; on-vehicle calibration 3.28% FA, recall 98.9%.
- Code: can/stack_core.py, stack_eval.py, domain.py; tools/WP2_S7_*.py; tests/can/test_stack.py, test_domain.py (suite 303 passed). Cache ../data_extra/WP2_S7_cache (rebuild: WP2_S7_fit.py prep|fold|weights|loo, WP2_S7_tables.py folds|val, WP2_S7_select.py, WP2_S7_final.py freeze; test tables and final.py test only after s7_frozen.json exists).

## Frozen CAN domain output (for WP6 / WP7)
`can/domain.py`; fitted object `results/WP2/s7_domain/` (domain.pkl force-added to git, domain.json, fixtures example_evidence_correlated_signal.json, example_can_motion_estimates.json).
```
d = CanDomain.load("results/WP2/s7_domain")
comb, per = d.score_capture(t, ids, dlc, B, name="car0")    # t seconds (recorded order), ids, dlc, B n x 8 uint8
est = d.motion_estimates(t, ids, dlc, B)
```
- Evidence (comb): domain "can", layer "combined", name "can.combined", one per 1 s window (emitted when its second has passed; the first second is not scored), t = window end, score in [0, 1] = max of ECDF-calibrated layer scores, alarm = score >= 0.99304, reason = layer physics sentences + culprit signal, details {method, layer_scores, culprit_signal}, sample_id "capture/second". per = {layer name: Evidence list} (L1 spec rules, L3c predictors, L3d reverse-light rule) with their own 1% thresholds.
- MotionEstimate: source "can", one per second, speed = mean of the 4 wheel speeds (0x6e0.0-3) x 0.01 km/h -> m/s (ASSUMED unit; calibrate against GPS / LiDAR), unsigned, sigma = max(0.3 m/s, 3% of speed), yaw_rate / displacement None. A CAN attacker who rewrites 0x6e0 controls it: a claim, not a witness.
- Vehicle-specific (ROAD, anonymised DBC): another vehicle needs its own clean calibration and DBC. Expect 1-3% window FA on unseen sessions (worst test capture 6.7%).

## Binding decisions
- Domain "can", layers L1.. ; Layer API from common/layer.py; evaluation only through common/evaluate.py.
- Unit 1 = frame (causal, recorded order, dt_clipped only; never use the sign of dt). Unit 2 = 1 s window by running-max t;
  window label = >= 1 injected frame.
- Clean = attack-free traffic only (ROAD ambient + lead of attack captures minus 1 s; Car-Hacking blocks without injection;
  D11 same lead rule). Profiles/thresholds never see attack frames; the tolerance variant is the only chosen hyper-parameter.
- Splits: v2 ROAD split, v2 block split for Car-Hacking, D11 splits in results/WP2/splits_d11.json (4 sets, 4 test subsets).
- D11 regime A zero-shot, regime B on-vehicle (first 30 s profile, next 30 s thresholds, score t >= 60 s).
- Test labels never choose anything. ROAD run 1 is the verdict; run 2 (IQR periodic test) is "revised design".

## Pitfalls
- Specification rules cannot see same-ID same-period masquerade; do not claim the masquerade target for L1.
- ID/DLC allow-lists are vehicle-specific: zero-shot to another vehicle gives ~100% FA. Needs on-vehicle calibration.
- Noisy-or of 5 rules at 1% each gives 3-4% FA; ROAD test ambient (benign_anomaly, extended_short) shifts vs val.
- D11 files with no clean frame exist (ProfileBuilder guards empty input). Car-Hacking test is interleaved blocks:
  delay fields are not onset delays; "other_normal" windows there border attacks, high alarm rate is expected.
- Do NOT cache per-frame strings: a 39 GB blow-up filled the disk. Cache = int8 attack codes
  (../data_extra/WP2_S2_cache, 3.4 GB; rebuild: tools/WP2_S2_cache.py road|carhacking|d11, ~10 min).
- Run python with PYTHONDONTWRITEBYTECODE=1 in the tf conda env. Avoid apostrophes in long bash heredocs (parse errors).

## File map
- can/: frames.py, adapters.py, splits.py (S1); l1.py (rules, profile, features); l1_exp.py (experiment machinery).
- tools/: WP2_S2_cache.py, WP2_S2_run.py (road|carhacking|d11 set_0N, resumable).
- tests/can/: test_frames_adapters.py, test_l1.py.
- results/WP2/: s1_*.json, splits_*.json, s2_road.json (run 2), s2_run1_frozen/ (verdict), s2_run2_iqr/, s2_carhacking.json,
  s2_d11_set_0N.json, s2_d11_tables.md, s2_harness/, s2_profiles/, logs/.
- reports/WP2_S1.md, WP2_S2.md; notes/WP2_can.md (all decisions, written before results).
