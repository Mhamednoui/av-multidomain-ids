# WP4 S1: data layer (BLOCKED at the gate, v2 gate G1 fails)

Date: 2026-10-21    Worker: sonnet medium (WP4 S1)

## Goal of the step
Gate: cross-check the D10 unofficial mirror against D01; then build the unified flow tables and the time split.

## Acceptance rule
In notes/WP4_network.md ("S1 gate", written before the comparison): >= 99% of the v2-clean D01 rows found in D10 with identical features and mapped label.

## What was done
- tools/WP4_s1_gate.py, tools/WP4_s1_gate_diag.py, network/flows.py (loader helpers only).
- Results: results/WP4/s1_gate_d10_vs_d01.json, results/WP4/s1_gate_diag.json.

## Results
| Check | Value |
|---|---|
| v2 cleaning reproduced on D01 (raw / dup / conflict / clean) | 56,661 / 12,598 / 24 / 44,039 (equal to codes_v2/results/network.json) |
| clean D01 rows found in D10, features + label | 14,655 = 33.3% |
| clean D01 rows found, features only | 39.2% |
| raw D01 rows found, features + label / only features | 46.5% / 51.2% |
| D01 rows matching D10 on 5 key columns | 100% |
| raw D01 rows matching on 55 non-IAT/header/window columns | 55.4% |
Acceptance: NOT MET (33.3% < 99%). Data layer not built.

## Problems, open questions
D01 and D10 share pcaps and key columns but not identical flow records (IAT, header-length, window, URG columns differ in
2-10% of key-matched rows). Likely cause (unverified): D01 comes from MachineLearningCVE, D10 is GeneratedLabelledFlows.
Question: (a) accept D10 and drop the 99% gate; (b) download MachineLearningCVE and repeat the gate against it; (c) wait for UNB.

## Proposed next step
On answer, build the data layer (flows, cleaning counts, time split, per-host labels, brief).

## Update: gate v2 (supervisor option b), results/WP4/s1_gate2.json
MachineLearningCVE downloaded (sha256 = HF LFS oid). G1 (D01 clean rows in MLCVE, features + label): 17,065 / 44,039 = 38.7% FAIL.
G2 (per-file rows and per-label counts D10 = MLCVE): PASS, all 8 files, total 2,830,743. G3 (5 key columns + label, MLCVE rows in D10): 100.0% PASS.
Gate not met as defined (all three required) -> stopped, data layer not built.
Interpretation: D10 = MLCVE flows (same rows, same labels); D01 is not a verbatim subset of either file set, so G1 cannot be met by any official copy.
Question: accept D10 on the evidence of G2+G3 (and treat D01-based v2 numbers as not directly comparable), or investigate D01 provenance first?
