# WP9 B1 notes (CAN benchmark track: Car-Hacking, ROAD, can-train-and-test)

## 2026-11-04 pre-registration (written BEFORE any B1 model was fitted or any test window scored)

### Units, splits, dedup
- Unit: 1 s non-overlapping window (label = injected-frame class inside; classes below) and the frame (causal features).
  Windows and features are built inside each split segment after the split (never across a boundary).
- Splits: results/WP2 splits reused as in notes/B0 proposal; locked in locks/WP9_{carhacking,road,d11}.json.
  Car-Hacking: v2/WP2 S1 100-block interleaved split + 1 s gap at each boundary between different parts; D02n normal_run first half
  val / second half test (pure benign). ROAD: WP2 capture split; coolant capture = unseen-family row. D11: splits_d11.json.
- Dedup: rows identical in (t, id, dlc, payload) dropped (first kept), counts in the lock.
- CORRECTION to B0_splits_proposal.md: in D11 test_03 / test_04 hold attack families ABSENT from train ("unknown attack"), so the
  seen-attack rows are test_01 (known vehicle) and test_02 (unknown vehicle); test_03 / test_04 are unseen-attack rows, reported
  separately and labelled so (the literature numbers for them are also "unknown attack"). Decided before training.

### Models (all choices on validation only)
- F: frame model, XGBoost multi-class on causal frame features (id, dlc, 8 bytes, dt_prev, dt_id, dt_id_ratio, n_id_win, n_unique_win,
  bytes_changed, same_payload; layout of the v3 L4 payload model, can/l4_features.py). Window score = 1 - min over frames of p(normal)
  (max attack probability); window class = class of the frame with the largest attack probability.
- W: window model on 1 s window features (generic ID-agnostic statistics, optional per-ID counts): XGBoost multi-class (W_xgb) and
  Random Forest (W_rf), variants generic-only / generic + id counts (feature set chosen on validation).
- E: ensemble = mean of the validation-ECDF-calibrated attack scores of the best F and best W (class from the more confident).
- Hyper-parameters: a small fixed grid (<= 6 configs) with early stopping on validation logloss; selection criterion =
  validation macro-F1 at the validation 1% false-alarm budget (threshold on validation normal windows), ties -> simpler model.
- Operating point of every reported number: alarm if 1 - P(normal) >= threshold set at 1% FPR of VALIDATION normal windows
  (Car-Hacking: block-normal + normal_run validation windows pooled); class = argmax over attack classes. Secondary column:
  plain argmax (no budget) macro-F1 for literature comparability. FPR reported at the test set (not forced to 1%).

### Controls (pre-registered)
- Shuffled labels: refit each selected learned unit (F, W_xgb, W_rf) on training labels permuted at random (seed fixed); score validation.
  Pass if attack-vs-normal AUC at the unit's own level is in [0.42, 0.58] (frame level for F; window level for W). The window-max
  aggregation of F is biased by frame count (WP2 S6 finding); its window AUC is reported but not the pass criterion.
- Feature importance (total gain): report top 5. Red flag = a feature above 50% share that is a capture/time proxy (none is in the
  feature set: no absolute time, no capture id, no row index) -> would be "stop and report". Dominant physical features (id, dt_id_ratio,
  n_id_win, payload bytes) are described, not stopped; an ablation without raw id is run for F as an extra row.

### Acceptance rules (the bar is B0, notes/WP9_brief.md)
- Car-Hacking: MET if on test (block split) attack recall >= 0.98 at test FPR <= 1.5% (block-normal windows) AND 5-class macro-F1 >= 0.95.
  Literature numbers are random splits (leaky), so the comparison is labelled "reported under a random split".
- ROAD: no leak-free published number; the comparators are Guerra et al. multiclass mean F1 0.32 (LCCDE) and DCNN 0.65-0.75 (possibly
  leaky) and our WP2 rule-based stack (masquerade 5/5, window FA 3.2%). MET if 10-class window macro-F1 >= 0.75 on test and per-family
  recall (alarm) >= 0.8 for fabrication and masquerade families at test FPR <= 2%; otherwise reported as NOT MET with the per-class table.
  coolant row (unseen) reported separately, no threshold.
- can-train-and-test: MET if test_01 (set_01) attack-class F1 >= 0.98 at FPR <= 2%, mean over sets 01..04 reported with spread; test_02
  (unknown vehicle) reported without a threshold (the ID-specific features are expected to hurt); test_03 / 04 unseen rows reported.
- Test is scored once per dataset (per D11 set), after the selection JSON results/WP9/B1_<ds>_selection.json is committed.

## 2026-11-04 execution log and results (all numbers: results/WP9/B1_*.json, B1_tables.md)
- Locks (committed before training): locks/WP9_carhacking.json (4 files + normal_run; 0 exact duplicate rows), locks/WP9_road.json (41 usable captures,
  1,435 duplicate rows of 27.4M dropped; accelerator x4 excluded; coolant x2 = unseen), locks/WP9_d11.json (4 sets, 1 duplicate row total).
- Bugs found and fixed before any test number was seen: (1) float32 vs float64 threshold comparison made FPR 1.06% instead of <= 1% (decide() now float64, unit test added);
  carhacking fit re-run (run 1 log kept as B1_fit_carhacking_run1_buggy_decide.log). (2) XGBoost Booster loaded from file used all trees instead of the early-stopping best
  iteration; the validation-reproduction guard in the test script caught it (ROAD), fixed with iteration_range. (3) test script group-array and frame_matrix argument bugs
  crashed before any output. No test metric existed before the final run of each dataset.
- Selection (validation, results/WP9/B1_<tag>_selection.json): Car-Hacking W_rf_generic (all candidates tie at val macro-F1 0.995-0.997, simplest chosen);
  ROAD Fb (frame XGBoost depth 9, 51 trees; val macro-F1 0.873 vs 0.53 best window model); D11 set_01 W_xgb_a_ids, set_02 E, set_03 F_noid, set_04 E.
- Feature importance: no feature above 50% share, none a capture/time proxy; dominant features are bus-rate / timing (dt_id_ratio, n_id_win, nid_max) and payload bytes: no red flag.
- Controls: global shuffled-label control passes for Car-Hacking, fails in the band [0.42,0.58] for ROAD F (frame AUC 0.28), many D11 units (0.16-0.86): the noise model's score is
  not flat on outlier regions (WP2 S6 saw the same). Added control2 (labels permuted inside each training capture / block run): validation AUC 0.88 Car-Hacking, 0.88 ROAD,
  0.72-0.88 D11 window units, 0.44-0.81 frame units. So the regime of a capture / block predicts "attack-bearing" across captures. Regime diagnostic on test (B1_regime.json):
  restricted to the SAME segments (normal windows of attack-bearing captures) the detectors still separate: AUC 1.000 Car-Hacking, 0.932 ROAD, 0.99-1.00 D11 test_01 (sets 01, 03, 04), 0.93 set_02;
  but ROAD FPR on normal windows inside attack captures is 13.8% vs 1.7% on ambient captures: part of the ROAD false-alarm budget problem is windows next to attacks.
- Acceptance verdicts (rules above): Car-Hacking MET; ROAD NOT MET (macro-F1 0.829 >= 0.75 holds, but test FPR 3.2% > 2% and reverse_light_on masquerade recall 0, reverse_light_off masquerade 0.48);
  D11 NOT MET at the 1% budget (set_01 test_01 window attack-F1 0.723 < 0.98; mean over sets 0.80); unknown vehicle (test_02 / 04) fails completely (FPR 100%, AUC 0.56-0.90).
- Post-hoc (declared after seeing budget numbers, not an acceptance basis): validation-F1-optimal threshold: D11 test_01 F1 0.964 / 0.571 / 0.985 / 0.979 (sets 01..04).
- Limitation to carry to B5: the literature unit is the frame / short window; our unit is the 1 s window (>= 1 injected frame). Frame-expanded metrics (B1_frames.json) are poor because
  a flagged window flags all of its frames. A per-frame detector (F models) was validated but not scored on test (the selected model was a window model for Car-Hacking).
