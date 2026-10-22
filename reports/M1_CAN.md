# M1-CAN: CAN intrusion detection by specification rules and signal redundancy (WP2, milestone report)

Date 2026-10-22. Status: **PARTIAL** (detection met, false alarms NOT met). Rule written before any S7 result: notes/WP2_can.md "S7 start" (items 1, 2, 4 met; item 3 NOT met). Self-contained; long tables: `results/WP2/s7_summary.md`, `s7_test_tables.md`, `s7_others.md`, `s7_select_tables.md`; numbers: `s7_test.json` (ROAD test), `s7_select.json`, `s7_dev.json`, `s7_accel.json`, `s7_others.json`, `s7_diag_dev.json`, `s7_diag_test.json`, `s7_frozen.json`.

**Protocol.** ROAD (one real vehicle, anonymised DBC, 41 capture files + 4 accelerator files). Windows are 1 s (running-max clock); a window is positive if it holds one injected frame; clean = attack-free frames only. Calibration = leave-one-capture-out (LOCO) over 10 clean folds (6 dyno captures, 4 time blocks of the real-road highway drive with 30 s cut between blocks; exercise_all_bits fit-only), 7,198 pooled normal windows, tie-safe 1% budget, all fitted parts nested (L1 profile, L3c ridge/lambda/sigma/R2 by inner folds, L2b check weights). Design choices only on LOCO + 18 train/val attack captures (rules in the notes). Default stack **L1 spec rules + L3c per-signal predictors + L3d reverse-light state rule**; layer scores ECDF-calibrated, combined by `common.combiner.DomainCombiner` (auto -> `max`, threshold = 1% of pooled normal windows). L2b relations-only was **dropped by the pre-registered LOCO rule** (below); L2a clock skew and L4 learned models are out (negative S3 / S6). Test = 15 ROAD test captures, scored **once** (see exposure).

## 1. What each layer catches, and why (ROAD test, window level, each layer at its own 1%)

| layer | physics | clean FA | masquerade (of 5) | injected (non-masq, of 6) |
|---|---|---|---|---|
| L1 spec rules (ID allow-list, DLC, period, bus load, flood) | an injector ADDS frames (bus load, flood, unknown ID); a masquerade only edits frames in place (legit frames of the ID removed, same period) | 4.73% | 0 | 6 |
| L3c per-signal predictors (ridge over 138 signals, 1 s CUSUM) | the car tells the truth through redundant signals: 4 wheel speeds, speedometer and 2 more speed copies agree to a learned residual; a rewritten wheel message (z 72-315) or speedometer (z 10-19) or coolant byte (z 154-175) disagrees with its relatives | 0.80% | 3 (wheels, speedometer, coolant) | 3 |
| L3d gear vs reverse-light rule | the light must follow 3 redundant gear copies within a lag; a flag held against the gear for longer than any clean contradiction (one 0.05 s step) is an injection | 0.00% | 2 (light on / off) | 2 |
| **combined (L1 + L3c + L3d)** | | **3.20%** | **5** | **6** |
| physics only (L3c + L3d, noisy-or) | | 1.16% | 5 | 5 (fuzzing missed) |
| optional: + L2b relations (K3) / L2b alone | linear wheel/speed relations, range, rate on continuous signals | 5.16% / 5.38% | 5 / 4 | 6 / 4 |

Invisible by construction: a masquerade that rewrites ALL related signals consistently (all wheels + speedometer + copies, or the gear copies together with the light); no ROAD capture does (each rewrites one ID). The reverse-light on/off bits are discrete: continuous predictors never fire on them, only L3d does.

## 2. Final numbers (ROAD test, combined stack; 95% intervals: cluster bootstrap over clean units, exact binomial for counts)

| attack | original: detected / delay (s) | masquerade copy: detected / delay (s) | window recall (orig / masq) |
|---|---|---|---|
| correlated_signal | yes / 0.68 | yes / 0.68 | 100% / 100% |
| max_speedometer | yes / 0.48 | yes / 0.48 | 100% / 5% (3 of 62 windows; detected in the first window) |
| reverse_light_off | yes / 0.48 | yes / 0.48 | 100% / 100% |
| reverse_light_on | yes / 0.93 | yes / 0.93 | 100% / 100% |
| max_engine_coolant | yes / 1.02 | yes / 1.02 | 83% / 83% |
| fuzzing | yes / 0.17 | (none) | 100% |

Masquerade detected **5/5** (exact 95% CI 48-100%), injected captures 6/6; all delays 0.17-1.02 s. Clean-window FA **3.20%** [0.00, 5.65] (44 of 1,375 windows = **115 false alerts/h**; 3.97% without the highway drive). Per clean capture (95% block bootstrap): benign_anomaly 2.8% [0.5, 6.1], extended_short **6.7%** [3.1, 11.4], reverse 0/51 [0, 52], highway diagnostics 1.7% [0.4, 3.2]. Threshold-LOCO on the development folds predicted 2.06% (dyno) / 0.47% (road blocks) / 1.24% (all): the new dyno sessions are worse than the fold average (one fold, extended_long, was 9.1%).

**Fresh data.** The 4 ROAD accelerator captures (never scored in v3) have no injected frames; ROAD documents the injection as happening BEFORE the capture starts, so each whole capture is in the attacked state and there is no onset and no window label: no fresh labelled ROAD holdout exists. Whole-capture check, combined alarm fraction: drive_1 11.6%, drive_2 4.2%, reverse_1 4.7%, reverse_2 0.0% (clean test captures 0.0-6.7%). Only drive_1 exceeds the clean range; four captures cannot support a claim, and the layers do not model pedal-vs-acceleration (no pedal signal identified). Result: no evidence of detection, none of absence.

**v2 side-by-side** (same captures, v2 numbers read from `codes_v2/results/road_windows.json`): the v2 timing model at its 0.1% target has 0 false alerts and detects only the 5 injected captures (masquerade AND coolant missed); at 1% it detects 7/11 (masquerade correlated + speedometer) with 0.83% FA (30/h); the v2 payload model detects 10/11 at 4.85% FA (175/h) and 8/11 at 0.1%. v3 detects 11/11 at 3.20% (115/h); with L3 only 10/11 at 1.16% (42/h). v3 buys the masquerade and coolant captures with false alarms: v2 at 0 FA/h is not beaten on FA.

## 3. Ablation (ROAD test; development ablation in `s7_dev.json` is in-sample for the combiner)

| configuration | combiner | clean FA | alerts/h | masq of 5 | injected of 6 |
|---|---|---|---|---|---|
| all | max | 3.20% | 115 | 5 | 6 |
| only L1 / L3c / L3d | own 1% | 4.73% / 0.80% / 0.00% | 170 / 29 / 0 | 0 / 3 / 2 | 6 / 3 / 2 |
| all but L1 / L3c / L3d | noisy_or / noisy_or / max | 1.16% / 4.73% / 3.20% | 42 / 170 / 115 | 5 / 2 / 3 | 5 / 6 / 6 |

Every combined false alarm comes from L1 (post-verdict description, `s7_diag_test.json`: L1 is the maximum layer in 44 of 44 alarms; clean windows above the 0.99 ECDF level of the bus-load rule: 37, of the period rule: 17); L3c alone contributes 0 of the combined alarms. The combiner `max` was chosen by the pre-registered auto-selection on validation (held-out-half detection max 0.994, noisy-or 0.945, logistic 0.943); the all-but-L1 row (1.16% / 5 of 5 / injected 5 of 6) is an ablation reported for information: adopting it now would be a choice made on the test. Sharing one 1% budget across three layers lowers per-layer sensitivity (max_speedometer_masquerade window recall 100% for L3c alone, 5% combined) but not capture-level detection.

## 4. Other data sets (L1 only: no DBC exists for Car-Hacking / D11, so L2b / L3 cannot run; numbers are the S2 ones, deterministic, re-read not re-scored)

Car-Hacking (test blocks, window level, 1% budget): DoS 100%, Fuzzy 100%, RPM 99.5%, Gear 99.5%, clean FA 1.0% [0.0, 2.2] (36/h); L1 rules each alone 2-92%, all-but-period 90.3%. D11 (can-train-and-test, 16 test subsets, 175 attack files, 95% bootstrap over files): regime A zero-shot (thresholds from the training vehicle) on KNOWN vehicles 88/88 files, window recall 98.4%, clean FA 1.63% [1.17, 2.16]; on UNKNOWN vehicles 87/87 files detected but **clean FA 100%** (ID/DLC/period profiles are vehicle-specific). Regime B (30 s profile + 30 s thresholds on the target vehicle, scored from 60 s): known 2.76% [1.77, 3.97], **unknown 3.28% [2.48, 4.11]** at recall 98.9% (budget 1%; one cell Subaru test_01 20.1%). L4 (S6) adds nothing on top of L1 here (D11: 1 of 32 cells; Car-Hacking L1 already 4/4); not in the stack.

## 5. NOT met / NOT caught

- **False alarms.** Final ROAD test clean-window FA 3.20% > 2% (CI includes 2%), extended_short 6.7% > 5%, **115 false alerts/h against the fixed WP2 target of <= 1/h** (v2 timing model: 0). History of the clean-window FA on the ROAD test: L1 3.4% (S2) -> L2b 38.1% (S4) -> L3 7.6% (S5, highway drive 20.4%) -> final stack 3.20% (highway drive 1.7%). The remaining false alarms are the specification rules (bus load, period) on legitimate traffic bursts of the extended / benign-anomaly drives; they never saw those events in the 10 folds.
- **Unknown vehicles.** Zero-shot calibration fails (100% FA, S2, S6); on-vehicle calibration costs a clean minute and still gives 3.3% FA (budget 1%) from 240-300 clean windows.
- L2b (relations-only) failed the LOCO rule (one road block alarms in 100% of its windows for linear-only sets, 6.4-6.6% for sets with rate / value checks, limit 5%); on the test, K3 alone: 4/5 masquerade at 5.38% FA.
- Masquerade types not covered: consistent multi-signal rewrites; adaptive attackers who know the predictors. ROAD attacks are real but one vehicle, 3 instances per attack.
- Reverse driving: 0 of 51 windows alarm, but 51 windows cannot bound the rate below 52%.

## 6. Negative results

L2a clock skew (CIDS, S3): masquerade 0/5, FA 3.9% / 35%; attacker-vs-ECU rate difference about 60 ppm is below the jitter of the logged timestamps (12-28% of the period). L4 retrained v2 timing/payload models (S6): no gain on ROAD validation, Car-Hacking or D11 (1 of 32 cells); window-level shuffled control failed 11 of 12; payload false alarms on the reverse bit 5.9%. L2b generic discrete checks: 38% FA (S4). Rule-of-thumb confirmed: thresholds from few captures of one regime do not transfer (S2-S5); the S7 fix was to make the predictor scales conservative over BOTH regimes (inner folds include the road blocks): road-block FA 24% -> 0.2% in LOCO, and the S5 alarms on the highway test drive (20.4% of its windows) disappear (0 L3c alarms; its 1.7% are L1).

## 7. Artefacts and pitfalls

- ROAD masquerade captures are EDITED COPIES: the legit frames of the injected ID are deleted after the fact, injected frames keep real attacker timestamps; always the same split as the original. Accelerator captures: no injected frames, injection precedes the capture.
- D11: 62 of 236 files are byte-identical copies (174 distinct); timestamp inversions up to -7.9 ms next to injected frames (the sign of dt is never a feature); `set_01/test_04` is a Traverse, not a Silverado (label error in the readme); vehicles are known per set only.
- Car-Hacking: injection is software-timed and sits in the first 75-80% of each file; test blocks are interleaved, so delay fields are not onset delays and "other normal" windows border attacks.
- The `anonymized.dbc` names every signal Unknown_k: meaning (wheels 0x6e0.0-3, speedometer 0xd0.5, reverse bit 0xd0.2, coolant 0x4e7.1, gear copies 0x295.0 / 0xc0.0 / 0x274.14) was derived from the train attack metadata and correlations; the wheel speed unit is assumed (0.01 km/h).
- Winsorised scores create ties at the quantile (tie-safe thresholds above the cap alarm nothing); an unbounded CUSUM of a session offset grows without limit (S5).
- Highway blocks are time blocks of ONE drive, a proxy for a new road session: the test highway drive (another session) confirmed it (1.7%), but this is one session.

## 8. Test over-exposure and data limits

The ROAD test captures were scored in S2, S3, S4 (verdict + R1), S5 and here: **this is the 6th exposure**; no S7 choice used a test number (selection on LOCO + train/val, frozen in `s7_frozen.json` before any test table was built), but the test has stopped being independent for the project and numbers should be read as optimistic by an unknown amount. Car-Hacking test blocks were scored in S2 (L1), S3 (L2a) and S6 (L4), D11 test subsets likewise (the supervisor note says "second exposure"; by the reports it is at least the fourth). Data: one vehicle (ROAD), 3 attack instances per type, 4 clean test captures (1,375 clean windows, 10 independent units), no DBC for Car-Hacking / D11, no labelled holdout for the accelerator attack.

## 9. Frozen deployable CAN domain output (for WP6 / WP7)

`can/domain.py`; fitted object `results/WP2/s7_domain/` (`domain.pkl` 1.7 MB, `domain.json`; fixtures `example_evidence_correlated_signal.json`, `example_can_motion_estimates.json`); optional ablation domain `s7_domain_l2b/`.
```
d = CanDomain.load("results/WP2/s7_domain")                      # L1 + L3c + L3d, combiner "max"
comb, per = d.score_capture(t, ids, dlc, B, name="car0")        # t (s, recorded order), ids, dlc, B (n x 8 uint8 payload); whole capture or stream prefix
est = d.motion_estimates(t, ids, dlc, B)                         # MotionEstimate list
```
Evidence: one per scored 1 s window (the window is emitted when its second has passed; the first second is not scored), `domain="can"`, `layer="combined"`, `name="can.combined"`, `t` = window end (s), `score` in [0, 1] = max of the ECDF-calibrated layer scores, `alarm` = score >= 0.99304 (1% of pooled normal windows; expect 1-3% on unseen sessions, 6.7% on the worst test capture), `reason` = the physics sentence of the firing layers plus the culprit signal (e.g. "a signal disagrees with the prediction ... (signal 0x6e0.3)"), `details` = {method, layer_scores, culprit_signal}, `sample_id` = "capture/second". Per-layer Evidence (`L1`, `L3c`, `L3d`) with the layers' own 1% thresholds in `per`. Causal (scores of complete windows do not change when later frames arrive; tested). MotionEstimate: `source="can"`, one per second, `speed` = mean of the four wheel speeds (0x6e0) held at the end of the second x 0.01 km/h -> m/s (**unit assumed, factor 1 in the anonymised DBC: calibrate against GPS or LiDAR speed in WP6**), unsigned, `sigma` = max(0.3 m/s, 3% of speed), `yaw_rate` and `displacement` None. It is a CLAIM that a CAN attacker who rewrites 0x6e0 controls (the correlated-signal attack does exactly that), to be cross-checked against GPS / LiDAR motion. The models are specific to the ROAD vehicle and its DBC; another vehicle needs its own clean calibration.
