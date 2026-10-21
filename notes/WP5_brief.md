# WP5 V2X brief (state at end of S4, 2026-10-21)

## Current state
- S0 PARTIAL (VeReMi D12 + Tampa D14 sample; V2AIX D13 needs user request form), S1 / S1b / S2 / S3 APPROVED, S4 REVIEW (PARTIAL).
- Layers: L1 `v2x/l1.py` (beacon rate, freshness, field ranges, sudden appearance = unit-tested only), L2 `v2x/l2.py` (8 deployable checks + map_road soft), L3 `v2x/l3.py` (kf_nis, kf_cusum_hi, kf_cusum_lo, track_birth).
- VeReMi test, harness mean detection over 19 classes at 1% FA: L1+L2 68.0%, L1+L2+L3 78.4%.
- Tests: `python tests/run_tests.py` = 144 pass.

## Binding decisions
- VeReMi = primary benchmark; Tampa (splits_tampa_v2.json, 3 test vehicles, 2 attackers/type) = illustration, no statistical claims.
- Held-out attack types 6, 12, 17: never in any fit, calibration or combiner validation.
- Thresholds: genuine validation only, 1% budget, tie-safe (common/). Union = max of calibrated scores at one budget.
- map_road is NOT in any deployable union. No receiver-position approximations (acceptance range / sudden appearance wait for S3b).
- Use `adapters.load_tampa()` (dedup passages) and `splits_tampa_v2.json`; never `load_tampa_v1`.
- One test run per step; no re-tuning after seeing results.

## Pitfalls
- VeReMi genuine position noise is time-correlated (not white): filter noise fits hit floors.
- VeReMi classes 11/13/16 implementations are kinematically inconsistent; class 12 in the CSV is zero placeholders; 17/18/19 have 1-2 message tracks; 18/19 invisible to any tracker.
- CUSUM keeps alarming after a jump (memory) and inflates message-level detection.
- cusum_lo works on VeReMi only; real standing vehicles (Tampa) repeat positions exactly (FA 13.5%).
- Per-sender ">= 1 alarm" is meaningless at per-message 1% budget; use ">= 3 alarms".
- Tampa 18/19 injection reuses pseudonyms within 5 s (unlike VeReMi).
- Noise fit takes ~9 min; windows python scripts to files, python -I, tf env only.

## Open questions
- Drop cusum_lo from deployable L3? Build a learned road-occupancy prior for classes 2, 12, 18, 19?
- User action: ITS DataHub request for more Tampa days.

## File map
- Code: v2x/{schema,adapters,splitting,attacks,tampa_link,l1,l2,l3}.py; tests/v2x/.
- Tools: tools/WP5_S{1,1b,2,3,4}_*.py (build / eval / report); S4: WP5_S4_l3.py, _diag.py, _report.py.
- Results: results/WP5/ (splits_veremi.json, splits_tampa_v2.json, s2_*, s3_*, s4_*; s4_report_details.md; logs/).
- Reports: reports/WP5_S{1,1b,2,3,4}.md. Notes: notes/WP5_v2x.md (full log with acceptance rules).
