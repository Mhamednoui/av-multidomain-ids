# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S3 | APPROVED | worker sonnet | 2026-10-19 | M0 closed: v2 B2 reproduced exactly (19 tests) |
| WP1 GPS | S5 | IN PROGRESS | worker sonnet (medium) | 2026-10-20 | S4 APPROVED with misses. S6 must filter OSM to drivable classes |
| WP2 CAN | S1 | IN PROGRESS | worker sonnet (medium) | 2026-10-19 | S0 APPROVED (D11 7.47 GB, 62 duplicate files) |
| WP3 LiDAR | S1 | BLOCKED | - | 2026-10-20 | waits for M0 (S0 optional, later) |
| WP4 Network | S0 | BLOCKED | - | 2026-10-20 | waits for M0 |
| WP5 V2X | S1b | REVIEW | worker sonnet (medium) | 2026-10-20 | S1b PARTIAL: Tampa = 38 physical vehicles, 19,527 msgs; new split splits_tampa_v2.json; reruns done (heading_rate FA 2.7%). S3b still waits for receiver positions |
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
