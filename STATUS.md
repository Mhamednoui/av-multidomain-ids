# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S4 | APPROVED | worker sonnet | 2026-10-21 | combiner noisy_or log form (rank-equivalent, no saturation) |
| WP1 GPS | done (M1-GPS partial) | APPROVED | - | 2026-10-21 | M1-GPS closed PARTIAL, see reports/M1_GPS.md; frozen output gps/domain.py |
| WP2 CAN | done (M1-CAN partial) | APPROVED | - | 2026-10-22 | M1-CAN closed PARTIAL, see reports/M1_CAN.md; frozen output can/domain.py |
| WP3 LiDAR | S4 | IN PROGRESS | worker sonnet (medium, T2) | 2026-10-22 | S3 APPROVED (S2b confirmed add artefact) |
| WP4 Network | S7 | IN PROGRESS | worker sonnet (high, T3) | 2026-10-22 | S6 APPROVED (L4 optional supervised). S7 -> M1-NET |
| WP5 V2X | done (M1-V2X partial) | APPROVED | - | 2026-10-21 | M1-V2X closed PARTIAL, see reports/M1_V2X.md. Open: S3b acceptance range (needs receiver positions), V2AIX, null-control follow-up |
| WP6 Cross-domain | S2 | REVIEW | worker opus (medium, T4) | 2026-10-22 | S2 NOT MET (FA 4.4% KITTI / 5.4% comma, KITTI blame 49%); comma test exposed twice (bug fix, labelled); reports/WP6_S2.md |
| WP7 System | S1 | BLOCKED | - | 2026-10-20 | waits for M2 |

## Overall progress (orchestrator updates this at every approval)

**Overall: 41 / 55 steps approved = 75%** (updated 2026-10-22)

| WP | Steps counted | Approved | % |
|---|---|---|---|
| WP0 Foundation | S1-S4 (4) | 4 | 100 |
| WP1 GPS | S0-S8 (9) | 9 | 100 (M1-GPS partial) |
| WP2 CAN | S0-S7 (8) | 8 | 100 (M1-CAN partial) |
| WP3 LiDAR | S1-S7, S9 (8; S0, S8 optional) | 3 | 38 |
| WP4 Network | S0-S7 (8) | 7 | 88 |
| WP5 V2X | S0, S0b, S1, S1b, S2-S6 (9; S3b, S7 optional) | 9 | 100 (M1-V2X partial) |
| WP6 Cross-domain | S1-S5 (5) | 1 | 20 |
| WP7 System | S1-S4 (4) | 0 | 0 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | V2X, GPS, CAN closed partial (2026-10-21/22); LiDAR, NET open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
