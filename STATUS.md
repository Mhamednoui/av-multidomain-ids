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

**v3.1 progress: 10 / 11 steps approved = 91% (WP8, S8 added); WP9 benchmark 4 / 6; overall v3.1+WP9 14 / 17 = 82%** (updated 2026-11-05 19:35)

| WP | Step | State | Assigned to | Date | Note |
|---|---|---|---|---|---|
| WP8 v3.1 | S0 | APPROVED | worker opus (medium, T4) | 2026-11-03 | H31 + V31_val locked, rules pre-registered (notes/WP8_v31.md); reports/WP8_S0.md |
| WP8 v3.1 | S1 | APPROVED | worker haiku (medium, T1) | 2026-11-03 | downloads done (17.3 GB, free 88.99 GB); calib zips resolved (server sizes); reports/WP8_S1.md |
| WP8 v3.1 | S3 | APPROVED | worker sonnet (high, T3) | 2026-11-03 | LiDAR in-stack: PointDrop 4.3 -> 67.5 % at 1 % (L3 not met; 74.4 % at 1.25 %), FA 0.96 %, other kinds within 2 pts; stream==batch exact; speed 0.14-0.18 s (L1 not met); reports/WP8_S3.md |
| WP8 v3.1 | S3b | APPROVED | worker sonnet (medium, T2) | 2026-11-03 | LiDAR numba kernels: median 73-76 ms, p99 110-135 ms (L1 met), identical outputs (0 alarm diffs, max diff 0.0); reports/WP8_S3b.md |
| WP8 v3.1 | S4 | APPROVED | worker sonnet (high, T3) | 2026-11-03 | network streaming Evidence: ORCH freeze F1 tick-final (60 s, -0.34) primary, RC5 (delay 0, -2.90) labelled variant; unseen Bot: no gain counts; reports/WP8_S4.md |
| WP8 v3.1 | S5 | APPROVED | worker sonnet (medium, T2) | 2026-11-03 | CAN incremental windows (exact, p99 41 ms) + V2X single ego (0.03 s/s); reports/WP8_S5.md |
| WP8 v3.1 | S6 | APPROVED | worker sonnet (high, T3) | 2026-11-04 | blame: channel-graph hypothesis blame (A1 selected): comma GNSS correct 77 % / wrong 0 % (B2 met), K B3 met, B1 gps_can NOT MET (A3 inertial alt 43 / 41 %); regression exact; reports/WP8_S6.md |
| WP8 v3.1 | S2 | APPROVED | worker opus (medium, T4) | 2026-11-04 | V31_val all S2 rows MET: chosen MX/L100/b2 (equal split = max), K FA 1.92 %, 5.09 ev/h, det 78.2 %; frozen_system31 sha256 a8994883; reports/WP8_S2.md |
| WP8 v3.1 | S7 | APPROVED | worker sonnet (high, T3) | 2026-11-05 | M4 NOT MET (7 of 18 rows): H31 clean FA K 12.2 % / C 6.1 % (drive 0093 anomaly), events/h 24.8 / 22.6; PointDrop scan +34 pts (fresh); comma GNSS blame fixed; reports/M4.md, WP8_S7.md, RESULTS_v31.md |
| WP8 v3.1 | P1 | APPROVED | worker sonnet (medium, T2) | 2026-11-03 | paper curves / AUC from saved v3 outputs |
| WP8 v3.1 | S8 | REVIEW | worker sonnet (high, T3) | 2026-11-05 | 0093 = non-converged OXTS record (data defect); pre-registered sensor-health gate (system/health31.py): V31_val no-op, H31 exposure 2 (NOT fresh) K FA 12.2 -> 4.7 %, SAFE_STOP 6.43 -> 0.88/h, det 87.1 -> 84.6; M4 still NOT MET; reports/WP8_S8.md |

## WP9 benchmark track (plan: workpackages/WP9_benchmark.md; deadline 2026-11-30)

| WP | Step | State | Assigned to | Date | Note |
|---|---|---|---|---|---|
| WP9 bench | B0 | APPROVED | worker sonnet (medium, T2) | 2026-11-04 | literature bar + leak-free split proposal; reports/WP9_B0.md, results/WP9/ |
| WP9 bench | B1 | APPROVED | worker sonnet (high, T3) | 2026-11-04 | CAN: Car-Hacking MET (equal to leaky bar), ROAD NOT MET (FPR 3.2%), D11 NOT MET at 1% budget, unknown vehicle fails; reports/WP9_B1.md |
| WP9 bench | B2 | IN PROGRESS | worker sonnet (high, T3) | 2026-11-04 | network |
| WP9 bench | B3 | APPROVED | worker sonnet (high, T3) | 2026-11-05 | V2X: DoS-family matched F1 0.992-0.996 (bar 0.93-0.998), all-19 macro-F1 0.917, FPR 1.0%; 2 pre-registered controls fail as written; reports/WP9_B3.md |
| WP9 bench | B4 | REVIEW | worker sonnet (high, T3) | 2026-11-05 | GPS: AV-GPS Case I F_full F1 0.976 [0.69,0.995] (bar 0.90-0.965, equal not better; label predictable from vehicle state, AUC 0.997), Case II fails, v3 layers F1 0.90 AUC at null q95; LiDAR: full model red-flagged, static supervised NAIVE-add TPR@10% FPR 0.426 (rule 0.85 NOT MET), v3.1 0.446; reports/WP9_B4.md |
| WP9 bench | B5 | TODO | | | final scoring + comparison |
