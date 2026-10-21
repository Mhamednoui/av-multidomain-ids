# STATUS board

States: `BLOCKED` (waits for another WP) · `TODO` (next step ready to assign) · `IN PROGRESS`
(a worker is on it) · `REVIEW` (worker finished; waits for the supervisor) · `APPROVED` ·
`CHANGES` (sent back with comments). A worker edits only its own row.

| WP | Step | State | Worker / session | Updated | Note |
|---|---|---|---|---|---|
| WP0 Foundation | S4 | APPROVED | worker sonnet | 2026-10-21 | combiner noisy_or log form (rank-equivalent, no saturation) |
| WP1 GPS | done (M1-GPS partial) | APPROVED | - | 2026-10-21 | M1-GPS closed PARTIAL, see reports/M1_GPS.md; frozen output gps/domain.py |
| WP2 CAN | S5 | IN PROGRESS | worker sonnet (high, T3) | 2026-10-22 | S4 APPROVED with miss (masquerade 4/5 caught, FA 38%) |
| WP3 LiDAR | S1 | IN PROGRESS | worker sonnet (medium, T2) | 2026-10-21 | data layer + ray-cast attack generator |
| WP4 Network | S3 | IN PROGRESS | worker sonnet (medium, T2) | 2026-10-22 | S2 APPROVED (A4 transfer miss; topology artefact flagged) |
| WP5 V2X | done (M1-V2X partial) | APPROVED | - | 2026-10-21 | M1-V2X closed PARTIAL, see reports/M1_V2X.md. Open: S3b acceptance range (needs receiver positions), V2AIX, null-control follow-up |
| WP6 Cross-domain | S1 | BLOCKED | - | 2026-10-20 | waits for WP1 S5 + domain milestones |
| WP7 System | S1 | BLOCKED | - | 2026-10-20 | waits for M2 |

## Milestones

| Id | State |
|---|---|
| M0 foundation | closed 2026-10-19 |
| M1 GPS / CAN / LiDAR / NET / V2X | V2X closed partial 2026-10-21; GPS closed partial 2026-10-21; others open |
| M2 cross-domain + fusion | open |
| M3 system | open |
| M4 publication | open (needs the user's approval) |

## Supervisor decisions

Logged in `notes/ORCHESTRATOR.md` (assignments, approvals, changes requested, user decisions).
