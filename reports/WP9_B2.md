# WP9 B2: network benchmark, seen attack types, leak-free (CICIDS2017, CSE-CIC-IDS2018)

## Summary (all numbers from results/WP9/B2_summary.json, generated tables in results/WP9/B2_tables.md)
- Setting: "seen attack types, standard dataset" (every class is in train). Flow-level multiclass models (XGBoost / random forest on the 76 CICFlowMeter columns, no IPs, ports, time).
  Exact duplicates and conflicting labels removed first. Splits locked before any training: locks/WP9_D10o.json, WP9_D10e.json, WP9_D23x.json. Each test part scored once (results/WP9/B2_exposure.json).
- Label sets: CICIDS2017 corrected labels (Engelen et al. 2021, downloaded without login, sha256 4d535da1...) AND original labels (WP4 table); CSE-CIC-IDS2018 corrected (Liu et al. 2022 release,
  sha256 7f7b6f80...; the original D23 CSVs have no IPs on 9 of 10 days, so no 5-tuple group split is possible there). "Attempted" flows relabelled BENIGN (authors' advice).
- Protocols: T = time block per period (last 20% of every period reserved, so no overlap with the v3 D10 test), G = 5-tuple group split (Moczkodan and Ragab protocol, 70/10/20), B = 5-min block group (stricter, my addition).
- Metric: macro-F1 over classes with >= 20 flows in train and test (rare classes listed, not averaged), FPR, AUC, per-class recall; 95% CI = bootstrap over 10-minute test blocks.

| dataset, labels | protocol | model (picked on val) | test flows | classes | macro-F1 [95% CI] | all present classes | FPR [CI] | AUC | control |
|---|---|---|---|---|---|---|---|---|---|
| CICIDS2017 original | time block | xgb_d6_f76 | 296,975 | 11 | 0.838 [0.719, 0.905] | 0.709 | 0.078% [0.059, 0.099] | 1.000 | pass |
| CICIDS2017 original | 5-tuple group | xgb_d10_f76 | 427,025 | 12 | 0.894 [0.832, 0.926] | 0.863 | 0.118% [0.097, 0.142] | 1.000 | pass |
| CICIDS2017 original | block group | xgb_d6_f76 | 413,657 | 12 | 0.876 [0.697, 0.952] | 0.851 | 0.079% [0.053, 0.109] | 1.000 | pass |
| CICIDS2017 corrected | time block | xgb_d6_f76 | 218,975 | 9 | 0.918 [0.865, 1.000] | 0.812 | 0.006% [0.001, 0.013] | 1.000 | pass |
| CICIDS2017 corrected | 5-tuple group | rf_c60 | 319,979 | 10 | 0.996 [0.977, 0.998] | 0.948 | 0.008% [0.004, 0.014] | 1.000 | AUC rule FAIL (RF) |
| CICIDS2017 corrected | block group | xgb_d6_f76 | 261,480 | 11 | 0.937 [0.896, 0.995] | 0.906 | 0.007% [0.002, 0.013] | 1.000 | pass |
| CSE-CIC-IDS2018 corrected | time block | rf_f76 | 947,073 | 11 | 0.926 [0.862, 0.986] | 0.880 | 0.056% [0.048, 0.063] | 1.000 | AUC rule FAIL (RF) |
| CSE-CIC-IDS2018 corrected | 5-tuple group | rf_f76 | 1,523,412 | 13 | 0.945 [0.918, 0.961] | 0.886 | 0.063% [0.057, 0.069] | 1.000 | AUC rule FAIL (RF) |
| CSE-CIC-IDS2018 corrected | block group | rf_f76 | 1,004,186 | 12 | 0.945 [0.911, 0.959] | 0.886 | 0.065% [0.054, 0.078] | 1.000 | AUC rule FAIL (RF) |

Comparison with the B0 bar (Moczkodan and Ragab, arXiv 2606.11098, read in the HTML version for this step):
| source | protocol | classes / labels | macro-F1 |
|---|---|---|---|
| bar, headline | Transformer, random-style 20-flow windows, NON-PADDED subset only (windows with 20 real flows) | 13 classes, original labels, no dedup | 0.89 (not a whole-test number, not leak-free comparable) |
| bar, whole test | RF on last flow, group-by-5-tuple 80/20, windows built after the split | 13 classes, original labels, no dedup | 0.778 (LSTM 0.753, GRU 0.736) |
| bar, time split | first 80% / last 20% of the week | 2 classes survive in test | degenerate, no number |
| ours, same labels, same group protocol | 5-tuple group, dedup, flow level | original labels, 12 classes with >= 20 test flows (0.863 over every class present) | 0.894 [0.832, 0.926] |
| ours, strictest | 5-min block group / time block | original labels | 0.876 / 0.838 |
| ours, corrected labels | G / B / T | corrected labels | 0.996 / 0.937 / 0.918 |
| CSE-CIC-IDS2018 | no leak-free published bar | corrected labels | 0.945 / 0.945 / 0.926 (first such numbers we know of) |

Read this table with care (more in Caveats): our classes differ from the bar's (we exclude classes with < 20 test flows, they keep 13), we deduplicate (they do not), the corrected-label sets contain far
fewer hard examples (Web attacks drop to 12-151 flows), and every split here is in-distribution (the same attack campaign appears on both sides). They are seen-attack numbers, not generalisation to new attacks.
- Shuffled-label control (registered: 3 seeds on validation, pass = max AUC <= 0.55 and mean macro-F1 < half the real one): macro-F1 passes everywhere (0.08-0.14 vs 0.82-0.99). The AUC criterion FAILED for the 4 units
  whose selected model is a random forest (shuffled-label RF reaches AUC 0.56-0.67). An extra XGBoost control (validation only, after the fact) gives AUC 0.50-0.52 on CICIDS2017 but 0.52-0.60 on 2018, so the 2018 rows are a density-structure
  effect (below), not only an RF effect. Registered verdicts are kept as FAIL; the label-dependent evidence (macro-F1 0.08-0.11 vs 0.93-0.95) is clean.
- No red flag in feature importance: top feature share 5-20% (never a port or time: they are not features). Init window bytes (a TCP-stack fingerprint) is the top RF feature on 2018 (5%) and XGB top on D10o (9%).
- Problems: bootstrap bug found after the first test result (see below, fixed, CIs recomputed from saved scores, no test rescoring); 2018 benign flows are sampled 1-in-10 and carry weight 10.

## Method
- Data: D10o = WP4 cleaned CICIDS2017 table (2,233,825 flows, original labels, dedup 21.1%, WP4 counts). D10e = Engelen et al. 2021 CSVs (WTMC; 2,100,814 flows, 386,698 exact duplicates = 18.4%, 226 conflicting, 1,713,890 kept;
  9,144 "Attempted" flows relabelled BENIGN, per-family counts in results/WP9/B2_build_D10e.json). D23x = CSECICIDS2018_improved.zip (63,195,145 flows, 18,065,136 duplicates = 28.6%, 142 conflicts, 306,237 attempted flows relabelled BENIGN;
  results/WP9/B2_build_D23x.json). D23x keeps all attack flows and a hash-selected 1-in-10 benign sample (identical vectors share one fate, so dedup on the sample equals dedup on the full data); benign flows weigh 10 in every metric and in the validation threshold.
- Splits: tools/WP9_B2_splits.py (definitions in the file header and notes/WP9_B2.md, written before any result). T: per period (WP4 attack-window periods) train 0-50%, val 50-65%, test 65-80%, 1-minute gaps, last 20% reserved (never used).
  G: hash of the 5-tuple (CICFlowMeter Flow ID for 2018). B: 5-minute blocks permuted by hash, 1-minute gaps at part edges. Lock files carry per-part counts and the sha256 of the part arrays.
- Models (fixed before results): XGBoost depth 6 (76 or 60 "clean" features), XGBoost depth 10, random forest (76 or 60 features). Train = all attack flows (2018: at most 60,000 per class) + 250,000 random benign flows; class weights (frequency^-0.5).
  Choice = best validation macro-F1 (tools/WP9_B2_run.py: stages cand / select / control / test; test stage refuses to rescore). The v3 L4 layer (binary XGBoost) is the same family but cannot give a multiclass macro-F1, so it was not reused as is;
  flow-window features of the bar paper were not built (optional).
- Test overlap with the v3 / WP8 D10 test (results/WP9/B2_exposure.json): D10o time block: 0 rows in the v3 test, all 296,975 in the v3 validation part (no v3 model reused, all retrained); D10o G: 90,068 test rows are v3 test rows; D10o B: 56,087.
  D10e and D23x are different flow extractions: no row identity with the v3 tables (same capture days for 2017).

## Results per class, caveats, files
Per-class recall with CI, precision, F1, AUC vs benign for every row: results/WP9/B2_tables.md. Points worth reading:
- Original labels: Bot recall 0.97 but precision 0.56 (G): benign-labelled beacon flows are label noise (WP4 finding); Web-BruteForce / Web-XSS recall 0.76 / 0.43 (indistinguishable from each other); PortScan precision 0.77.
  Corrected labels: those hard Web classes shrink to 151 / 27 flows and mostly fall below the support rule, which is a main reason the corrected-label macro-F1 is higher. Slow DoS (SlowHTTPTest) recall 0.20 in the corrected time block (35 test flows).
- 2018: Infiltration-NMAP (a port scan the improved labels name separately) recall 0.98-0.99 but precision 0.18-0.36 (benign scans); Infiltration (rare sub-types) recall 0.66-0.79 with wide CIs; all large DoS / DDoS / Bot / SSH classes near 1.0.
- Classes failing the support rule per row are listed in each *_test.json ("not_eligible"); Heartbleed (11 flows) is never evaluable.
- All three protocols are in-distribution. They show the seen-attack ceiling, they do not show detection of an unseen campaign (that is the v3 zero-shot track).
- Shuffled-label controls: the registered control fails the AUC rule for random forests. Extra evidence (validation only, written after the failure, registered verdict unchanged): CICIDS2017 corrected G, RF, 10 seeds: AUC mean 0.558 (sd 0.049), macro-F1 0.086
  (results/WP9/B2/D10e_G_control_extra.json); same unit with XGBoost: AUC 0.50 / 0.52 / 0.52; 2018 with XGBoost (3 seeds each): time block 0.52 / 0.54 / 0.55, G 0.55 / 0.54 / 0.58, B 0.52 / 0.55 / 0.60
  (results/WP9/B2/*_control_xgb_d6_f76.json).
  Hypothesis, not tested: on duplicate-rich data, dense attack clusters and sparse benign flows get different leaf-composition statistics even with random labels (class-weighted learners; large attack campaigns such as Hulk/HOIC dominate
  AUC and make it high-variance across seeds, sd 0.05). That uses no label information; the real models score macro-F1 0.84-0.996 and the control stays near 0.08-0.11, so it cannot explain the results, but the rows with a control above 0.55 carry the flag
  (CICIDS2017 corrected G; all three CSE-CIC-IDS2018 rows).
- Bootstrap fix: the first cluster bootstrap averaged eligible classes that were absent from a resample as F1 = 0 (D10o T interval [0.43, 0.83] excluded its own point 0.838). Fixed in tools/WP9_B2_report.py; all intervals recomputed
  from the saved scores by tools/WP9_B2_recompute.py (point estimates kept from the original float32 scoring; float16 score files differ by < 2e-3 in AUC).
- Not done: original-label CSE-CIC-IDS2018 (no IPs: no group protocol), flow-window features, leave-one-family-out (v3 track).

Files: tools/WP9_B2_{build,build23,splits,run,report,recompute,tables,exposure,ctl_extra,ctl_xgb}.py, WP9_B2_driver.sh; locks/WP9_D10o|D10e|D23x.json; results/WP9/B2/ (select, control, test json, parts/ candidate validation);
results/WP9/scores/B2/*.npz (val and test probabilities, float16, per protocol); results/WP9/B2_summary.json, B2_tables.md, B2_exposure.json, B2_build_*.json; logs results/WP9/logs/ (git-ignored); notes/WP9_B2.md.
Downloads: ../data_extra/D10e_cicids2017_wtmc2021/ (WTMC2021 dataset.zip, 333,841,436 B, sha256 4d535da19795d85376ae1397d161329e3b06fc47d9a5a68cd9be2cd7ecee0f2a) and ../data_extra/D23e_cse-cic-ids2018_improved_cns2022/
(CSECICIDS2018_improved.zip, 10,426,851,729 B, sha256 7f7b6f8065a88527bcb6e1579f088e1d0480a49903c5fd7e4e907ab238344f6e), both from intrusion-detection.distrinet-research.be (no login), read with python -I, 2018 zip never extracted.
