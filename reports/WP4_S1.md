# WP4 S1: data layer (unified flows, cleaning, time split)

Date: 2026-10-21    Worker: sonnet medium (WP4 S1)

## Goal of the step
Gate the D10 mirror, then build the unified flow tables for D10 (CICIDS2017) and D23 (CSE-CIC-IDS2018), clean as in v2, split by time,
per-host labels, fix the held-out families for S7.

## Acceptance rule (notes/WP4_network.md, "S1 gate", "gate v2", "S1 acceptance rule", all written before the results they judge)
Gate v2: G1 (D01 clean rows in MLCVE >= 99%), G2 (D10 = MLCVE per-file rows and label counts), G3 (5 key columns, >= 99%).
Data layer: unified table, counts per file before/after each cleaning step, time split with every evaluated family having a test part
(>= 100 test, >= 30 val), held-out list fixed, host labels, column map tested, caches <= 5 GB, tests pass.

## What was done
- Gate: results/WP4/s1_gate_d10_vs_d01.json, s1_gate_diag.json, s1_gate2.json. D10 accepted by the supervisor on G2+G3; G1 failed (recorded).
- network/flows.py (column map, labels, timestamps, cleaning, time split), tools/WP4_s1_build.py (D10, D23), tools/WP4_s1_hosts.py,
  WP4_s1_hosts_d23.py, WP4_s1_tables.py, tests/network/test_flows.py (8 tests), notes/WP4_brief.md.
- Caches: ../data_extra/cache_v3/WP4/ (3.2 GB; not in git).

## Results (tables: results/WP4/s1_tables.md, generated from results/WP4/s1_clean_D10.json / s1_clean_D23.json)
| Item | D10 | D23 |
|---|---|---|
| lines read | 3,119,345 | 16,233,002 |
| empty / repeated-header rows removed | 288,602 / 0 | 0 / 59 |
| rows after that | 2,830,743 | 16,232,943 |
| exact duplicates removed | 596,376 (21.1%) | 5,410,812 (33.3%) |
| conflicting-label rows removed | 542 | 43,572 |
| clean rows | 2,233,825 | 10,778,559 |
| split train / val / test / gap | 1,259,486 / 410,760 / 470,829 / 92,750 | 6,620,892 / 1,897,210 / 2,019,464 / 240,993 (+14 NaT) |
Per-file counts and per family split counts: results/WP4/s1_tables.md.
- D10 evaluable families (test >= 100, val >= 30): 11 (Bot 308 test, PortScan 192, Web-XSS 132 ...). Not evaluable: Heartbleed, Infiltration, Web-SQLi.
- D23 evaluable: Bot, DDoS x3, GoldenEye, Slowloris, Infiltration, SSH-Patator, Web-BruteForce. Not: Hulk (val 0: file ends at the row limit), SlowHTTPTest (43 clean rows),
  FTP (40), SQLi, XSS (test 53).
- Held-out for S7 fixed: notes/WP4_brief.md and results/WP4/s1_heldout.json.
- Host labels: 336,230 of 336,234 D10 attack flows have the documented attacker end (205.174.165.73 / 172.16.0.1); victims in results/WP4/s1_hosts_d10.json.
  D23: only Tue-20-02 has IPs (s1_hosts_d23.json).
- v2 numbers: D01 cleaning reproduced exactly with the same code (56,661 / 12,598 / 24 / 44,039). Not reproducible on D10: D10 is a different, larger flow
  set (and D01 is not a subset of it), so the 44,039 and v2's 99.73% accuracy have no D10 counterpart; D10 duplicate rate 21.1% is in line with D01's 22.2%.
Acceptance: MET for the data layer, with the gate G1 recorded as failed (accepted by the supervisor).

## Findings and caveats
1. Both datasets have no AM/PM: hours 1-7 are afternoon (+12 h); D23 needed the same fix (found from attack-hour histograms; first D23 split discarded).
2. Split design changed once before any model was trained (flow-count cuts, 1-minute gap, 5-minute short-period limit) after the first D10 split gave PortScan val = 2 flows.
3. v2-style dedup removes 99% of PortScan flows (158,930 -> 1,851) and most D23 FTP / SlowHTTPTest flows; host-window rules (S3/S4) must use the stage caches (all rows before dedup).
4. D23 Tue-20-02 has 84 columns = the usual 80 plus Flow ID, Src IP, Src Port, Dst IP (not renamed features); mapped and tested. 9 of 10 D23 files have no IPs.
5. D23 7 files at 1,048,575 rows: as published. Fri-16-02 stops at 13:xx so Hulk has no val part.
6. Both D10 file sets come from one unofficial mirror; D01-based v2 numbers are not comparable with v3 (differing features: s1_gate_diag.json).
7. Time-ordered split inside attack windows means train/val/test of one family come from the same attack session (same attacker tool run); cross-session generalisation is tested only by leave-one-attack-out and D23.

## Ablation row(s)
Not applicable (data step).

## Proposed next step
S2 (L1 allow-list / protocol rules) on the D10 train split; stage caches for S3.
