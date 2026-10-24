# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S4 | APPROVED | worker sonnet | 2026-10-21 | combiner noisy_or log form (rank-equivalent, no saturation) |
| WP1 GPS | done (M1-GPS partial) | APPROVED | - | 2026-10-21 | M1-GPS closed PARTIAL, see reports/M1_GPS.md; frozen output gps/domain.py |
| WP2 CAN | done (M1-CAN partial) | APPROVED | - | 2026-10-22 | M1-CAN closed PARTIAL, see reports/M1_CAN.md; frozen output can/domain.py |
| WP3 LiDAR | S5 + S7 | IN PROGRESS (parallel) | 2 workers sonnet | 2026-10-24 | S6 APPROVED partial (PointDrop 87%); S5 occlusion and S7 learned layers in parallel |
| WP4 Network | done (M1-NET partial) | APPROVED | - | 2026-10-22 | M1-NET closed PARTIAL, see reports/M1_NET.md; frozen network/domain.py |
| WP5 V2X | done (M1-V2X partial + V2AIX addendum) | APPROVED | - | 2026-10-24 | S3b APPROVED partial: real-CAM FA 92-95% with VeReMi calibration, ~1% recalibrated |
| WP6 Cross-domain | S5b | TODO (after M1-LiDAR) | - | 2026-10-24 | S5 / M2 closed NOT MET (1 of 7 rules); addendum S5b after M1-LiDAR |
| WP7 System | S3 (early) + S2 later | REVIEW | worker sonnet (medium, T2) | 2026-10-24 | S3 run_all / make_report / README done (reports/WP7_S3.md); open sections PENDING; S2 simulation waits for M1-LiDAR + M2 addendum |

## Overall progress (orchestrator updates this at every approval)

**Overall: 52 / 59 steps approved = 88%** (updated 2026-10-24)

| WP | Steps counted | Approved | % |
|---|---|---|---|
| WP0 Foundation | S1-S4 (4) | 4 | 100 |
| WP1 GPS | S0-S8 (9) | 9 | 100 (M1-GPS partial) |
| WP2 CAN | S0-S7 (8) | 8 | 100 (M1-CAN partial) |
| WP3 LiDAR | S1-S7, S9 (8; S0, S8 optional) | 5 | 63 |
| WP4 Network | S0-S7 (8) | 8 | 100 (M1-NET partial) |
| WP5 V2X | S0, S0b, S0c, S1, S1b, S2-S6, S3b (11; S7 optional) | 11 | 100 (M1-V2X partial + V2AIX addendum) |
| WP6 Cross-domain | S1, S2, S2b, S3-S5, S5b (7) | 6 | 86 |
| WP7 System | S1-S4 (4) | 1 | 25 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | V2X, GPS, CAN, NET closed partial (2026-10-21/22); LiDAR open |
| M2 cross-domain + fusion | closed NOT MET 2026-10-24 (LiDAR interim); addendum S5b after M1-LiDAR |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
