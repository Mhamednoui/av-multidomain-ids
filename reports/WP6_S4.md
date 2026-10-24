# WP6 S4: zero-day v3 (unseen attack types, label-free layers, evidence-novelty layer)

Date: 2026-10-24    Worker: sonnet (WP6, T3)

## Summary (verdict first)
- **Verdict: PARTIAL.** Rules (written before any result, notes/WP6_crossdomain.md "S4 start"): Z1 MET (K and C), Z2 MET for K / NOT MET for C,
  **Z3 NOT MET, Z4 NOT MET, Z5 NOT MET**, Z6 MET, Z7 MET (386 tests). Numbers: `results/WP6/s4_test.json`, `s4_acceptance.json`, tables `results/WP6/s4_tables.md`.
- Held-out types (fixed from earlier steps): GPS doppler_spoof + meaconing; CAN the 5 masquerade families; network PortScan, Web-BruteForce, Web-XSS (Bot is not in
  the one-host D10 view; M1-NET LOAO Bot = 0% cited); V2X classes 6 and 17 (12 is an artefact). LiDAR has no fixed held-out type: its interim XGB saw all three
  types, so the zero-day stack uses only the label-free L1 union; the cross-domain families are "choice-seen" (S2b chose among a few options on their detection).
- **System (S3 composites, label-free noisy_or, 2% val budget, test once): K held-out mean detection 61.1% [48.6, 71.3] at clean-tick FA 2.73% [1.9, 3.8]
  (60 alarm events/h); C 86.2% [82.7, 90.7] at FA 4.78% [4.0, 5.6] (87 events/h).** Seen (non-held-out domain) families: K 84.8%, C 97.3%.
  FA is much better than S3 (6.36% / 6.31%) mainly because the supervised LiDAR XGB (7.7% own FA) is gone; the composites are not identical, so this is not a clean A/B.
- **Zero-day gap (Z3): held-out 61.1% vs seen 84.8% (gap 23.7 points, rule <= 15).** Per held-out domain (K, headline): V2X 96.8, CAN 62.5, GPS 55.5, network 38.7.
  Hardest: Web-XSS 15.3%, Web-BruteForce 42.7%, CAN reverse_light / max_speedometer masquerade 43-48%. Equal-FA diagnostic (threshold at 2% of TEST clean ticks,
  test-informed): K held-out 55.1%, C 67.6%.
- **Physics point (Z4 NOT MET): the data do not support "physics / rule layers are the zero-day defence" for these held-out types.** Tick level, 1% group threshold,
  held-out detection (rules vs normal-only L3): GPS 39.1 vs 72.4 (AUC .802 vs .916), CAN 0.0 vs 96.7 (AUC .434 vs .984), network 33.3 vs 0.0 (AUC .646 vs .774), V2X 87.6 vs 90.5
  (AUC .956 vs .952). Reason: the held-out types are exactly the ones built to pass the simple rules (masquerade respects IDs / timing; Doppler / meaconing are kinematically
  consistent). Rules are zero-day by construction (never saw labels) but only catch what violates a rule: network scans (PortScan 80%) and V2X plausibility. The normal-only
  models add where normal behaviour is well modelled: CAN signals, V2X Kalman, GPS EKF. System level K held-out: rules-only 36.9, L3-only 56.6, both (no novelty) 69.1.
  The second half of the user's claim ("learned layers only add where normal behaviour is well modelled") is what the data show; the first half is only partly supported.
- **Evidence-novelty layer (Z5 NOT MET as written): per domain, robust Mahalanobis (MCD) on the per-layer calibrated scores, fit on clean validation half A only.** Chosen on
  validation (seen families) over IsolationForest. Test, matched pair K: held-out **-8.0 points** (69.1 -> 61.1), FA -0.85 points (3.58 -> 2.73), seen +4.7. At equal FA
  (diagnostic): held-out -2.1, seen +12.8, choice-seen +17. So it improves the broad/seen picture and lowers the clean-alarm rate, but **does not help unseen types**; it
  lowers CAN masquerade detection (81 -> 62, reverse_light 88 -> 45) because 5 extra calibrated entries raise the noisy_or noise floor. Domain level (tick): MCD novelty alone
  catches GPS 63.6% (AUC .858), V2X 87.5%, CAN masquerade 36.7%, network 6.7%, cross-domain 2-33%. Rescued 187 vs lost 476 held-out composites (K).
- Network H+L3 (service, AE) was worse than H on validation and stays out; network L3 alone detects 0% of held-out network types at its 1% threshold (AUC .774).
- **v2 side-by-side (not like-for-like):** v2 OCSVM on detector outputs: FA 2.92%, Bot 5.3%, WebAttack 96.3%, GhostCluster 2.9%. v3: no learned layer saw attacks; WebAttack
  tick-level 10% / 0% (rules + L3), composites 42.7% (BruteForce) / 15.3% (XSS); **v3 is clearly worse than v2 on network WebAttack**; Bot unseen 0% (M1-NET). v2's WebAttack number
  comes from a different pipeline (D01 per-sample features, one-class SVM on detector outputs), so it is a reference, not a like-for-like target.
- **Honest caveats:** held-out detection is a mix of strong V2X / CAN-L3 and weak network / GPS-rule numbers; GPS / cross novelty was fitted on one drive (241 clean ticks); the
  LiDAR label-free L1 alone has 9.7% tick FA at its 1% val threshold (37 clean B ticks); max combiner results are degenerate (tie blocks); every test set was seen before.

## Goal of the step
Zero-day evaluation of v3 with the v2 unseen-attack protocol: per-domain label-free layers (physics / rule and normal-only L3), a novelty detector on evidence vectors inside the
S3 fusion with the label-free combiner; report per domain and system level, ablation, v2 comparison.

## Acceptance rule (notes/WP6_crossdomain.md "S4 start", written before any S4 result)
Z1 held-out mean detection >= 60% (K and C). Z2 clean test tick FA <= 3.0% and <= S3 + 1 point. Z3 held-out >= seen - 15 points (K). Z4 rules >= L3 on held-out types in >= 3 of
4 domains. Z5 novelty kept only if +3 points held-out and FA +0.5 points at most. Z6 no held-out family in any selection. Z7 tests.

## What was done
- `fusion/novelty.py` (EvidenceNovelty mcd / iforest, out-of-fold fit, explain), `tools/WP6_S4_streams.py` (network pack with stack O layers, WP1 S7 L3 column),
  `tools/WP6_S4_lib.py`, `WP6_S4_dev.py` (validation: novelty fit on half A, 12-config grid on half B with seen families only, freeze), `WP6_S4_test.py` (the one test run),
  `WP6_S4_tables.py`; tests `tests/fusion/test_novelty.py` (5), `tests/fusion/test_zeroday.py` (4). Cache: 2 small files in ../data_extra/cache_v3/WP6 (total 148 MB).
- Data: S3 tick packs (val for development, test once), D10 S7 score tables, WP1 s8_raw. Composites: S3 construction, test seeds [SEED, 64, 9, ord], 17,900 (K) / 15,400 (C).
- Smoke run of the test tool on validation packs (plumbing; it printed held-out numbers on validation); nothing was changed after it except a faster bootstrap.

## Results
See `results/WP6/s4_tables.md`: 1 acceptance, 2 system headline + ablation + equal FA, 3 per held-out family, 4 tier table per domain (rules / L3 / union / novelty / frozen domain
score, plus GPS S7 L3, network dos_rate, LiDAR XGB), 5 novelty explanations, 6 validation grid and the same grid on test (information), 7 v2 side-by-side.
Selection (validation half B, non-held-out families): noisy_or beats max everywhere (max thresholds fall in tie blocks of re-sampled outlier ticks); chosen noisy_or, network H, novelty mcd (pooled seen 79.8% vs 74.6% without novelty).
Per-domain system-level held-out detection K (headline / no novelty / rules-only / L3-only): CAN 62.5 / 81.3 / 11.0 / 83.3; GPS 55.5 / 54.3 / 46.8 / 22.0; network 38.7 / 47.2 / 42.9 / 17.6; V2X 96.8 / 86.3 / 82.5 / 83.2.

## Ablation rows
Novelty on / off / iforest, rules-only, L3-only systems (section 2 of the tables); each layer group alone per domain (section 4); full 12-config grid on test (information).

## Problems, surprises, open questions
1. The pre-registered held-out types are hard for simple rules, so Z4 fails; rules-vs-L3 conclusions depend on that choice (stated, not changed).
2. Adding calibrated entries to noisy_or raises the clean noise floor (network H+L3 and the novelty entries both cost detection on weak-signal domains). A gated or
   per-domain-budgeted novelty (alarm only above its own threshold) is the obvious follow-up; not tried (no post-test tuning).
3. FA improved vs S3 but C is still above 3%; the S5 density-aware calibration is still needed. FA in this step is partly an artefact of removing the LiDAR XGB.
4. LiDAR label-free coverage is poor (L1 38% mean at 9.7% FA); real zero-day LiDAR evidence waits for WP3 S9.
5. GPS S7 L3 and the EKF layers are strong held-out detectors (61-72%) but sit outside the frozen GPS default stack; the supervisor may want them in the S5 fusion.
6. The Web-XSS / Web-BruteForce collapse versus v2 should be confirmed with the on-network (stack O + L4) network rows in a later step; here only the host view is used.

## Proposed next step
S5 (density-aware calibration, LOGO ECDFs, temporal correlator, response) with the zero-day variant (noisy_or, network H, label-free) as a labelled row; decide whether the novelty
layer is gated or dropped.

## Tests
Full suite: 386 passed, 0 failed (9 new: 5 novelty, 4 zero-day lib).
