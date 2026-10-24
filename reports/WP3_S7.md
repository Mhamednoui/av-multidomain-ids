# WP3 S7: L3 normal-only object statistics and L4 retrained v2 descriptor model

Date: 2026-10-24    Worker: sonnet (high, T3); S5 (occlusion) ran in parallel in separate files and was NOT committed when this verdict ran, so the physics stack here is L1 + L2a (intensity) + L2c + L2d without S5.

## Goal of the step
L3: a normal-only model of object statistics fitted on clean train scans. L4: retrain the v2 descriptor model inside the harness on the physically consistent attack set only; leakage controls; say whether L3 / L4 add anything beyond the physics layers.

## Acceptance rule (notes/WP3_lidar.md, "S7 design and ACCEPTANCE RULE", written before any L3 / L4 result)
A1 clean test FA <= 2.5 % (L3, L4), per-drive spread; A2 L4 PointDrop >= 60 %, IntensitySpoof >= 80 %, single-return phantoms at FA + 10 or less (predicted); A3 shuffled-label null (5 seeds) mean AUC <= 0.55; A4 no feature importance red flag; A5 leave-one-type-out reported, collapse stated; A6 L3 against prediction; A7 "adds beyond physics" (>= 3 points on one physical attack, paired bootstrap CI > 0, combined FA <= 2.5 %); A8 sensor-fixed episodes within 3 s, false-episode rate <= 10 %; A9 WP targets (predicted NOT MET); A10 tests, cache <= 2 GB.
Supplement fixed on validation before the verdict: the label-free max stack dilutes strong single layers (PointDrop), so X alone is also compared with the best single physics layer per attack.

## What was done
- Code: lidar/learned.py (L3 features, robust covariance / isolation forest / autoencoder, scan statistics), lidar/learned_l4.py (descriptor rows of the physical attack set, XGBoost, null control, importance), lidar/learned_eval.py (ranks, combiners, LODO FA, paired bootstrap, episodes); tools/WP3_S7_{build_l3,build_l4,l1train,dev_l3,dev_l4,dev_stack,oof,final,analysis,stack,objects,cost,tables,lib}.py; tests/lidar/test_learned.py (10), test_learned_analysis.py (3).
- L3: unit = S3 cluster (>= 10 points); 14 single-scan features (range, count, count residual vs the S2 expected count, extent, angular footprint, ring coverage, intensity, carlike) + 3 track-class features (matched to the previous scan after OXTS ego-motion). Fitted on clean objects only. 6 variants compared on validation; chosen: base features + autoencoder (mean physical detection 6.3 % vs 1.6-2.3 % for the others).
- L4: v2 descriptor (429 columns) + XGBoost, 4 classes (Normal, PointDrop, IntensitySpoof, Phantom = calibrated single-return replace / budget, near / far), 10321 rows from 16 train+val drives; multi-return add and box cloud never trained on. Hyperparameters by a 12-config search on validation (depth 8, lr 0.2, 18 trees). Thresholds: LODO (16 folds, a model per fold), 1 %, tie-safe. Comparison models L4_nophantom and L4_v2 (box-cloud class).
- Same attacked scans as S4 / S6 (regenerated seeds; n_inj identical on all checked scans and 360/360 episode steps).
- Test: ONE verdict run (tools/WP3_S7_final.py, results/WP3/S7/final.json); L3 object-level view and cost are descriptive on the same data. Test exposure: first for L3 / L4; the physics layers' test sets are the same ones used in S4 / S6 (second exposure of those scans, no choice made on test).

## Results (results/WP3/S7/final.json, S7_tables.md; detection in %, per-scan, 510 attacked scans per attack, 7 test drives, 1526 clean scans)
| layer (own 1 % LODO threshold) | FA | worst drive | repl near | repl far | budget near | budget far | PointDrop | IntSpoof |
|---|---|---|---|---|---|---|---|---|
| L1 | 0.1 | 1.9 | 0.0 | 0.2 | 0.0 | 0.0 | 0.0 | 0.0 |
| L2a intensity | 1.0 | 2.3 | 0.8 | 0.8 | 0.8 | 0.8 | 0.6 | 65.3 |
| L2c | 2.1 | 6.1 | 1.8 | 1.8 | 1.8 | 1.8 | 87.3 | 1.8 |
| L2d | 0.2 | 0.7 | 32.5 | 0.2 | 0.2 | 0.2 | 0.2 | 0.2 |
| L3 | 1.7 | 21.5 (0001) | 2.2 | 2.4 | 2.4 | 2.4 | 3.1 | 27.3 |
| L4 | 0.7 | 1.9 | 19.2 | 0.6 | 0.8 | 0.6 | 90.8 | 100.0 |
| L4_nophantom (cmp) | 1.0 | 3.4 | 0.8 | 0.8 | 0.8 | 0.8 | 93.1 | 100.0 |
| L4_v2 box cloud (cmp) | 0.7 | 1.9 | 0.8 | 0.6 | 0.8 | 0.6 | 84.9 | 98.8 |
Comparison attacks (impossible on a single-return sensor): L4 box cloud 5.7, multi-return add near / far 15.1 / 1.0; L4_v2 18.6, 55.3 / 11.4. AUC of L4: replace near 0.842, far 0.552, budget near 0.601, far 0.533, PointDrop 0.992, IntensitySpoof 1.000; L3: IntensitySpoof 0.831, others 0.50-0.54.

Stacks (label-free max of ECDF ranks, combiner chosen on validation, threshold 1 % of pooled out-of-fold clean scores):
| stack | FA | worst drive | repl near | PointDrop | IntSpoof | far / budget phantoms |
|---|---|---|---|---|---|---|
| physics (L1, L2a, L2c, L2d) | 1.2 | 2.5 | 17.8 | 27.6 | 51.6 | 0.8 |
| physics + L3 | 1.4 | 6.5 | 17.3 | 6.3 | 54.7 | 0.8-1.0 |
| physics + L4 | 1.5 | 3.0 | 22.4 | 85.7 | 99.4 | 1.0 |
| physics + L3 + L4 | 1.0 | 6.5 | 20.2 | 82.4 | 98.4 | 0.4-0.6 |
Paired difference over physics (95 % CI): L4: replace near +4.5 [+2.5, +6.7], PointDrop +58.0 [+53.7, +62.4], IntSpoof +47.8 [+43.3, +52.2]; L3: IntSpoof +3.1 [+1.8, +4.7] but PointDrop -21.4 [-25.1, -17.6]. The PointDrop and IntSpoof "gains" are mostly dilution of the physics stack (L2c alone has 87.3 % at its own 1 %): against the BEST SINGLE physics layer per attack, L4 gives PointDrop +3.5 [+0.4, +6.7] (90.8 vs 87.3), IntensitySpoof +34.7 [+30.4, +38.8] (100 vs L2a 65.3), near replace -13.3 (19.2 vs L2d 32.5), all other phantoms at FA. L3 alone is below the best physics layer on every attack.

Episodes (21 per kind, sensor-fixed, 3 s rule): near replace L4 8/21, L2d 11/21, physics stack 11/21, physics + L4 12/21; far replace and budget kinds 0-6/21 for every layer and stack (L3 budget far 6/21 at false-episode rate 8.3 %, not credited: object-level AUC 0.42). False-episode rate: L1 0.0, L2d 2.1, L4 4.2, L2a 6.2, L3 8.3, L2c 10.4, physics 6.2, physics + L3 + L4 12.5 %.

Leakage controls (validation, results/WP3/S7/dev_l4.json):
- C1 null control: AUCs 0.517 0.505 0.521 0.505 0.532, mean 0.516 (bound 0.55): MET.
- C2 importance: top-1 feature sect_hifrac_max 21.0 % of gain (< 25 %); top features sector bright fraction / intensity peak (IntensitySpoof) and sector minimum counts (PointDrop): the physics of those two attacks. Phantom class: diffuse (top feature d_double_return_frac 4.3 %), double-return / range-discontinuity and scan-to-scan features. Ablation without the top-5: 46.2 % vs 40.4 % mean validation detection, no collapse. No red flag by the pre-declared rule.
- C3 leave-one-type-out (validation): PointDrop 95.7 -> 0.0, IntensitySpoof 100 -> 0.0, replace phantoms (near) 41.6 -> 0.5: COLLAPSE. A supervised model trained on our own generator detects the families it was trained on and nothing it has not seen. Without the Phantom class (L4_nophantom) near replace is 0.8 % on test: the 19 % (val 42 %) near-replace detection exists only because the generator's dense near phantoms were a training class (the S2 generator is ~1.5x denser than real near objects), i.e. it is generator-dependent.
Acceptance: A1 MET for the overall FA (L3 1.7 %, L4 0.7 %) but L3's worst test drive is 21.5 % (0001, 108 scans) - not usable per drive; A2 PointDrop 90.8 / IntensitySpoof 100 MET, replace near 19.2 % is ABOVE the FA + 10 bound (flag: generator-dependent, see C3), others at FA; A3 MET; A4 MET (no red flag); A5 reported, collapse stated; A6 L3: IntensitySpoof 27.3 (predicted detectable), near replace 2.2 (merged-cluster prediction not confirmed: scan max over ~225 objects dilutes the object AUC 0.79), PointDrop 3.1, far / budget at FA; A7 formally YES for L4 (PointDrop, IntensitySpoof, near replace in the stack) and for L3 (IntensitySpoof +3.1, but PointDrop -21 in the stack); substantive reading: L4 adds IntensitySpoof +35 over L2a and PointDrop +3.5 over L2c, nothing on far / budget phantoms, and loses to L2d on near replace; L3 adds nothing; A8 L4 near replace 8/21, no kind of far / budget phantom reaches 50 %; false-episode rate of physics + L3 + L4 12.5 % > 10 %; A9 NOT MET (50-400 added points: 0.4-1.0 %; near sparse 0.6-1.0 %); A10 tests see the notes, S7 cache 0.23 GB.

## Ablation row
physics stack alone vs + L3 vs + L4 vs + L3 + L4 above; L4 variants (full / no phantom class / v2 box-cloud class) in the layer table. Validation versions: results/WP3/S7/dev_stack.json.

## Problems, surprises, open questions
- Single-return phantoms that match real objects are not detectable by any learned or physical layer here (AUC 0.50-0.55 for L3 and L4 on far / budget, object-level L3 AUC 0.51 on val and 0.39-0.42 on test): the physics bound again, now also for learned models.
- L4 is a seen-family detector: leave-one-type-out collapses for PointDrop and IntensitySpoof, which L2c and L2a already cover without labels. Recommendation: L4 stays OUT of the zero-shot stack (as for GPS, CAN); optional for seen families.
- L3 FA: drive 0001 (city, 108 scans) 21.5 % alone, 6.5 % inside the stack: normal-only statistics on objects drift between drives; the LODO mean over the 16 train+val drives was 0.9 % (max 4.0 %).
- Label-free max at 1 % total FA gives every layer ~0.25 % budget: PointDrop falls from 87 % (L2c alone) to 27.6 % (physics stack). S9 must decide how to allocate FA (not per-attack labels).
- Validation to test shift of near-replace detection in L4 (41.6 -> 19.2 %), PointDrop 95.7 -> 90.8 %: validation drives are harder, as known.
- S5 occlusion not available at verdict time; "adds beyond physics" for S5 is untested and S9 should re-run the stack with S5.
- World-fixed persistent episodes were not evaluated for L3 / L4 (S4 sensor-fixed set only).
- Build cost: L4 rows took 100 min on the saturated machine (9 python processes on 6 cores).

## Proposed next step
S9 combiner with LODO recalibration of every layer, S5 occlusion included if approved; keep L3 out (adds nothing), L4 optional for seen families; allocate false-alarm budget to layers on validation (not max at 1 % total).
