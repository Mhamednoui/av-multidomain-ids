# WP5 V2X brief (state at end of S5, 2026-10-21)

## Current state
- S0 PARTIAL (VeReMi D12 + Tampa D14 sample; V2AIX D13 needs user request form), S1 / S1b / S2 / S3 / S4 APPROVED, S5 REVIEW (PARTIAL).
- Layers: L1 `v2x/l1.py`, L2 `v2x/l2.py` (8 deployable checks + map_road soft), L3 `v2x/l3.py` (kf_nis, kf_cusum_hi, track_birth deployable; kf_cusum_lo diagnostic only), L4 `v2x/l4.py` (xgboost on 27 plausibility features, VeReMi-trained without types 6/12/17).
- VeReMi test, 1% FA, message level: L1+L2+L3 (deployable) 78.1% mean over 19 classes -> L1+L2+L3+L4 91.5% (FA 1.1 -> 1.2%). Unseen 6 / 17 / 12: L4 100.0 / 91.9 / 100.0% vs union 99.1 / 46.4 / 48.2%.
- BUT post-hoc diagnostic: L4 headline contains a zero-residual-vector shortcut (flags 100% of first messages, 100% of exactly repeated messages; genuine VeReMi has 0% repeats, genuine Tampa 10-21%). On scored rows (predecessor and moved): L4 ~ baseline on seen classes (83.0 vs 82.7%), real gain only on unseen class 17 (74.8% / 96.3% diagnostic model vs 19.9%).
- Tests: `python tests/run_tests.py` = 168 pass.

## Binding decisions
- VeReMi = primary benchmark; Tampa (splits_tampa_v2.json, 3 test vehicles) = illustration, no statistical claims.
- Held-out attack types 6, 12, 17: never in any fit, calibration, hyperparameter choice or combiner validation (also removed from the frames that produce neighbour features).
- Thresholds: genuine validation only, 1% budget, tie-safe (common/). Union = max of calibrated scores at one budget.
- map_road and kf_cusum_lo are NOT in any deployable union and not L4 features. No receiver-position approximations.
- Use `adapters.load_tampa()` (dedup) and `splits_tampa_v2.json`; never `load_tampa_v1`. One test run per step; no re-tuning after seeing results.
- L4 features: only L1-L3 plausibility outputs (no x, y, speed, sender id, t). Groups M (message), W (window 10), N (birth), T (track_pos, dt_prev; ablated).

## Pitfalls
- VeReMi genuine position noise is time-correlated; classes 11/13/16 are kinematically inconsistent; class 12 in the CSV = zero placeholders (its detection is an artefact: frozen placeholder rows + CUSUM memory); 17/18/19 have 1-2 message tracks.
- Zero residuals mean "first message" or "exact repeat". A supervised model turns them into an attack flag (genuine VeReMi is always noisy, real standing vehicles are not); the per-message 1% budget lets it flag every genuine first message (84% of its false alarms). Always report scored-row FA, FA per genuine first message and the frozen share.
- Per-sender ">= 1 alarm" is meaningless at the per-message budget; use ">= 3 alarms" (L4: genuine senders 1.8%, union 10.5%).
- Shuffled-label control: AUC 0.475 but 4.1% detection at 1.1% FA (outlier tail), so "chance" is ~3-4% not 1%.
- VeReMi-trained model does not transfer to Tampa as is: 10 Hz vs 1 Hz beacons (rate and window features), FA 100% at the VeReMi threshold; rank transfers partly (AUC 0.904).
- Windows: python scripts to files, python -I, tf env only; features cache for L4 ~0.5 GB (rebuild with tools/WP5_S5_dev.py --cache <dir>, 2 min), deleted after the run.

## Open questions
- Adopt a scored-rows-only L4 (first messages -> sender-level birth rule; frozen repeats not claimed) as the deployable L4 and re-test once? (S5 report, question 1.)
- Tampa-specific L4 needs more Tampa days (user action: ITS DataHub request, text in reports/WP5_S0b.md); V2AIX access form still pending.

## File map
- Code: v2x/{schema,adapters,splitting,attacks,tampa_link,l1,l2,l3,l4}.py; tests/v2x/.
- Tools: tools/WP5_S{1,1b,2,3,4}_*.py; S5: WP5_S5_dev.py (features + hyperparameters on validation), WP5_S5_l4.py (final run), WP5_S5_diag.py, WP5_S5_tampa_frozen.py.
- Results: results/WP5/ (splits_*.json, s2_* ... s4_*, s5_dev.json, s5_summary.json, s5_tables.md, s5_diag.{json,md}, s5_l4_model.json; logs/).
- Reports: reports/WP5_S{1,1b,2,3,4,5}.md. Notes: notes/WP5_v2x.md (full log with acceptance rules).
