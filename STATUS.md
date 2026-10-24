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
| WP6 Cross-domain | S5b | REVIEW | worker opus (medium, T4) | 2026-10-25 | M2 addendum NOT MET (A4, A5, A7 met); system v2 frozen for WP7 S2; reports/WP6_S5b.md |
| WP7 System | S2 | TODO (waits for M1-LiDAR + M2 addendum) | - | 2026-10-24 | S1, S1b, S3 APPROVED; regenerate RESULTS_v3.md after every milestone |

## Overall progress (orchestrator updates this at every approval)

**Overall: 56 / 59 steps approved = 95%** (updated 2026-10-25)

| WP | Steps counted | Approved | % |
|---|---|---|---|
| WP0 Foundation | S1-S4 (4) | 4 | 100 |
| WP1 GPS | S0-S8 (9) | 9 | 100 (M1-GPS partial) |
| WP2 CAN | S0-S7 (8) | 8 | 100 (M1-CAN partial) |
| WP3 LiDAR | S1-S7, S9 (8; S0, S8 optional) | 8 | 100 (M1-LiDAR partial) |
| WP4 Network | S0-S7 (8) | 8 | 100 (M1-NET partial) |
| WP5 V2X | S0, S0b, S0c, S1, S1b, S2-S6, S3b (11; S7 optional) | 11 | 100 (M1-V2X partial + V2AIX addendum) |
| WP6 Cross-domain | S1, S2, S2b, S3-S5, S5b (7) | 6 | 86 |
| WP7 System | S1-S4 (4) | 2 | 50 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | ALL CLOSED PARTIAL (last: LiDAR 2026-10-25) |
| M2 cross-domain + fusion | closed NOT MET 2026-10-24 (LiDAR interim); addendum S5b after M1-LiDAR |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
