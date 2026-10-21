# WP2 S4: L2b signal physics on decoded ROAD signals

Date: 2026-10-22    Worker: sonnet (medium)

## Summary
Verdict: **NOT MET** (items 2 and 4 fail on false alarms; detection is good). Rule and design: notes/WP2_can.md "S4 start" + "design change 1, 2" (all written before any test score).
Plain answer: **signal physics catches 4 of the 5 ROAD test masquerade captures, including the coolant one, at 0.0-0.9 s delay, but alarms on 64-71% of the windows of two
benign test drives (door / seatbelt style rare states), so clean-window FA is 38% (limit 2%).** Reverse driving: 0 alerts.
- Decoding: own DBC decoder (can/signals.py, no cantools) reproduces signal_extractions exactly (7.4 M values, 0 mismatches); runs on raw frames of any capture. The DBC is
  anonymised (all signals "Unknown_k"): meaning comes from TRAIN attack metadata + correlations: 0xd0.5 = speedometer, 0xd0.2 = reverse-light bit, 0x6e0.0-3 = four wheel speeds
  (14 bit), 0x4e7.1 = coolant byte, 0x498.3 / 0x20e.1 = more speed signals (corr 1.0), 0x295.0 / 0x274.14 / 0xc0.0 = gear state (predict the reverse bit, NMI 0.997).
- Model (clean-only, summable statistics): value/range, rate/transition, linear relations between continuous signals (45 pairs, rho 0.98; wheel speeds vs speedometer ~ gain 0.866),
  joint state support between discrete signals (1500 pairs, NMI >= 0.7; includes reverse bit vs gear). Not done: RPM x gear ratio and brake vs deceleration (no such signals identifiable
  from the anonymous DBC; gear-conditioned linear relations not implemented).
- Calibration: LOCO over 7 clean ambient captures (exercise_all_bits in the fit only), 1% tie-safe thresholds at window and frame level; 4 variants (rho x min support) chosen on
  train/val masquerade recall (variant 0: rho 0.98, ms 1; val recall 0.75: wheel/speedometer/reverse_on 1.0, reverse_off 0.0; val clean FA 0).
- Two design changes BEFORE the test run, both forced by LOCO / validation diagnostics: (1) per-check surprise weights from LOCO violation counts (a per-type ECDF made every held-out
  capture alarm in 100% of windows: session-specific states); (2) in-situ baseline: checks that violate in the first 3 s of a capture are muted and those 3 s are not scored (attack captures are
  other sessions with states absent from all ambient folds; clean-lead FA was 100% without it). Cost: attacks in the first 3 s invisible (test onsets >= 4.3 s).
- TEST (single verdict run, variant 0), window level, detection (>= 1 alarmed attack window) / delay: correlated_signal_3 masq yes 0.68 s (check: linear wheel vs speedometer),
  max_speedometer_3 masq yes 0.48 s (linear), reverse_light_on_3 masq yes 0.93 s (joint: reverse bit vs gear), coolant masq yes 0.02 s (linear/value), reverse_light_off_3 masq NO.
  Non-masquerade copies behave the same; fuzzing_3 detected (joint, 0.66 s, recall 0.5). Frame-level recall at the 1% frame budget: 1.0 on the four detected masquerade captures.
- False alarms on clean test windows (n = 1394): L2b 38.1% (benign_anomaly 64.2%, extended_short 71.1%, reverse 0/48, highway diagnostics 0/466, attack-capture leads 2/94). L1 alone 5.2% (OR of the
  five S2 run-1 rules recomputed from stored windows; S2's harness reported 3.4%), L1 + L2b 40.4%. Item 3 (no alert on reverse driving) is met.
- Why caught: wheel speeds / speedometer / coolant byte are overwritten while the other speed signals keep telling the truth (physical redundancy: four wheels + two more speed
  signals agree to within a learned residual); reverse-light on while the gear state says D is a state contradiction. Why reverse_light_off is missed: the light bit is cleared while the
  car is in R, but flag 0 + gear R is seen a few times in every clean capture (light lags the lever by a few frames), so the combination is not rare enough; it is plausible physics. An honest limit: only
  a time-aware relation (light must follow gear within ~0.5 s) could catch it, not a support check.
- Why the false alarms: value / rate checks on discrete signals fire on values never seen in training (0x5e1.2, 0x107.3, 0x153.6, 0xc0.2 ...) = the rare legitimate states the task warns about (benign
  anomaly drive: door / belt events), and the 1500 generic joint pairs add many more. Post-verdict diagnostic only (tools/WP2_S4_diag_test.py): 89-127 checks fire in these two drives.
- Second exposure (labelled): revision R1 = joint checks only for pairs involving the reverse-light bit (motivated by the post-verdict diagnostic; on VALIDATION identical: recall 0.75, LOCO FA 1.0%,
  results/WP2/s4_ablation_val.json). Test: same 4/5 masquerade detected, clean FA 32.3% (benign 49.5%, extended 66.6%), reverse_on attack lead FA 0. Still NOT MET: single-value checks on discrete signals dominate.
- Ablation (validation, variant 0): without joint checks reverse_on is lost (recall 0.5); linear alone 0.5; joint alone 0.25; value/rate alone 0.5. Harness ablation on top of L1 (test): L1 alone detects the
  non-masquerade copies only (0/5 masquerade captures except coolant, L1 sees coolant by period); L1 + L2b adds 4 masquerade captures at the cost of FA 5.2% -> 40.4%.
- Car-Hacking: NOT evaluable (no DBC; payload to signal mapping of 0x316 RPM / 0x43f gear is not available in the data and I did not invent one). D11: no decoded signals, NOT evaluable.
Acceptance: 1 met (layer, causal, clean-only, LOCO + 1% tie-safe, 227 tests pass, cache 673 MB); 2 NOT MET (4/5 detected, FA 38.1% > 2%); 3 met; 4 NOT MET (keeps the 5 v2 captures, delay <= 0.93 s, FA 40.4% > 5.5%); 5 reported.

## What changed after seeing results (honest list)
1. First LOCO pass with per-type ECDF -> weights (change 1); 2. in-situ 3 s baseline (change 2); both from LOCO / train-val diagnostics, before any test score; 3 s chosen knowing the public onset list.
2. After the verdict: diagnostics on the test ambient drives (descriptive) and the labelled second exposure R1. Verdict numbers are from results/WP2/s4_test.json.
3. A stray first LOCO process (old design, python pid 30976) was started by me and could not be stopped (kill denied by the permission system); it wastes CPU and writes only to a cache folder I deleted.
4. Intermediate caches (ECDF-era scores) deleted; cache ../data_extra/WP2_S4_cache = 673 MB.

## Files
can/signals.py, can/l2b_signals.py, tools/WP2_S4_{cache,decode_check,explore,run,eval,ablate_val,fit_probe,trace,trace_attack,diag_test,model_summary}.py, tests/can/test_l2b.py (5 tests).
Results: results/WP2/s4_test.json + s4_tables.md (verdict), s4_test_r1.json + s4_tables_r1.md (second exposure), s4_select.json, s4_ablation_val.json, s4_final_model.json, s4_weights_summary.json,
s4_signal_stats.json, s4_decode_check.json, logs/s4_*.

## Problems / open questions
- The per-session shift (rare discrete states, each attack capture a new session) is the same obstacle as S2/S3: FA does not transfer. A deployable L2b probably needs continuous-signal relations only
  (linear, rate, range on cont signals: detects 4/5 per validation ablation) plus a handful of named joint rules (gear vs reverse bit), with discrete value/rate checks off. That is a design for S5/S7, not tested on test here beyond R1.
- Decision wanted: keep L2b "relations only" in the default stack and drop generic discrete value/rate/joint checks? 

## Proposed next step
S5 per-signal predictors (L3) on continuous signals only, trained on ambient; reverse_light_off needs a lag relation (light follows gear), to be added there.
