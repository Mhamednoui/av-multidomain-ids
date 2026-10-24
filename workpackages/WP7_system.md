# WP7 System, simulation, final evaluation

Goal: run the whole v3 system as streams, measure it end to end, and produce the final
results and documentation.

Owns: `system/`, `tests/system/`, `results/WP7/`, `notes/WP7_system.md`, `reports/WP7_*`,
`tools/WP7_*`, and (with the supervisor) `run_all.py`, `make_report.py`, `README.md`, `RESULTS_v3.md`.

## Steps
- S1 Streaming runtime: per-domain runners with all layers (stateful, reset per drive /
  capture), latency per sample and per domain (v2 reference: network ~1 ms, CAN ~0.05 ms per
  frame in windows, GPS ~0.8 ms, LiDAR ~23 ms per scan, fusion ~0.3 ms).
- S2 Simulation v3: all five domains as real streams (consecutive fixes, scans, frames,
  messages, flows), persistent attacks starting at block starts, coordinated multi-domain
  scenarios; first-alert delay per block; representative attack sampling (all test episodes,
  not a few random ones).
- S3 `run_all.py` (every step in order), `make_report.py` -> `RESULTS_v3.md` generated from
  JSON, README for v3, full test run.
- S4 Publication (only with the user's approval): local repo branch, then GitHub; paper tables.
- Milestones M3, M4.

## Progress
- 2026-10-22 S1 streaming runtime: REVIEW (reports/WP7_S1.md, notes/WP7_brief.md). Stream == batch exact on validation data in GPS, CAN, V2X, cross-domain, LiDAR (interim); network = placeholder until M1-NET.
- 2026-10-24 S3 (early) run_all.py, make_report.py -> RESULTS_v3.md, README.md: REVIEW (reports/WP7_S3.md). Sections of M1-LiDAR, M2 addendum, M3 simulation are PENDING and fill from results/WP3/S9/acceptance.json, results/WP6/s5b_acceptance.json, results/WP7/S2_acceptance.json. S2 and S4 not started.
