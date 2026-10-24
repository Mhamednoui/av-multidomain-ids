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
| WP4 Network | done (M1-NET partial) | APPROVED | - | 2026-10-22 | M1-NET closed PARTIAL, see reports/M1_NET.md; frozen network/domain.py |
| WP5 V2X | S3b | IN PROGRESS | worker sonnet (medium, T2) | 2026-10-24 | S0c APPROVED (V2AIX 212k CAMs, ego pose as receiver) |
| WP6 Cross-domain | S5 | REVIEW | worker opus (medium, T4) | 2026-10-24 | M2 (LiDAR interim) NOT MET: FA K 2.08% / C 6.70%, 25 / 31 events per clean h, K det 60%; M2 frozen; see reports/M2.md |
| WP7 System | S2 | TODO (waits for M1-LiDAR + M2) | - | 2026-10-24 | S1 + S1b APPROVED |

## Overall progress (orchestrator updates this at every approval)

**Overall: 48 / 58 steps approved = 83%** (updated 2026-10-24)

| WP | Steps counted | Approved | % |
|---|---|---|---|
| WP0 Foundation | S1-S4 (4) | 4 | 100 |
| WP1 GPS | S0-S8 (9) | 9 | 100 (M1-GPS partial) |
| WP2 CAN | S0-S7 (8) | 8 | 100 (M1-CAN partial) |
| WP3 LiDAR | S1-S7, S9 (8; S0, S8 optional) | 3 | 38 |
| WP4 Network | S0-S7 (8) | 8 | 100 (M1-NET partial) |
| WP5 V2X | S0, S0b, S0c, S1, S1b, S2-S6, S3b (11; S7 optional) | 10 | 91 |
| WP6 Cross-domain | S1, S2, S2b, S3-S5 (6) | 5 | 83 |
| WP7 System | S1-S4 (4) | 1 | 25 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | V2X, GPS, CAN, NET closed partial (2026-10-21/22); LiDAR open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
