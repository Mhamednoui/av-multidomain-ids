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
