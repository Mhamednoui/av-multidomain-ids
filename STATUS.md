# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S3 | REVIEW | worker sonnet | 2026-10-19 | B2 reproduced exactly (alarm level); threshold differs 0.0009 m by interpolation |
| WP1 GPS | S0 | REVIEW | worker sonnet | 2026-10-19 | download only, started before M0 (orchestrator) |
| WP2 CAN | S0 | IN PROGRESS | worker sonnet | 2026-10-19 | download only, started before M0 (orchestrator) |
| WP3 LiDAR | S1 | BLOCKED | - | 2026-10-20 | waits for M0 (S0 optional, later) |
| WP4 Network | S0 | BLOCKED | - | 2026-10-20 | waits for M0 |
| WP5 V2X | S0 | BLOCKED | - | 2026-10-20 | waits for M0 |
| WP6 Cross-domain | S1 | BLOCKED | - | 2026-10-20 | waits for WP1 S5 + domain milestones |
| WP7 System | S1 | BLOCKED | - | 2026-10-20 | waits for M2 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | open |
| M1 GPS / CAN / LiDAR / NET / V2X | open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
