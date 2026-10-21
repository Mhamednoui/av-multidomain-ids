# WP4 S1: data layer (BLOCKED at the gate)

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
