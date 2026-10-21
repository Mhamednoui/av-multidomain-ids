# WP5 V2X brief (state at end of S6 = M1-V2X candidate, 2026-10-21)

## Current state
- S0 PARTIAL (VeReMi D12 + Tampa D14 sample; V2AIX D13 needs the user's request form), S1 / S1b / S2 / S3 / S4 / S5 APPROVED, S6 REVIEW (PARTIAL). Milestone report: `reports/M1_V2X.md` (self-contained, ~100 lines).
- Deployable stack (VeReMi): L1 beacon_rate + field_ranges; L2 seven checks (no map_road, yaw, freshness); L3 kf_nis, kf_cusum_hi, track_birth (no kf_cusum_lo); L4-scored (`v2x/l4.py` L4Scored: xgboost, 10 rate-free residual features set S2_resid, trained and applied on scored rows only; score 0 on first messages / gaps / exact repeats). Combiner `common/combiner.py` "auto" (full stack chose max).
- VeReMi test (SECOND exposure; first in S5), block bootstrap CIs over 10 test time blocks: full stack FA 1.1% msgs / 0.9% scored; scored-row mean over 13 seen classes 83.0% [82.7, 83.1] vs physics-only 82.7%: L4 adds nothing on seen classes. Unseen: class 6 100%; class 17 27.8% [24.7, 31.8] scored rows (physics 19.9%, L4 alone 48.9%), sender level 95.3% [87.2, 100] at 1.0% genuine-sender FA. Class 12 excluded (zero-placeholder artefact).
- Sender level: k=3 alarms flags 11.7% of genuine senders at the 1% message budget (rule 5%: NOT met); validation-chosen k (9 for the full stack, <= 1% genuine senders) gives 1.0%; seen-class mean 86.6%, Sybil 18 / 19 97.8 / 100%.
- Not caught: ConstPosOffset (2) 0.8% / 0% senders, EventualStop (9) 0.8% / 0%, per-message Sybil 17-19 at message level, delayed messages (no age in VeReMi). Tampa (illustration, 3 vehicles): stack FA 2.8%, scored seen 81.8% (physics 81.7%).
- Shuffled-label control on scored rows: +2.3 points (null 3.3% at 1.1% FA, AUC 0.511): NOT met (bound kept at 1 point).
- Tests: `python tests/run_tests.py` = 185 pass.

## Binding decisions (accumulated)
- VeReMi = primary benchmark; Tampa (splits_tampa_v2.json, 3 test vehicles) = illustration, no statistical claims.
- Held-out types 6, 12, 17: never in any fit, calibration, hyperparameter choice or combiner validation; 12 is an artefact (zero placeholder + CUSUM memory) and is never claimed.
- Thresholds: genuine validation only, 1% budget, tie-safe. map_road and kf_cusum_lo are NOT in any deployable union and not L4 features. No receiver-position approximations.
- Deployable L4 = scored rows only; new identities -> sender-level birth rule; exact repeats not claimed. Tampa-bound features rate invariant (no rate / dt / track position / birth features, no count windows).
- One test run per step; no re-tuning after seeing results.

## Pitfalls
- Zero residuals mean "first message" or "exact repeat": a supervised model turns them into an attack flag. Report scored-row FA and the row-kind shares next to every headline.
- Per-sender ">= 3 alarms" is not a 1% rule; choose k on validation genuine senders.
- Max combiner chosen on validation seen classes dilutes the L4 gain on unseen class 17.
- Tampa is 10 Hz, VeReMi 1 Hz; the VeReMi-trained model transfers only with rate-free features and a Tampa re-threshold.
- Windows: python scripts to files, `python -I`, tf env only; `tests/run_tests.py` filters on the path with backslashes ("test_l4"); do not put double-backslash-n in heredoc edit scripts.

## Open questions
- Adopt the validation-chosen k as the sender-level rule for WP6 / WP7? Which V2X domain output is frozen for WP6 (VeReMi-calibrated full stack or Tampa-calibrated)?
- Tampa-specific L4 needs more Tampa days (user action: ITS DataHub request, text in reports/WP5_S0b.md); V2AIX access form still pending.

## File map
- Code: v2x/{schema,adapters,splitting,attacks,tampa_link,l1,l2,l3,l4,stackeval}.py; tests/v2x/.
- Tools: tools/WP5_S{1,1b,2,3,4,5}_*.py; S6: WP5_S6_dev.py (features, feature set + hyperparameters on validation), WP5_S6_run.py (final run, --smoke = validation stand-in), WP5_S6_report.py (writes reports/M1_V2X.md, reports/WP5_S6.md, results/WP5/s6_acceptance.json).
- Results: results/WP5/ (splits_*.json, s2_* ... s5_*, s6_dev.json, s6_veremi.json, s6_tampa.json, s6_acceptance.json, s6_tables_veremi.md, s6_tables_tampa.md, s6_l4_model.json; logs/).
- Reports: reports/WP5_S{1,1b,2,3,4,5,6}.md, reports/M1_V2X.md. Notes: notes/WP5_v2x.md (full log with acceptance rules).
