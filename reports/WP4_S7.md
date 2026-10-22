# WP4 S7: combiner + ablation + leave-one-attack-out + cross-dataset -> M1-NET

Date: 2026-10-22    Worker: sonnet high (WP4 S7)

## Goal of the step
Close WP4: final stacks with a combiner chosen on validation, full ablation, leave-one-attack-out (LOAO), cross-dataset D23, frozen network domain output, milestone report `reports/M1_NET.md` (numbers, CIs, what is NOT met).

## Acceptance rule (notes/WP4_network.md, "S7 plan ... BEFORE any S7 score", written before the D10 test run) and result
| rule | result |
|---|---|
| G1 FA of H and O <= 2% (D10 test, headline benign) | MET: 0.48% [0.36, 0.64] / 0.48% [0.29, 0.73]; published labels (audit file in) 5.82% / 5.80% |
| G2 H >= 50% in >= 4 of 11 families; O in >= 7 | MET: 7 / 7 |
| G3 LOAO: no family loses > 20 points, macro within 10; unseen Bot > 70% (expected NOT MET) | NOT MET: PortScan 98 -> 0 for H and O (combiner selection without PortScan picks the learned logistic); macro 65.9 -> 57.0 (within 10); unseen Bot 0% for every stack |
| G4 D23 zero-shot FA <= 5% (H, and H without tcp_flags); on-network O refit <= 2% | zero-shot NOT MET (tcp_flags 30.4%; H on Tue 34.7% sample rows / 23.5% stage; without tcp_flags 6.13% / 4.54%, borderline); on-network MET (Tue O 1.67%, flow-level O 1.08%) |
| G5 null control (<= 0.55 where a learned part exists) | combiner: not applicable (chosen max / noisy-or have no parameters); L4: 0.477 (S6) MET |
| G6 honesty items (Infiltration with / without, Bot published / corrected, ablation, delay, CIs, v2 side by side, labels of optional rows) | done (`reports/M1_NET.md`) |
| G7 frozen domain round trip, tests, cache <= 7 GB | MET: identical scores and alarms on all 585,951 test flows, 347/347 tests, cache 6.3 GB |

## What was done
- Validation-only choices (`results/WP4/s7_dev_val.json`): combiner method per stack and per all-but-one sub-stack (family-balanced sample, 10-minute time-block groups; a first pass with day x period groups was discarded because each family sat in one half and the logistic never saw half of them), dos_rate warm-up sweep.
- D10 test once (`tools/WP4_S7_test.py` -> `results/WP4/s7_d10.json`): 7 stacks, 12 layers alone, ablation H / O, OR view, combiner sensitivity (information), published / Bot-corrected labels, dedup view, delay, bootstrap CIs over 10-minute blocks, LOAO (14 hold-outs, L4 retrained 14 times).
- D23 (`tools/WP4_S7_d23.py` -> `results/WP4/s7_d23.json`): zero-shot and on-network, warm-up sweep.
- Frozen domain `network/domain.py` + `tools/WP4_S7_freeze.py` -> `results/WP4/s7_domain/`; tests `tests/network/test_domain.py` (8 tests).
- Files: tools/WP4_S7_lib.py, _prep.py, _prep_d23.py, _dev.py, _test.py, _d23.py, _freeze.py, _tables.py; results/WP4/s7_*.json|md; reports/M1_NET.md; notes/WP4_network.md, notes/WP4_brief.md updated.

## Results
See `reports/M1_NET.md` (sections 2-5) and `results/WP4/s7_tables_d10.md`, `s7_tables_d23.md`.

## Ablation
`reports/M1_NET.md` section 3 (full tables: s7_tables_d10.md section 5).

## Problems, surprises, open questions
1. The learned combiner makes the headline depend on which families were visible on validation (LOAO PortScan 98 -> 0). The parameter-free max keeps PortScan, but its selection used all families; a combiner that never saw attack labels (fixed max or noisy-or) would be the label-free alternative. Decision for the supervisor.
2. O is not better than H in macro (noisy-or dilution; SSH 4.6%); the validation selection was a tie (0.832 vs 0.829) and the logistic would give 72.1 / 0.19 on test. Not adopted.
3. Family intervals from the block bootstrap are degenerate (1-3 blocks per family): one attack run per family in the test window.
4. D23 zero-shot headline: the flag layer does not transfer; the L2a subset is borderline (6.13% sample rows vs 4.54% stage stream: I did not pre-specify which row set counts).
5. The D10 test stage rows have now been scored 6 times in WP4.
6. S5/D23_eval.pkl deleted (identical copy with file / row / ts in the S7 cache).

## Proposed next step
WP4 is done after your review (M1-NET PARTIAL). Hand over `network/domain.py` + `results/WP4/s7_domain/` to WP6 / WP7 (interface in M1_NET section 9).
