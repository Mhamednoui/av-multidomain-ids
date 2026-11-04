# WP9 B3: V2X (VeReMi Extension) seen-attack benchmark, notes

## 2026-11-04 pre-registration (written BEFORE any B3 model was fitted or any B3 test message scored)

### Data facts that shape the split (re-checked in tools/WP9_B3_explore*.py)
- D12 combined CSV = ONE simulated 24 h timeline: type = 4 for all rows, messageID is one global counter, sender ids grow with first
  message time (step 6), 24,663 senders, 30% attackers, exactly 389-390 attacker senders per class 1..19. No run / file / receiver id.
  The original per-attack-type VeReMi Extension files are not in D12. So "split by simulation run" is realised as the closest available
  unit: the WP5 1800 s TIME BLOCK (sender assigned by first message; senders crossing a block end dropped; no sender of one block is on
  air with a sender of another block). Orchestrator decision 4 (not by sender) is satisfied: parts never coexist in time.
- B0 proposal said "reuse splits_veremi.json". locks/H31.json (reused.veremi_test) holds exactly the 10 WP5 TEST blocks (S7 scores them,
  exposure after S7 = 3). To keep H31 out of B3, B3 uses NONE of those blocks (not even for training): the other 38 blocks are re-cut
  60/20/20 (group_split, SEED 42) into B3 train 23 / val 7 / test 8 blocks (tools/WP9_B3_lock.py -> locks/WP9_veremi.json, committed
  before training). Overlap with H31 = none (asserted in the lock script). The B3 test blocks come from WP5 train/val blocks: they were
  never scored as a test set by any WP5 / WP8 step (exposure of the B3 test = 1), but WP5 trained / tuned the v3 L4 and its Kalman noise
  on those blocks. B3 therefore refits everything (including the 3 Kalman noise parameters) on B3 train genuine rows.
- Dedup: 0 exact duplicate rows, 0 duplicate messageID, 0 duplicate (sender, pseudonym, time). Repeated positions (replay, constant position)
  are attacks, kept.
- Cross-sender plausibility features (L2 overlap, L3 birth density) are computed inside one part only; parts never coexist in time.
  A per-sender-only feature set is in the grid as an ablation.

### Unit, labels, features
- Unit: one received message; track = sender + pseudonym stream (v2x/adapters.load_veremi). Label: 20 classes (0 genuine, 1..19 attacks).
  All 19 attack classes are trained and tested (orchestrator task: "all 19 classes"). Class 12 (DelayedMessages) is, in this CSV, a
  (0,0) placeholder artefact (WP5): it stays in every table with a flag, and an extra "without class 12" macro-F1 is reported.
- Feature table = v2x.l4.feature_table (v3 L4 code, causal per track: residual checks of L1-L3, Kalman NIS / CUSUM, beacon rate, 10-message
  window aggregates, birth density, track descriptors) + raw message fields. Sets (names fixed here):
  A_plaus (l4.FEATURES, 27) | A_noT (A minus track_pos, dt_prev, is_first) | B_plaus_ps (A minus overlap, birth_density, track_birth_density: per-sender only)
  | C_raw (x, y, speed, cos/sin heading, acl, pos/spd/acl sigma, dt_prev, track_pos, is_first, rate) | D_all (A + raw fields) | D_noT (D minus track_pos, dt_prev, is_first).
  Never a feature: sender, pseudonym, messageID, sendTime, block id.
- Kalman noise (sp, sv, sa): refit on B3-train genuine rows (l3.Tracker.fit, max 800 tracks) -> results/WP9/B3_tracker.json.

### Models and selection (validation only)
- Candidates: XGBoost multi-class (20 classes, hist, lr 0.1, depth in {6, 8}, early stopping on validation mlogloss, patience 20, max 300 rounds)
  on each of the 6 sets (12 fits) + Random Forest (100 trees, min_samples_leaf 5, max_features sqrt, max_samples 0.5, n_jobs 4) on A_plaus and D_all (2 fits).
  Alarm score s = 1 - P(genuine); predicted class = argmax over attack classes of the probabilities.
- Reference unit REUSED from v3: v2x.l4.L4Scored recipe (binary XGBoost on the S2_resid features, scored rows only, score 0 elsewhere; hyper-parameters
  d5_mcw1 as chosen in WP5 S6), retrained on B3 train with all 19 classes; binary only (no class). Reported in the same single test pass; it is not a selection candidate
  (binary, so it has no 20-class macro-F1). No sequence model: 10-message trailing windows of residuals are already in the features; a GRU would add training
  cost without a stricter protocol (a justification, not a result).
- Selection criterion: validation 20-class macro-F1 (classes present) of the decision "alarm if s >= thr_1%, class = argmax", with thr_1% = the 1% quantile
  from the top of VALIDATION genuine scores (tie-safe, float64). Ties (difference < 0.002): fewer features, then smaller depth, then XGBoost over RF.
- Operating points reported at test (thresholds fixed on validation before): (H) headline = 1% validation genuine-message budget;
  (S) secondary = threshold maximising validation binary attack F1 at natural prevalence, labelled "chosen on validation for max F1 (literature convention),
  reported after the headline, same single scoring"; (G) plain argmax (no budget), for literature comparability.

### Controls (pre-registered, run on validation, before test)
1. Shuffled labels (row-level permutation of train labels, seed 42) at every learned unit (chosen XGB/RF, V3 L4 reference): validation attack-vs-genuine AUC in [0.42, 0.58] = PASS.
2. Within-run label permutation: sender labels permuted among senders of the same 1800 s train block (labels stay constant inside a sender), refit chosen config, score validation;
   AUC in [0.42, 0.58] = PASS. Failing = a block / time regime or sender-specific content predicts the label.
3. Proxy-only model: XGBoost on (sendTime-in-day, sender id, pseudonym id) alone, train -> validation AUC in [0.42, 0.58] = PASS (otherwise those are proxies; they are not features).
4. Feature importance (total gain share, chosen model): RED FLAG (stop, write brief, no test scoring) if one feature > 50% or if the track-descriptor group
   {track_pos, dt_prev, is_first} or raw x, y > 50% together. Noted: Sybil classes 17-19 are single-message pseudonyms, so is_first / birth features legitimately carry them.

### Metrics (test, scored once)
- Message level, 20-class macro-F1 (classes present), per-class recall for the 19 attack classes (alarm recall = any alarm; class-correct recall also given), attack-vs-genuine
  precision / recall / F1, FPR on genuine messages, AUC (1 - P(genuine)), block bootstrap (8 test blocks, 1000 resamples, percentile 95% CI).
- DoS-only subset matching the bar: classes {13 DoS, 14 DoSRandom, 15 DoSDisruptive, 18 DoSRandomSybil, 19 DoSDisruptiveSybil}; for each type and pooled: genuine-vs-type F1,
  (i) natural mixed-CSV prevalence, (ii) PREVALENCE-MATCHED: genuine messages weighted so the sender mix is 70% genuine / 30% attack as in the single-type literature datasets
  (w = 7/3 * S_att / S_gen with sender counts of the test subset). Bar F1 0.93-0.998 is a 70/30 within-dataset split, per vehicle (Baharlouei et al. 2024), so (ii) is the comparable cell.
- Sender level (secondary): sender flagged if >= k alarms, k = smallest k with <= 1% of validation genuine senders flagged; detection per class.
- Unseen attack families: none exist in the standard 19 (all trained); no separate unseen row in B3 (the zero-shot results are WP5's). Class 12 artefact is flagged, not an unseen row.

### Acceptance rules (verdict wording fixed here)
- R1 (bar): MET if at (H) on test the prevalence-matched F1 of each of the five DoS-family types is >= 0.93 AND test FPR (genuine messages) <= 2%.
- R2 (all classes): MET if at (H) the mean alarm recall over the 19 attack classes (class 12 included, flagged) is >= 0.80 AND test FPR <= 2% (v3 stack WP5 S6: 83.0% on 13 seen classes, scored rows).
- Everything else is descriptive. No "better than" claim against the bar: its split is within-dataset 70/30 per vehicle with an unstated dedup; ours is block-disjoint.

### Amendment 2026-11-04 (before any model was fitted)
- Random Forest size: min_samples_leaf 20, max_samples 0.3 (100 trees, max_features sqrt) instead of 5 / 0.5: 20-class leaf arrays make the larger forest several GB. Nothing else changed.
- Windows of the feature table: count-based (10 messages, l4.WINDOW), as the WP5 S5 recipe; the time-window variant is not a candidate.
