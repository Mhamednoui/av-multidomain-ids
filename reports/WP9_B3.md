# WP9 B3: V2X seen-attack benchmark (VeReMi Extension, D12)

Date: 2026-11-05    Worker: sonnet (high, T3)

## Summary (<= 40 lines)
- Unit: one received message, 20 classes (genuine + all 19 attack types). D12 is ONE 24 h simulation: no run / file / receiver id exists, so "split by simulation run" is realised as the 1800 s time block
  (no two parts ever have senders on air at the same time; cross-sender features computed inside a part). locks/WP9_veremi.json, committed before training: 23 train / 7 val / 8 test blocks
  (1,358,905 / 325,119 / 564,466 messages; 10,612 / 2,636 / 4,451 senders). Dedup: 0 exact duplicate rows (nothing dropped; repeats are attacks).
- H31: locks/H31.json reuses the 10 WP5 test blocks of VeReMi (S7 scores them). B3 uses none of them, not even for training: overlap = 0 (asserted). The B3 test blocks were WP5 train/val blocks, never scored as a test set
  (exposure 1, results/WP9/B3_exposure.json); everything (also the 3 Kalman noise parameters) was refit on B3 train.
- Models (validation macro-F1 at the 1% genuine budget): XGBoost / RF on v3 plausibility features (L1-L3 residuals, Kalman NIS/CUSUM, beacon rate, windows), per-sender-only variant, raw message fields, and both together;
  chosen xgb_D_noT_d6 (33 features: plausibility + raw fields, no track descriptors), val macro-F1 0.917. Raw fields alone: 0.526; plausibility alone: 0.849; the combination wins. v3 L4 layer reused as a binary reference.
- Test scored ONCE (rule fixed in notes/WP9_B3.md before any fit). Acceptance: R1 (bar) MET, R2 (all classes) MET. Thresholds were fixed on validation; test macro-F1 equals validation macro-F1 (0.917 / 0.917).

| Protocol / cell (message level, test) | Our result [95% CI over 8 test blocks] | B0 bar (protocol) | Verdict |
|---|---|---|---|
| All 19 attacks + genuine, block split, 1% val budget (H) | macro-F1 0.917 [0.911, 0.923]; binary F1 0.968; precision 0.984; recall 0.953; FPR 0.0104 [0.008, 0.012]; AUC 0.983 [0.980, 0.984]; mean alarm recall 0.957 | none comparable (published numbers are DoS-family only) | R2 MET (>= 0.80 at FPR <= 2%) |
| same, val-F1-optimal threshold (S, secondary, reported after H, same scoring) | macro-F1 0.918 [0.911, 0.924]; binary F1 0.972; precision 0.997; recall 0.947; FPR 0.0017 | same | informative |
| same, plain argmax (G) | macro-F1 0.916 [0.909, 0.922]; precision 0.999; recall 0.944; FPR 0.0005 | same | informative |
| DoS family (13, 14, 15, 18, 19), prevalence-matched 70/30, H | F1 per type 0.995 / 0.996 / 0.996 / 0.994 / 0.992; pooled 0.995 [0.994, 0.996]; recall 0.997-1.000 | F1 0.93-0.998, 70/30 split inside each dataset, per vehicle, dedup not stated (Baharlouei 2024; Asensio-Garriga as cited: 99.06 DoS, 99.77 DoSRandom, 97.97 DoSDisruptive, 94.46 Random Sybil, 92.56 Disruptive Sybil) | R1 MET; equal to / inside the bar range, protocol stricter (block-disjoint); no "better" claim |
| DoS family, natural mixed-CSV prevalence, H | F1 per type 0.928 / 0.925 / 0.935 / 0.895 / 0.890; pooled 0.982; precision 0.80-0.88 (1% FPR on 59% genuine traffic) | - | shows what the prevalence matching changes |
| DoS family, natural prevalence, S | F1 0.986 / 0.987 / 0.988 / 0.981 / 0.977; pooled 0.996 | - | informative |
| Sender level (k = 16 alarms chosen on validation) | genuine-sender FA 0.008 [0.003, 0.013]; mean detection over 19 classes 0.968 [0.961, 0.976] | WP5 v3 stack sender level 86.6% (13 seen classes, different split) | informative |
| v3 L4 reused as is (binary, rate-free residual features, scored rows only) | binary F1 0.754; recall 0.615; AUC 0.654; Sybil DoS 18 / 19 recall 0.000 / 0.005 | - | weak on the full stream (first messages, repeats, rate classes unscored) |

- Per-class alarm recall at H: 16 of 19 classes >= 0.93 (DoS family >= 0.997; random/const speed and position 0.997-1.000). Weak: ConstPosOffset (2) 0.633 [0.542, 0.693], EventualStop (9) 0.829 [0.786, 0.857], GridSybil (16) 0.810 [0.771, 0.829], DataReplaySybil (17) 0.935 but class-correct only 0.727.
  Class 12 (DelayedMessages) 1.000 is the (0,0) placeholder artefact (placeholder rows 1.0, other rows 1.0): flagged, macro-F1 without it 0.913.
- Controls (validation, pass band 0.42-0.58): row-level shuffled labels 0.496 PASS (chosen unit); v3 reference on scored rows 0.489 PASS (all rows 0.333, unscored rows score 0). Within-block sender-label permutation 0.377 and
  proxy-only (time, sender id, pseudonym id) 0.638: FAIL as written. Post-hoc diagnostics: time alone 0.508, sender id alone 0.508 (no leak), pseudonym id alone 0.629 (its ordinal = pseudonym churn, never a feature);
  sender-level permutation nulls of the same model give 0.34-0.52 over 4 seeds x 2 schemes (the band is too narrow for group-permutation nulls). No feature-importance red flag (cusum_hi 0.16, rate features 0.08 each; raw x,y 0.037; track descriptors absent).
- Not claimed: any "best"; transfer to another map (raw x, y, speed carry the single LuST map; the 63% on ConstPosOffset needs it); real-traffic behaviour (the WP5 V2AIX results say thresholds must be re-fitted).

## Goal of the step
Seen-attack-type benchmark for V2X misbehaviour detection, leak-free, comparable to the B0 bar (VeReMi Extension DoS family, 70/30, F1 0.93-0.998).

## Acceptance rule (written before results: notes/WP9_B3.md, "pre-registration", 2026-11-04)
R1: prevalence-matched F1 of each of the five DoS-family types >= 0.93 at the 1% validation budget with test FPR <= 2%. R2: mean alarm recall over the 19 classes >= 0.80 at FPR <= 2%.
Both met (see table). Selection rule, operating points, controls and stop rule were also fixed there; the only stop condition (feature-importance red flag) did not occur.

## What was done
- Code: tools/WP9_B3_lock.py (dedup, split lock), WP9_B3_build.py (Kalman refit on B3 train genuine + v3 L4 feature table + raw fields), WP9_B3_lib.py (block-additive metrics, block bootstrap), WP9_B3_fit.py (14 candidates + selection + v3 reference),
  WP9_B3_controls.py, WP9_B3_control_seeds.py and WP9_B3_proxy_diag.py (post-hoc diagnostics), WP9_B3_test.py (single scoring, refuses to run unless selection and controls are committed), WP9_B3_report.py; tests/v2x/test_wp9_b3.py (6 pass).
- Results: results/WP9/B3_selection.json, B3_parts/, B3_controls.json, B3_control_seeds.json, B3_proxy_diag.json, B3_test.json, B3_tables.md (all tables, generated), B3_exposure.json, B3_tracker.json.
  Scores (rule 6): results/WP9/scores/B3/val_chosen.npz and test_chosen.npz (y, s, class, argmax, sender, pseudonym, block, t, row kind, v3 reference score; force-added, 5.5 MB).
- Amendment before any fit: RF size reduced (min_samples_leaf 20, max_samples 0.3). Journal lines in notes/WP8_journal.md (step B3).

## Results
Full tables (per-class recall with CIs, DoS subset, sender level, row kinds, candidates, controls): results/WP9/B3_tables.md.
Row kinds at H: genuine alarm rate 0.87% on scored rows, 19% on first-message / gap rows (3,117 genuine rows); 36,502 exact-repeat rows are all attacks. Candidate table (validation): A_plaus 0.849, A_noT 0.830, per-sender-only 0.805, raw only 0.526, D_all 0.917-0.919, D_noT 0.917-0.918, RF D_all 0.901.

## Ablation row(s)
Feature groups (validation macro-F1 at 1%): plausibility 0.849 -> + raw fields 0.917; per-sender-only (no cross-sender overlap / birth density) 0.805 vs 0.849 with them; without track descriptors 0.830 vs 0.849 (A) and 0.917 vs 0.917 (D): descriptors not needed once raw fields are in.
Reused v3 L4 layer (rate-free residuals, scored rows only) 0.60 mean alarm recall: the supervised gain over v3 in this seen-attack protocol comes from rate, windows and raw fields, not from the residual set alone.

## Problems, surprises, open questions
- The pre-registered within-block permutation and proxy-only controls fail as written. Time and sender id are clean; the pseudonym id carries label information (pseudonym churn), and group-permutation nulls are not centred on 0.5.
  Evidence that the test result is not a memorisation artefact: test macro-F1 equals validation macro-F1, row-shuffle control is flat, the test blocks are disjoint in time. Evidence against complete safety: all parts share one simulation, one map and one day pattern. A different simulation (VeReMi NextGen / the per-type raw files) was not available.
- Raw x, y, speed make the model map-specific (ConstPosOffset 63% vs 0.8% in WP5 physics-only). Report as a dataset-specific number.
- Genuine first messages alarm 19% of the time at H (new identities); the 1% FPR budget hides this. Class 12 is trivially detected (artefact).
- The usage limit interrupted the work between selection and controls; resumed from the journal without redoing any finished fit; the test was scored once.

## Proposed next step
B5 final comparison with the other B-steps; optionally a B3b with an independent simulation (VeReMi NextGen / the per-type VeReMi Extension files) to replace the single-simulation caveat, and a map-free (no raw x, y) variant for transfer.
