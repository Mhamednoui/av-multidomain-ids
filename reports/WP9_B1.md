# WP9 B1: CAN seen-attack benchmark (Car-Hacking, ROAD, can-train-and-test)

Date: 2026-11-04    Worker: sonnet (high, T3)

## Summary (<= 40 lines)
- Unit: 1 s window (label = at least one injected frame), features built inside each split segment. Splits locked and committed before training:
  locks/WP9_carhacking.json (v2/WP2 100-block split + 1 s gap, D02n normal_run first half val / second half test), locks/WP9_road.json (WP2 capture split, coolant = unseen row),
  locks/WP9_d11.json (WP2 splits_d11.json, sets 01-04). Dedup of exact rows: 0 (Car-Hacking), 1,435 of 27.4M (ROAD), 1 (D11).
- Models: window GBM / RF on generic and ID-count features, frame XGBoost (v3 L4 payload feature layout), ensemble; choice = validation macro-F1 at the validation 1% FA budget.
  Chosen: Car-Hacking W_rf_generic; ROAD frame XGBoost (Fb); D11 W_xgb_a_ids, E, F_noid, E for sets 01-04. Test scored ONCE per dataset / set (exposure: results/WP9/B1_exposure.json).
- Pre-registered verdicts (notes/WP9_B1.md): Car-Hacking MET; ROAD NOT MET; D11 NOT MET at the 1% budget. Unknown-vehicle sets fail completely.
- Honest caveat: the literature unit is frame / short window; ours is the 1 s window. "Better than" is claimed against nothing: the Car-Hacking numbers match the leaky bar, they do not exceed it.

| Dataset (protocol, our rows labelled seen attack types unless noted) | Our result on test (95% CI over blocks / captures) | B0 bar (protocol) | Verdict |
|---|---|---|---|
| Car-Hacking, block split + 1 s gap, window | macro-F1 0.999 [0.998, 1.000]; attack recall 0.999 [0.996, 1.000]; FPR 0.000 on block normals (596 windows); D02n test normal_run FPR 0.012; pooled FPR 0.0035 [0.000, 0.007]; AUC 1.000 | F1 0.998-1.0 reported under a random 7:3 / unstated 80:20 split (leaky; Hoang & Kim, Guerra et al.) | MET (our rule); equal, not better |
| ROAD, capture split, window, 10 classes | macro-F1 0.829 [0.724, 0.996]; attack F1 0.836 [0.536, 0.942]; FPR 0.032 [0.000, 0.157]; recall 0.858 [0.549, 1.000]; AUC 0.973 [0.889, 1.000]; 9/9 test attack captures alarmed, 0/2 coolant | Guerra et al.: LCCDE multiclass mean F1 0.32, DCNN 0.65-0.75, LSTM 1.0 (red flag), split not stated; our WP2 rules: masquerade 5/5 at FA 3.2% | NOT MET (FPR > 2%; reverse_light_on masquerade recall 0.00, reverse_light_off masquerade 0.48) |
| ROAD coolant (UNSEEN family row) | window recall 0 (0/2 captures), AUC 0.62 | none | unseen, reported only here |
| D11 test_01 known vehicle, known attacks (4 sets, attack-vs-normal window F1 at 1% budget) | mean 0.80 (sd 0.16); FPR 0.015; recall 0.90; AUC 0.98. Set_01: F1 0.723 [0.583, 0.827], FPR 0.019, recall 0.970 | Lampe & Meng set_01 test1 F1 0.98-0.99 (capture-disjoint, unit not stated) | NOT MET at the 1% budget |
| D11 test_01, post-hoc validation-F1-optimal threshold (not an acceptance basis) | F1 0.964 / 0.571 / 0.985 / 0.979 (sets 01-04), FPR 0.000-0.009 | same | informative only |
| D11 test_02 unknown vehicle, known attacks | mean F1 0.12; FPR 1.00 in all 4 sets; AUC 0.72 | Lampe & Meng test2 F1 0.95-0.96 | NOT MET (zero-shot vehicle fails, as in WP2) |
| D11 test_03 / test_04 (UNSEEN attack families) | test_03 F1 0.78 (sd 0.16), FPR 0.014; test_04 (unknown vehicle) F1 0.15, FPR 1.00 | Lampe & Meng test3 0.997, test4 0.998 | unseen rows, not seen-attack results |

- Controls: shuffled-label (global) AUC in [0.42, 0.58] for all Car-Hacking units; FAILS for ROAD frame model (0.28) and many D11 units (0.16-0.86): the shuffled-label noise model is not flat on outlier regions (same as WP2 S6).
  Added within-capture permutation control (validation): AUC 0.88 (Car-Hacking), 0.88 (ROAD), 0.44-0.88 (D11): the regime of a capture / block predicts "attack-bearing". Regime check on test: inside the same segments the detectors still separate (AUC 1.000 Car-Hacking, 0.93 ROAD, 0.99-1.00 D11 test_01 sets 01, 03, 04, 0.93 set_02), but ROAD FPR on normal windows next to attacks is 13.8% against 1.7% on ambient captures (and 43% on the short ambient reverse capture).
- Feature importance: no feature above 50% share; top features are bus-rate / timing (dt_id_ratio 0.15-0.39, n_id_win 0.32-0.44, nid_max 0.27-0.30) and payload bytes; no capture / time proxy. No red flag.
- Not claimed: any "best"; frame-level state of the art numbers (our unit differs; frame-expanded metrics in results/WP9/B1_frames.json are poor because a flagged window flags all its frames).

## Goal of the step
Seen-attack-type benchmark for CAN under leak-free splits, comparable to the B0 bar (WP9 file, step B1).

## Acceptance rule (written before results: notes/WP9_B1.md, section "pre-registration", 2026-11-04)
Car-Hacking: attack recall >= 0.98 at test FPR <= 1.5% and 5-class macro-F1 >= 0.95. ROAD: 10-class macro-F1 >= 0.75 and per-family alarm recall >= 0.8 at FPR <= 2%.
D11: set_01 test_01 attack F1 >= 0.98 at FPR <= 2%, mean over sets reported; test_02 reported without threshold; test_03/04 unseen rows.

## What was done
- Code: tools/WP9_B1_lib.py (parse, dedup, features, metrics), WP9_B1_lock.py, WP9_B1_build.py, WP9_B1_fit.py, WP9_B1_control2.py, WP9_B1_test.py, WP9_B1_report.py, WP9_B1_frames.py, WP9_B1_f1op.py; tests/can/test_wp9_b1.py (5 pass).
- Results: results/WP9/B1_<tag>_selection.json (validation, committed before test), B1_<tag>_test.json, B1_<tag>_control2.json, B1_tables.md (all tables), B1_frames.json, B1_regime.json, B1_f1op.json, B1_exposure.json.
  Scores (rule 6): results/WP9/scores/B1/<tag>_val.npz and <tag>_test.npz (test file: one pickled dict per model/subset with y, s, c, group, seg, wid; frame scores for frame models).
- Correction of B0 proposal: D11 test_03 / test_04 hold attack families absent from train, so they are unseen-attack rows, not seen rows (decision recorded before training).
- Bugs fixed before any test number existed: float32 threshold rounding (FPR 1.06% vs 1%), XGBoost Booster all-trees vs best iteration (caught by the validation-reproduction guard), script argument bugs.

## Results
See the summary table; full per-class recall with CIs, event-level ROAD table, FPR by capture, controls and regime diagnostic in results/WP9/B1_tables.md.
Car-Hacking per-class recall (test blocks): Normal 1.00, DoS 1.00, Fuzzy 0.996 [0.986, 1.000], RPM 1.00, Gear 1.00. ROAD per-class recall: fabrication classes 1.00 (correlated, speedometer, reverse on / off, fuzzing n=1 window),
masquerade: correlated 1.00, speedometer 0.98, reverse_light_off 0.48, reverse_light_on 0.00.

## Ablation row(s)
Frame model without raw ID (F_noid) vs with ID: Car-Hacking val macro-F1 0.995 vs 0.997 (ID not needed); window feature sets generic vs +ID counts: equal within 0.002 on Car-Hacking, +ID better on D11 val set_01 (0.596 vs 0.57).

## Problems, surprises, open questions
- Capture-regime shortcut is learnable (within-capture control fails); results are credible only through the same-segment diagnostics above; ROAD's alarm budget is violated by windows adjacent to attacks.
- Unknown-vehicle D11 sets fail completely with a threshold calibrated on the known vehicle (FPR 1.0). On-vehicle calibration (WP2 regime B) was not tried; it needs benign data of the new vehicle.
- Unit mismatch with the literature (frame / short window); the frame detector F was validated but not scored on test. Suggest for B5: pre-register a frame-level secondary and the on-vehicle calibration variant.
- ROAD fuzzing and several D11 classes have 1-30 test windows: per-class recall CIs are wide.

## Proposed next step
B5 (final comparison) after B2-B4; or a B1b step: frame-level scoring + on-vehicle calibration for D11, if the supervisor wants those rows.
