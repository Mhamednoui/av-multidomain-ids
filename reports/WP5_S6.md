# WP5 S6: combiner, ablation, scored-row L4, M1-V2X report

Date: 2026-10-21    Worker: sonnet (high)    Status: PARTIAL (see below). Full milestone report: `reports/M1_V2X.md`; tables `results/WP5/s6_tables_veremi.md`, `s6_tables_tampa.md`; rule `notes/WP5_v2x.md` (S6 section).

## Acceptance (rule written before the result)

| item | result | met |
|---|---|---|
| 1 implemented + tests | v2x/l4.py L4Scored / row_kinds / time windows, v2x/stackeval.py, tools/WP5_S6_*.py | yes |
| 2a FA <= 1.5% (messages, scored messages) | 1.1%, 0.9% | yes |
| 2b genuine senders (k=3) <= 5% | 11.7% (k val=9: 1.0%) | NO |
| 3a no loss on seen scored rows | 83.0% vs 82.7% | yes |
| 3b class 17 gain >= 10 points | 27.8% vs 19.9% (+8.0) | NO |
| 3c class 6 >= 95% | 100.0% | yes |
| 4 shuffled control (1 point) | +2.3 points | NO |
| 5 CIs (block bootstrap), Tampa without CIs | yes | yes |

## Problems, surprises, questions

- Second exposure of the VeReMi test split (S5 was the first); nothing was chosen after seeing it. Smoke run on the validation split was used for plumbing only.
- The supervised L4 adds no detection on the seen classes once restricted to scored rows (83.1% [82.9, 83.3] vs physics 82.7% [82.4, 82.9]); its S5 headline gain was the zero-residual shortcut. Class 17 is the only gain and the combiner (max, chosen on validation without class 17) dilutes it: 27.8% stack vs 48.9% L4 alone.
- Sender-level "k >= 3 alarms" flags 11.7% of genuine senders at the 1% message budget; I added a validation-chosen k (9, <= 1% genuine senders) next to it. Question: adopt the k-val rule as the sender-level rule for WP6?
- Shuffled control FAIL at 1 point (+2.3); AUC 0.511. Bound not changed as instructed.
- Question: freeze the V2X domain output for WP6/WP7 as the full stack with the max combiner on VeReMi, or as the Tampa-calibrated stack?

## Files

`v2x/l4.py` (L4Scored, row_kinds, window_lengths, SCORED_SETS), `v2x/stackeval.py`, `tests/v2x/test_l4.py`, `tests/v2x/test_stackeval.py`, `tools/WP5_S6_dev.py`, `WP5_S6_run.py`, `WP5_S6_report.py`; `results/WP5/s6_dev.json`, `s6_veremi.json`, `s6_tampa.json`, `s6_acceptance.json`, `s6_tables_veremi.md`, `s6_tables_tampa.md`, `s6_l4_model.json`; logs `results/WP5/logs/s6_*.log`. Feature cache deleted.
