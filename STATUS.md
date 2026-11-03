# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S4 | APPROVED | worker sonnet | 2026-10-21 | combiner noisy_or log form (rank-equivalent, no saturation) |
| WP1 GPS | done (M1-GPS partial) | APPROVED | - | 2026-10-21 | M1-GPS closed PARTIAL, see reports/M1_GPS.md; frozen output gps/domain.py |
| WP2 CAN | done (M1-CAN partial) | APPROVED | - | 2026-10-22 | M1-CAN closed PARTIAL, see reports/M1_CAN.md; frozen output can/domain.py |
| WP3 LiDAR | done (M1-LiDAR partial) | APPROVED | - | 2026-10-25 | M1-LiDAR closed PARTIAL, see reports/M1_LiDAR.md; frozen lidar/domain.py |
| WP4 Network | done (M1-NET partial) | APPROVED | - | 2026-10-22 | M1-NET closed PARTIAL, see reports/M1_NET.md; frozen network/domain.py |
| WP5 V2X | done (M1-V2X partial + V2AIX addendum) | APPROVED | - | 2026-10-24 | S3b APPROVED partial: real-CAM FA 92-95% with VeReMi calibration, ~1% recalibrated |
| WP6 Cross-domain | done (M2 + addendum, not met) | APPROVED | - | 2026-10-25 | final system v2: fusion.system.load_system(2) |
| WP7 System | S2 | APPROVED | worker sonnet (high, T3) | 2026-10-25 | simulation v3 on system v2 done: M3 NOT MET (8/12 rows), reports/WP7_S2.md + M3.md, S2_acceptance.json |

## Overall progress (orchestrator updates this at every approval)

**Overall: 58 / 59 steps approved = 98%** (updated 2026-10-25)

| WP | Steps counted | Approved | % |
|---|---|---|---|
| WP0 Foundation | S1-S4 (4) | 4 | 100 |
| WP1 GPS | S0-S8 (9) | 9 | 100 (M1-GPS partial) |
| WP2 CAN | S0-S7 (8) | 8 | 100 (M1-CAN partial) |
| WP3 LiDAR | S1-S7, S9 (8; S0, S8 optional) | 8 | 100 (M1-LiDAR partial) |
| WP4 Network | S0-S7 (8) | 8 | 100 (M1-NET partial) |
| WP5 V2X | S0, S0b, S0c, S1, S1b, S2-S6, S3b (11; S7 optional) | 11 | 100 (M1-V2X partial + V2AIX addendum) |
| WP6 Cross-domain | S1, S2, S2b, S3-S5, S5b (7) | 7 | 100 (M2 not met) |
| WP7 System | S1-S4 (4) | 3 | 75 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | ALL CLOSED PARTIAL (last: LiDAR 2026-10-25) |
| M2 cross-domain + fusion | closed NOT MET 2026-10-24; addendum S5b 2026-10-25 also NOT MET (3/7 rules) |
| M3 system | closed NOT MET 2026-10-25 (8/12 rows) |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).

## v3.1 (branch v3.1, WP8; plan: workpackages/WP8_v31.md; v3 frozen at tag v3.0)

**v3.1 progress: 6 / 10 steps approved = 60%** (updated 2026-11-03)

| WP | Step | State | Assigned to | Date | Note |
|---|---|---|---|---|---|
| WP8 v3.1 | S0 | APPROVED | worker opus (medium, T4) | 2026-11-03 | H31 + V31_val locked, rules pre-registered (notes/WP8_v31.md); reports/WP8_S0.md |
| WP8 v3.1 | S1 | APPROVED | worker haiku (medium, T1) | 2026-11-03 | downloads done (17.3 GB, free 88.99 GB); calib zips resolved (server sizes); reports/WP8_S1.md |
| WP8 v3.1 | S3 | APPROVED | worker sonnet (high, T3) | 2026-11-03 | LiDAR in-stack: PointDrop 4.3 -> 67.5 % at 1 % (L3 not met; 74.4 % at 1.25 %), FA 0.96 %, other kinds within 2 pts; stream==batch exact; speed 0.14-0.18 s (L1 not met); reports/WP8_S3.md |
| WP8 v3.1 | S3b | IN PROGRESS | worker sonnet (medium, T2) | 2026-11-03 | LiDAR numba kernels, identical outputs, speed rule L1 |
| WP8 v3.1 | S4 | APPROVED | worker sonnet (high, T3) | 2026-11-03 | network streaming Evidence: ORCH freeze F1 tick-final (60 s, -0.34) primary, RC5 (delay 0, -2.90) labelled variant; unseen Bot: no gain counts; reports/WP8_S4.md |
| WP8 v3.1 | S5 | APPROVED | worker sonnet (medium, T2) | 2026-11-03 | CAN incremental windows (exact, p99 41 ms) + V2X single ego (0.03 s/s); reports/WP8_S5.md |
| WP8 v3.1 | S6 | IN PROGRESS | worker sonnet (high, T3) | 2026-11-03 | blame fixes |
| WP8 v3.1 | S2 | TODO | | | fusion false alarms |
| WP8 v3.1 | S7 | TODO | | | final H31 scoring, M4 |
| WP8 v3.1 | P1 | APPROVED | worker sonnet (medium, T2) | 2026-11-03 | paper curves / AUC from saved v3 outputs |
