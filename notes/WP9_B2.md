# WP9 B2 notes (network benchmark, seen attack types, leak-free)

## 2026-11-04 Design and acceptance rules (written BEFORE any model result)
Bar (B0): Moczkodan & Ragab arXiv 2606.11098 (read the HTML v2, 2026-11-04):
- the headline 0.89 = Transformer macro-F1 on the NON-PADDED SUBSET of 20-flow windows (windows with 20 genuine flows only), a filtered evaluation;
- the whole-test leak-free numbers: group-by-5-tuple 80/20: RF (last flow of window, 13 classes, 76 numeric features, no ids/ports/timestamp) macro-F1 0.778,
  accuracy 0.9979; LSTM 0.753; GRU 0.736; their time split (first 80% / last 20% of the week) is degenerate (2 classes in test);
- no flow dedup, no label correction (original labels), 13 of 15 classes.
So the comparable bar for flow-level models is 0.778 (group split, all test windows) and 0.89 (non-padded subset, not leak-free-comparable); both are quoted.

Protocols per dataset and label set (all on deduplicated flows, rows with the same feature vector and label kept once, conflicting-label rows dropped, as WP4):
- T  time-block: each period (attack window / benign stretch, WP4 definition) cut in time order train 0-50% | gap 1 min | val 50-65% | gap | test 65-80%.
     The last 20% of every period (= the v3/WP4/WP8 D10 test rows) is NOT used by B2 at all (reserved). B2 test rows overlap v3 VAL rows (60-80% region) but no v3 test rows;
     no v3 model is reused (all models are retrained on the B2 train part).
- G  5-tuple group (Moczkodan): all flows with the same (src ip, dst ip, src port, dst port, protocol) go to the same side; deterministic hash of the 5-tuple, 70 / 10 / 20 (train/val/test)
     over the whole week (all days pooled). Needs IPs/ports.
- B  block group (stricter than G, my addition): blocks of 5 minutes within a period; blocks assigned to train/val/test by a hash (70/10/20); flows within 60 s of an edge between blocks of different parts are dropped.
     Conversations cannot straddle (a conversation lasts < 2 min in these sets except slow DoS, which are dropped near edges).
Features: 76 CICFlowMeter columns without ids/ports/time (D23 names); the 60 "clean" subset (WP4 L3/L4: also no TCP-stack fingerprints) as an alternative. Choice on validation.
Models: XGBoost (multiclass, class-weighted 0.5 power, random search 6 trials on val macro-F1, early stopping) and RF (balanced subsample), both n_jobs 4, chosen on validation macro-F1.
Metric definitions: primary macro-F1 over BENIGN + attack classes with >= 20 test flows (support rule fixed now); sensitivity row: all classes with >= 1 test flow.
  FPR = benign test flows predicted as any attack (argmax). AUC = binary attack-vs-benign (score 1 - P(benign)) and macro one-vs-rest. Per-class recall. Binary detection at 1% val benign FA (RULES 5.5).
  95% CI: bootstrap over 10-minute test blocks (clusters), 1000 resamples.
Controls: shuffled-label control (labels permuted in train, same config, scored on VALIDATION only, 3 seeds): acceptable if macro-F1 stays below benign-prevalence baseline + 0.05 and AUC <= 0.55.
Red flag (stop and report): one feature > 40% of total gain, or a port/timestamp-like proxy (ports and times are not features; Init-Win bytes and TTL-like columns are checked via the 60-clean variant).
Acceptance: B2 is a measurement, not a target; a result below the bar is reported as is. Test is scored once per (dataset, label set, protocol) with the model selected on that protocol's validation.

## 2026-11-04 clarifications before any model result
- Splits locked and committed: locks/WP9_D10o.json (original labels), locks/WP9_D10e.json (Engelen 2021 corrected labels; "Attempted" flows relabelled BENIGN as the authors recommend,
  counts in results/WP9/B2_build_D10e.json). Corrected set download: https://intrusion-detection.distrinet-research.be/WTMC2021/Dataset/dataset.zip (no login, 333,841,436 B,
  sha256 4d535da19795d85376ae1397d161329e3b06fc47d9a5a68cd9be2cd7ecee0f2a, folder ../data_extra/D10e_cicids2017_wtmc2021/, read with python -I).
- Eligible classes for macro-F1 (both for selection on val and for the reported test): class has >= 20 flows in the train part AND >= 20 in the evaluated part. Classes that fail are listed, not averaged.
- Candidate models (fixed now): XGB depth 6 / 76 features, XGB depth 6 / 60 clean, XGB depth 10 / 76, RF / 76, RF / 60 clean. Train = all attack flows + 250k random benign flows (seed 0);
  val and test are complete. Selection = best val macro-F1 (eligible classes). The selected config is retrained on train only and scored once on test.
- Shuffled-label control (3 seeds, on VALIDATION only; the test is never touched by it): pass if val AUC <= 0.55 and val macro-F1 < half of the real val macro-F1.
- Bar for comparison: group-split RF 0.778 (13 classes, all windows) and the 0.89 non-padded-subset headline (not like for like).
