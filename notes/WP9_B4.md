# WP9 B4: GPS (AV-GPS) + LiDAR (KITTI) seen-attack benchmark, notes

## 2026-11-05 pre-registration (written BEFORE any B4 model was fitted, any B4 test row scored or any B4 attack descriptor built)

### Data facts that shape the splits (tools/WP9_B4_gps_explore.py, _explore2.py; descriptive only, no model)
- AV-GPS-Dataset (Abrar et al., arXiv 2405.08359) is public on GitHub (mehrab-abrar/AV-GPS-Dataset, no login). A clone already sits in ../codes/data/AV-GPS-Dataset (D03, used by WP1);
  nothing was downloaded again (files hashed in locks/WP9_avgps.json). 4 CSV files, 44 columns, label `Data Type` (1 = spoofed), one rover, Tucson AZ, 1 Hz.
- Leaks inside the dataset (what the stratified-fold and "cross-dataset" protocol of the paper does not remove):
  file 0 (46,287 normal rows) is entirely contained in file 1; two spoofed sessions of file 1 are exact copies of two others (1584 and 1247 rows); the two spoofed sessions of file 3
  (181, 224 rows) are 94-96% copies of two file-2 sessions. After dedup dataset 3 keeps only its two normal sessions (231 rows), so the paper's third cross-dataset case cannot be formed.
- Spoofed sessions are not a clean attack signal: 5 of the 9 distinct file-1 spoof sessions have mean satellite count < 1.2 (no-fix placeholder: HDOP ~100, rover mostly stationary); the other 4 have mean HDOP 12-26 and coordinates that jump up to ~2000 km.
  WP1 S8 already found "nothing usable" for the v3 layers here. A receiver-state feature (satellites, HDOP) therefore separates the classes trivially; F_nosat / F_kin are the artefact-free views.
- KITTI LiDAR: the WP3 caches are gone (cache_v3/WP3 not on disk); descriptors are rebuilt from the raw scans. H31 drives (13 fresh KITTI drives of locks/H31.json) are never opened.

### Locks (committed before training): locks/WP9_avgps.json, locks/WP9_kitti.json (tools/WP9_B4_lock.py)
- H31 overlap = 0 (KITTI: asserted with WP8_lib.assert_not_h31 on all 23 drive names; AV-GPS: no AV-GPS data in H31).
- AV-GPS: session = contiguous rows, one label, no Run Time reset / gap > 5 s; dedup as above; sessions < 10 rows dropped.
  Case I (primary, the paper's "train one set, test another"): train 17 sessions / val 8 sessions of file 1 (per-label draw, seed 42), test = file 2 (2 normal + 3 spoof sessions, 5,184 normal + 1,699 spoof rows)
  plus the 2 file-3 normal sessions (231 rows) as extra false-alarm data. Case II: train = file 2 (no validation possible: config and threshold frozen from Case I), test = all file-1 sessions (25) + file-3 normals.
- KITTI: WP1/WP3 drive split train 13 / val 3 / test 7 (2588 / 552 / 1533 scans).
  Exposure of the test drives: v3 frozen layers and the v3.1 stack were fitted/tuned with these drives in the loop (V31_val), so for v3 / v3.1 they are NOT a fresh test; the v3.1 numbers on them are
  leave-one-drive-out (LODO) out-of-fold scores of the WP8 S3 harness, labelled "tuned on these drives". For the B4 supervised model the test drives are scored for the first time.

### GPS: unit, features, models, selection (validation only)
- Unit: one fix (row, 1 Hz). Label `Data Type`. Derived features computed inside a session only (previous row of the same session; first row NaN).
- Feature sets (fixed here):
  F_full = all numeric columns except identifiers/clock (Run Time, Clock Time, Clock Date, Hobbs, GPS MGRS, EKF Detector (file 3 only), Data Type): includes satellites / HDOP / VDOP / locks.
  F_nosat = F_full minus {GPS HDOP, GPS VDOP, Satellite Locks, Satellite Count}.
  F_kin = {pos_step_m (haversine step from lat/lon), speed_gap = |pos_step_m - Velocity|, heading_gap (course of the step vs Heading), 5-row means of the first three, Velocity, Yaw Rate, Steering Angle, Throttle}.
- Model: XGBoost (hist, lr 0.1, early stopping on validation logloss, patience 20, max 300 rounds), depth in {3, 5, 7}, 9 candidates (3 sets x 3 depths). Per set the depth is chosen on validation by F1 at the validation
  F1-optimal threshold (ties within 0.005: smaller depth). Case I validation = 8 file-1 sessions.
- Operating points (fixed on validation before test): (H) 1% budget on validation normal rows (tie-safe); (S) threshold maximising validation F1 (literature convention; reported after H, same single scoring). Case II uses probability 0.5.
- Reference (no labels): the v3 GPS layers that exist for AV-GPS (L1 kinematic rules from position, B2, EKF NIS, EKF-CUSUM, dead-reckoning CUSUM, combiner noisy_or_log; no Doppler / IMU / LiDAR; EKF noise config of WP1 S3_avgps.json),
  calibrated on the validation NORMAL rows (1% budget), scored on the same test sessions; AUC, FA, detection, session-label permutation null.
- Metrics (test, once): F1 (attack = positive), precision, recall, FPR, accuracy, AUC, macro-F1; session-cluster bootstrap 95% CI (2000 resamples, seed 42, over test sessions; 5 clusters in Case I: the interval is wide and is stated as such); per-session recall / FPR.

### GPS acceptance rules (written before results)
- G1 (bar row, "equal" only): Case I test F1 of F_full at (S) >= 0.90 (bar: Abrar cross-dataset F1 0.90-0.965; their features unknown, F_full is the closest; their split is not session-disjoint and has the dataset copies above).
- G2 (artefact-free): F_nosat or F_kin Case I test F1 at (S) >= 0.80 AND test FPR <= 5%.
- G3 (v3 layers): the combined layer separates if test AUC > 95th percentile of the session-label permutation null.
- Prediction written now: G1 MET (receiver state), G2 NOT MET, G3 NOT MET (WP1 S8 found the same on its own split). A claim "better than the bar" is impossible by construction: different features/split, 5 test clusters.
- Wording: "equal" / "comparable" / "not comparable" only.

### GPS controls (validation, committed before test)
1. Row-shuffled train labels, 3 seeds, chosen config of each set: validation AUC in [0.42, 0.58] = PASS.
2. Session-label permutation: whole-session labels permuted among train sessions (20 draws), refit, validation AUC. PASS if the real validation AUC > the 95th percentile of this null (the band 0.42-0.58 is not used: B3 showed group-permutation nulls are wide).
3. Proxy-only: XGBoost on vehicle-state fields {Velocity, Throttle, Steering Angle, Yaw Rate, Roll, Pitch} (no GPS fields) -> validation AUC reported; > 0.8 means the label is predictable without any GPS information (stationary-rover artefact) and is printed next to every GPS table.
4. Feature importance (total gain share, chosen model per set): single feature > 50% or satellite/HDOP group > 50% = flag "receiver-state artefact", printed on the row (not a stop, because F_full is expected to be flagged; F_nosat and F_kin must be flag-free or the flag is reported).

### LiDAR: unit, data, features, models, selection (validation only)
- Unit: one scan. Clean scans: all scans i >= 1 of each drive (previous scan exists). Attacked scans: the S4 / WP8 S3 evaluation set (scans i % 3 == 1, rng [83, drive, i], lidar.s4_build.attack_cases): 9 kinds per scan =
  ph_replace_near, ph_replace_far, ph_budget_near, ph_budget_far (calibrated single-return phantoms), PointDrop, IntensitySpoof, cmp_boxcloud (dense box-cloud phantom), cmp_mradd_near, cmp_mradd_far (multi-return add, impossible for a single-return sensor, the CARLO / literature style "add points").
  Training rows: same 9 kinds on every 2nd scan of the 13 train drives with rng [97, drive, i] (other scans / seeds than evaluation); all nine kinds are SEEN in training ("seen attack types, our generator, KITTI").
  Honesty: all attacks are injected by us; no public KITTI LiDAR-spoof detection benchmark exists. The kinds fall in two groups: NAIVE-ADD {cmp_boxcloud, cmp_mradd_near, cmp_mradd_far} (the attack style of the published bar, not physically possible for a single-return LiDAR) and
  PHYSICAL {4 ph_* kinds, PointDrop, IntensitySpoof} (RULES 5.7). A win on NAIVE-ADD is never presented as a realistic-attacker win.
- Features: lidar.features.describe (211) + temporal (218) + 7 = 429 columns (v2/v3 L4 descriptor), temporal part vs the previous scan (clean previous scan, onset case, as in S4 eval).
- Models: XGBoost 4-class (Normal, PointDrop, IntensitySpoof, Phantom = ph_* + cmp_*), hist, early stopping 50 on validation mlogloss, 12 random-search trials from lidar.train_xgb.SPACE (seed 42) x weight power in {0.5, 1.0}.
  Score s = 1 - P(Normal). Selection criterion: validation mean over the 9 kinds of TPR at validation FPR 10% (threshold = tie-safe 10% quantile from the top of the validation clean scores); ties within 0.005: fewer trees, then shallower.
- Secondary model "phys-only" (not a selection candidate): same chosen hyper-parameters, trained WITHOUT the three cmp_* kinds, so those become unseen (a leave-family-out row, shows how much the naive-add result depends on having seen it).
- v3.1 comparison: tools/WP8_S3_an.fit_fold with the S3-chosen config tail2h|zmulti|E7 (B 1%), LODO over the V31_val drives; scores on the B4 test drives' clean scans and the same attacked scans (WP8 results/WP8/S3/frame.pkl). Evaluated at the SAME validation-derived thresholds
  (10% and 1% of the 3 B4 val drives' clean scores) and at its native 1% alarm. The frame already exists (built by WP8 S3 with numba off/on identical outputs); no H31 scan is read by it (assert_not_h31 in WP8 S3 build).
- Operating points: FPR 10% and FPR 1% (thresholds from validation clean scans, applied unchanged to the test drives; the test FPR is reported and must be within [0.5x, 1.5x] of the target, else "threshold does not transfer").
- Metrics (test, once): per kind TPR at both operating points; pooled TPR of NAIVE-ADD and of PHYSICAL; 4-class macro-F1 and per-class recall at each operating point (alarm if s >= thr, class = argmax over the three attack classes; macro-F1 on a prevalence-balanced
  weighting: Normal total weight = each attack class total weight, written in the report); FPR; AUC (any attack vs clean, and per kind vs clean); drive-cluster bootstrap 95% CI (7 test drives, 2000 resamples, seed 42; paired for supervised minus v3.1).

### LiDAR acceptance rules (written before results)
- L1 (bar-style row): NAIVE-ADD pooled TPR >= 0.85 at the 10% operating point with test FPR <= 15%. Bar (ADoPT, nuScenes: TPR > 85% at FPR < 10%; Shadow-Catcher, KITTI: object-level accuracy > 94%) uses other data, other metric level (object / frame), other attacks: at most "equal in number", never "better".
- L2 (physical kinds): no numeric target. Written prediction: PointDrop and IntensitySpoof TPR >= 0.9 at 10%; single-return phantoms (ph_replace/budget far) <= 0.25 at 10% (physics bound, v3 finding); near replace/budget in between.
- L3 (v3.1 vs supervised): supervised "better" on a kind only if the paired drive-bootstrap CI of (TPR_sup - TPR_v31) at the same thresholds excludes 0. Caveat printed: v3.1 stack was tuned on these drives, the supervised model was not.
- L4: test FPR within [0.5x, 1.5x] of the validation targets at both operating points (else stated).
- Prediction written now: L1 MET (box cloud and multi-return add are easy for a supervised model), L2 as written, supervised > v3.1 on cmp_* and on PointDrop/IntensitySpoof at 10% FPR, equal on far single-return phantoms.

### LiDAR controls (validation, committed before test)
1. Row-shuffled train labels (seed 42): validation AUC any-attack vs clean in [0.42, 0.58] = PASS.
2. Within-scan label permutation: for each base scan (clean row + its attacked rows) the labels are permuted among those rows (5 seeds): validation AUC reported with the null spread; PASS if inside [0.42, 0.58], otherwise reported as FAIL as written
   (B3 lesson: group-permutation nulls can be off-centre; the interpretation goes next to the number; not a stop).
3. Feature importance (total gain share, chosen model): RED FLAG = STOP (no test scoring, write brief) if one feature > 40% of the gain, or the 218 temporal columns together > 70%.
4. Drive leakage check: the shuffled control above is run on train->val (drive-disjoint); additionally the real model's validation AUC is reported per validation drive (a drive far below the others is stated).

### Common
- Every row labelled "seen attack types, our generator (LiDAR) / AV-GPS spoofing (GPS)"; every number is read from results/WP9/B4_*.json. The test of each case/model is scored once; exposure file results/WP9/B4_exposure.json.
- No "better than the literature" statement unless the same dataset, same or stricter split and CI excluding the bar; here none of the rows meets that.
- Crash safety: journal lines in notes/WP8_journal.md (format `<ISO> | B4 | what | next`), chunked resumable builds in ../data_extra/cache_v3/WP9/B4, logs in results/WP9/logs/, scores in results/WP9/scores/B4/.
- CPU budget: the machine is shared with WP8 S7; descriptor builds run with 3 processes.

## 2026-11-05 amendments before any test scoring (GPS validation seen; LiDAR not yet built)
- Amendment 1 (after the first controls run, validation only): the proxy-only vehicle-state model (Velocity, Throttle, Steering, Yaw Rate, Roll, Pitch; no GPS field) reaches validation AUC 0.997 (depth 3) /
  0.994 (depth 5): the AV-GPS label is predictable without any GPS information (the rover is almost stationary in the spoofed sessions; Velocity / Longitudinal Vibration carry most gain even in F_full:
  satellite+HDOP gain share only 0.047). F_kin and F_nosat contain such fields, so G2 as written would not be artefact-free. Two extra feature sets were added BEFORE any test row was scored:
  F_kin_noVS = {pos_step_m, speed_gap, heading_gap and their 5-row means} (the GPS-vs-vehicle consistency view, no vehicle-state field as such, though speed_gap uses Velocity as the independent witness) and
  F_pos = {pos_step_m, pos_step_m5, course_change, course_change5, GPS Course} (GPS fields only). G2 is re-stated: artefact-free = F_kin_noVS or F_pos (Case I F1 at S >= 0.80 and FPR <= 5%);
  the original G2 (F_nosat or F_kin) is still reported and labelled "contains vehicle-state proxy fields". Same depth grid and selection rule for the new sets (tools/WP9_B4_gps_fit.py re-run; the first three sets are unchanged).
- Amendment 2: the row-shuffled control uses a FIXED number of rounds (the chosen trees) and 5 seeds; early stopping on the real validation labels (supplementary, also reported) selects the best-looking round and is biased upwards (AUC 0.6-0.87).
  Result: the fixed-round nulls scatter 0.29-0.71 around 0.5 on 8 clustered validation sessions, so the band 0.42-0.58 FAILS as written for 4 of 5 sets (PASS for F_kin_noVS only); interpretation (stated in the report): the null is centred, the spread is a validation-size effect;
  the real validation AUC (0.93-0.998) exceeds the maximum of each null (<= 0.71). Not a stop condition. Session-label permutation: PASS for all sets in the sense "real AUC > null q95" but the null spans 0.00-0.99 (8 validation sessions): weak evidence either way.
- v3 GPS layers script (tools/WP9_B4_gps_v3.py): F1 / AUC / CI are computed on the file-2 sessions only; file-3 normals contribute false alarms only (stated, same as the supervised rows).
