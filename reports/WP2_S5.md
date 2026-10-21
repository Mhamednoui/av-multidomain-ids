# WP2 S5: L3 per-signal predictors (residual alarms) on decoded ROAD signals

Date: 2026-10-22    Worker: sonnet (high)

## Summary
Verdict: **NOT MET** (item 2 FA and item 4 extra FA fail; detection is 5 of 5). Rule and design: notes/WP2_can.md "S5 start" + "S5 design changes 1-3" (rule written before any L3 score; test run once, labelled "ROAD test exposure 5").
Plain answer: **per-signal predictors catch all 5 ROAD test masquerade captures (including reverse_light_off, missed by L2b) at 0.48-1.02 s, but alarm on 7.6% of clean test windows (limit 2%), and on 20.4% of the highway drive: a new session of a driving regime is not predicted well enough.** Reverse driving: 0 alerts.
- Layer: L3c = one ridge predictor per continuous signal (138 signals), features = the other 137 signals at the same 0.05 s step + own value 0.05 / 0.25 / 1.0 s earlier (chosen variant "cross+own"), residual standardised by the largest per-capture out-of-fold RMSE, aggregated per 1 s by max over signals of a sliding 1 s CUSUM (sum of max(z-3, 0)).
  L3d = lag-aware state predictor of the reverse-light bit from three redundant gear copies (0x295.0, 0xc0.0, 0x274.14): seconds of contradiction in the last 1 s; alarm when longer than the longest one on any clean held-out capture (all clean ones were a single 0.05 s step).
  Ridge / lambda / sigma / R2 fitted from Gram matrices (numpy only), nested LOCO (inner folds choose lambda per signal and sigma). Code: can/l3_predictors.py; tools/WP2_S5_{grids,run,eval,report,tables,l2b,highway,diag_test}.py; tests/can/test_l3.py (5 tests; suite 239/239).
- Calibration: LOCO over 6 clean dyno captures (exercise_all_bits and the highway drive are fit-only, see changes), tie-safe 1% at window and frame level for each sub-detector; L3 = OR of the two (nominal <= 2%).
- Test (ROAD, window level), L3 alone: correlated_signal_3 yes 0.68 s, max_speedometer_3 yes 0.48 s, reverse_light_off_3 yes 0.48 s (L3d), reverse_light_on_3 yes 0.93 s (L3d), coolant yes 1.02 s (L3c). Non-masquerade copies same except reverse_off_3 1.48 s, reverse_on_3 20.9 s (attacker frames interleave with legit ones; flag flickers); fuzzing_3 not detected by L3 (L1 does, 0.18 s).
  Frame-level recall at 1% each: 0.977-0.999 on the five masquerade captures (and 0.50 / 0.12 on the interleaved reverse_off_3 / reverse_on_3 non-masquerade copies).
- Clean test windows (n = 1394): L3 FA 7.6% (L3c 7.6%, L3d 0). Per clean test capture: benign_anomaly 0.7%, extended_short 2.2%, reverse 0.0%, highway diagnostics 20.4%, attack-capture leads 0/94. LOCO per fold (pooled threshold): 0 / 4.6% / 0.5% / 0 / 0.5% / 0 (spread is large, one fold 4.6%).
- Harness (test, clean-window FA / masquerade detected of 5): L1 5.2% / 1 (coolant only; masquerade copies of the others not seen); L2b relations-only 31.2% / 4; L1+L2b 33.9% / 4; L3 7.6% / 5; L1+L3 12.6% / 5; L1+L2b+L3 40.6% / 5.
  L3 adds reverse_light_off_3_masquerade to L1+L2b (the only masquerade they miss). Extra FA of L3 over L1+L2b: +6.7 points (gate: 2). AUC (window, L3, all test) 0.957.
- Why caught (physics): ROAD masquerades overwrite ONE message while the car keeps telling the truth through redundant signals. correlated_signal rewrites the four wheel speeds of 0x6e0 consistently with each other but not with the speedometer and the two other speed copies (0x498.3, 0x20e.1): test median z 72-315 on the wheels, 90-96 on the copies;
  max_speedometer rewrites 0xd0.5 only: z 10-19 on the whole speed group (the corrupted value also contaminates the predictions of its relatives, so the culprit is not isolated by the argmax); coolant 0x4e7.1: z 154-175 (and 94 on 0x65c.3, a related thermal signal). These are visible. Invisible by construction: a masquerade that rewrites ALL related signals consistently (all 4 wheels + speedometer + copies, or the three gear copies together with the light). No ROAD capture does this (each rewrites one ID), so none is "invisible", but it is the stated limit of any redundancy-based layer.
  reverse_light_on / off are discrete bits: continuous predictors (L3c) never fire on them (0/4 captures); only the lag-aware gear contradiction (L3d) sees them. Reverse_light_off is the case S4 could not catch: flag 0 with gear R lasts seconds in the attack but only one 0.05 s step in clean data.
- Why the false alarms: the single highway drive and its test counterpart: signals 0x193.1 and 0x3c1.2 (poorly predicted, kept by r_min = 0) dominate the alarmed steps (diag, descriptive). Unseen-regime diagnostic (highway left out of the fit): 32% of its windows alarm at the pooled threshold. Same obstacle as S2-S4: thresholds from few captures of one regime do not transfer.
- Car-Hacking / D11: no decoded signals (no DBC): not evaluable.
Acceptance: 1 met; 2 NOT MET (5/5 detected, FA 7.6% > 2%, highway capture 20.4% > 5%); 3 met (0.0%); 4 NOT MET (keeps the five v2-detected captures at <= 0.93 s, adds 1 masquerade, extra FA +6.7 points > 2); 5 reported.

## Acceptance rule (written before the result, notes/WP2_can.md, 2026-10-22 "S5 start")
1 layers (API, causal, clean-only, nested LOCO, tie-safe 1% window + frame, tests, commit, caches <= 3 GB). 2 L3 >= 4/5 masquerade AND clean test FA <= 2% AND no clean test ambient capture > 5%. 3 reverse driving <= 2%.
4 L1 + L2b_rel + L3 keeps the 5 v2-detected captures (delay <= 2 s), L3 adds >= 1 masquerade or documents none, extra clean FA <= 2 points. 5 reporting list.

## What changed after seeing results (honest list)
1. Pre-registered design failed on LOCO (not on test): all 8 variants tied at recall 0.5 (pooled 1% threshold on the z cap). Three changes, all decided from LOCO / train+val diagnostics before any test score (details: notes "S5 design changes 1-3"):
   (a) highway drive and exercise_all_bits are fit-only (6 folds): leaving the highway out gives an unseen regime (z > 5 on 14.5% of steps, 3,740 of the pooled windows); the unseen-regime fold is reported (s5_highway_fold.json);
   (b) sigma = largest per-capture OOF RMSE, winsor 30 -> 1000, CUSUM made a bounded 1 s sliding sum; (c) L3d alarm floor = longest clean contradiction (lag tolerance).
2. Variant 5 (cross+own, r_min 0, cusum) was chosen by the pre-registered rule on validation (recall 0.994, lead FA 1.2%); test saw only that variant (scores for the other variants were not computed on test).
3. The L2b relations-only number on test appears here (harness ablation requested for S5). The decision of 2026-10-22 reserved its test number for the S7 verdict: this is therefore an additional exposure for L2b-rel, labelled; it did not feed any choice.
   L2b-rel was built exactly as decided (S4 variant-0 models and S4 weights, discrete value/rate checks dropped, joint only with the reverse bit, S4 3 s mute kept); on test it still alarms on 31.2% of clean windows: post-verdict diagnostic: 96-98% of its alarmed windows are "value" (range) checks on continuous signals in benign_anomaly / extended_short, so range checks on continuous signals also do not transfer. Not fixed here.
4. Post-verdict diagnostics (s5_diag_test.json) are descriptive; no design change followed.

## Files
can/l3_predictors.py, tools/WP2_S5_{grids,run,eval,report,tables,l2b,highway,diag_test,explore,explore2,dbg,dbg2,dbg3,dbg4}.py, tests/can/test_l3.py, can/l2b_signals.py (CONT_ONLY flag added, default off, S4 behaviour unchanged).
Results: results/WP2/s5_select.json, s5_val.json + s5_val_tables.md (train/val), s5_test.json + s5_test_tables.md (verdict), s5_summary.md (long tables, generated), s5_highway_fold.json, s5_diag_test.json, logs/s5_*. Cache ../data_extra/WP2_S5_cache = 165 MB.

## Problems / open questions
- FA transfer is again the blocker (L3c 20% on the real-road drive, 4.6% on one dyno fold). Options for the supervisor: (1) calibrate per driving regime / add regime recognition; (2) restrict L3c to signals with high out-of-fold R2 AND stable across sessions (r_min 0.9 variants were not chosen on validation; a test-time look would be a second exposure); (3) accept L3 as a high-precision relation layer (physics redundancy only: wheels / speed / coolant) and keep L3d for the reverse-light bit.
- Decision wanted: the L3d lag-aware gear/flag rule solved the reverse_light_off miss (0.48 s, 0 FA on all clean test drives incl. real reverse driving). Keep in the default stack?
- L2b relations-only still has 31% FA on test (range checks on continuous signals): S7 needs a decision (drop range, or calibrate per regime).

## Proposed next step
S6 retrain timing + payload models in the harness (as planned); S7 combiner must handle FA 5% (L1) + L3c highway FA; possibly a regime-aware calibration step before S7.
