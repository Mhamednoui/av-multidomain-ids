# REQUEST (WP7 -> supervisor): incremental entry points in the frozen domains (OPTIONAL, not blocking S1)

Raised by: WP7 S1 (streaming runtime), 2026-10-22. Nothing is blocked: S1 is delivered without any change outside `system/`.

## What S1 found
The frozen detectors are causal, but they are whole-run / whole-capture vectorised programs without a per-sample `step()`:

| Domain | Frozen entry point | What the runner does instead |
|---|---|---|
| GPS | `GPSDomain.score(df)` (EKF, CUSUMs, dead reckoning are per-run loops) | re-scores the prefix of the run per fix, takes the last row |
| CAN | `CanDomain.score_capture(t, ids, dlc, B)` (0.05 s grids, ridge predictors, windowed CUSUM) | re-scores the prefix once per completed 1 s window |
| V2X | no domain object; layers `v2x/l1,l2,l3` + `v2x.l4.message_scores` on whole tables | builds a bounded context table per message (own track + last second of traffic + births of the last 10 s) |
| Cross | `WhichDomainLies.evidence(t, Z)` | true per-step (statistic state carried): no change needed |
| LiDAR interim | per-scan already | no change needed |

Stream == batch holds exactly on all validation data tested (results/WP7/S1_*.json), so correctness is not the issue. The cost is latency that grows with the length of the run /
capture / track so far (see the "by context size" tables in results/WP7/S1_report_tables.md). For the final system (S2 simulation with long streams, S3 end-to-end timing)
an incremental implementation would make the per-sample cost constant.

## What would help (each owner decides; none is needed for correctness)
1. GPS (WP1): `GPSDomain.step(row, state) -> (Evidence, state)` where state holds the EKF (x, P, hold), the DR branch, the CUSUM statistics and the last rows needed by B2 / L1 (a handful of past fixes).
   The batch `score` would stay the reference; a test would assert step == score row by row (the same test WP7 S1 already runs from outside).
2. CAN (WP2): `CanDomain.step(frame, state)` keeping the decoded sample-and-hold values, the lag buffers of L3c (a few seconds) and the CUSUM window; windows are emitted when a second passes.
3. V2X (WP5): a saved physics-only domain object (`V2XPhysicsDomain` in `system/v2x_runner.py` is a WP7 re-creation of the S6 recipe; it reproduces the S6 layer thresholds to 0.0 and the S6
   validation false-alarm rate 0.009967 exactly, results/WP7/S1_v2x_fit.json) and per-track `Tracker.step()`.
   Also: `v2x.l3.birth_density` counts births with EQUAL timestamp that appear later in the table, which a causal stream cannot know (0 equal timestamps in VeReMi validation; Tampa not checked).

## Decision asked
Not needed now. If the supervisor wants S2 / S3 to measure realistic per-sample latency on long streams, assign the incremental entry points to the domain owners (small T2 steps),
or accept the prefix re-scoring numbers of S1 as an upper bound.
