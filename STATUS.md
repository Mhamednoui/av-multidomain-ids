# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S3 | APPROVED | worker sonnet | 2026-10-19 | M0 closed: v2 B2 reproduced exactly (19 tests) |
| WP1 GPS | S8 | IN PROGRESS | worker sonnet (high, T3) | 2026-10-21 | S7 APPROVED (negative: learned layers add nothing). S8 -> M1-GPS |
| WP2 CAN | S3 | REVIEW | worker sonnet (medium, T2) | 2026-10-21 | S3 NOT MET: clock skew does not catch ROAD masquerade (negative result, reports/WP2_S3.md) |
| WP3 LiDAR | S1 | BLOCKED | - | 2026-10-20 | waits for M0 (S0 optional, later) |
| WP4 Network | S0 | IN PROGRESS | worker haiku (medium, T1) | 2026-10-21 | downloads D10 + D23 (size-checked) |
| WP5 V2X | done (M1-V2X partial) | APPROVED | - | 2026-10-21 | M1-V2X closed PARTIAL, see reports/M1_V2X.md. Open: S3b acceptance range (needs receiver positions), V2AIX, null-control follow-up |
| WP6 Cross-domain | S1 | BLOCKED | - | 2026-10-20 | waits for WP1 S5 + domain milestones |
| WP7 System | S1 | BLOCKED | - | 2026-10-20 | waits for M2 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | V2X closed partial 2026-10-21; others open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
