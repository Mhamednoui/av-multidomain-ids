# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S3 | APPROVED | worker sonnet | 2026-10-19 | M0 closed: v2 B2 reproduced exactly (19 tests) |
| WP1 GPS | S7 | IN PROGRESS | worker sonnet (high, T3) | 2026-10-21 | S6 APPROVED (negative result: map layer out of default stack) |
| WP2 CAN | S3 | TODO | - | 2026-10-21 | S2 APPROVED with miss (ROAD FA 3.4% vs 1%) |
| WP3 LiDAR | S1 | BLOCKED | - | 2026-10-20 | waits for M0 (S0 optional, later) |
| WP4 Network | S0 | BLOCKED | - | 2026-10-20 | waits for M0 |
| WP5 V2X | S5 | IN PROGRESS | worker sonnet (high, T3) | 2026-10-21 | S4 APPROVED partial (kf_cusum_lo dropped from deployable L3) |
| WP6 Cross-domain | S1 | BLOCKED | - | 2026-10-20 | waits for WP1 S5 + domain milestones |
| WP7 System | S1 | BLOCKED | - | 2026-10-20 | waits for M2 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
