# WP6 Cross-domain, fusion, zero-day, correlator

Goal: use the fact that several domains observe the same physical reality (the vehicle's
motion) to find which domain is lying, and fuse all domains into one explained alert at a fixed
false-alarm budget.

Owns: `crossdomain/`, `fusion/`, `tests/crossdomain/`, `tests/fusion/`, `results/WP6/`,
`notes/WP6_crossdomain.md`, `reports/WP6_*`, `tools/WP6_*`.
Inputs: MotionEstimate and combined Evidence from WP1-WP5; KITTI (GPS/IMU + LiDAR on the same
car); CAN wheel speed simulated from OXTS + noise, or D22 comma2k19 (real CAN + GNSS) if approved.

## Baseline (v2, `../codes_v2/results/fusion.json`, `simulation.json`)
Fusion meta at a 2% validation budget: test 95.23% acc, 1.06% FA. Zero-day on detector outputs:
2.4% FA, unseen Bot 5.3%. Simulation: 91.67% acc, 1.90% FA, phantom block 8.3%.

## Steps
- S1 Motion witnesses: collect MotionEstimate from GPS/IMU (WP1), LiDAR odometry (WP1 S5),
  CAN wheel speed (simulated or comma2k19), V2X self-reports (WP5); time alignment.
- S2 "Which domain lies": pairwise consistency + majority logic; evaluation with single-domain
  attacks injected on KITTI streams (GPS spoof, LiDAR odometry corruption, CAN speed spoof).
- S3 Fusion v3 over 5 domains + cross-domain Evidence: calibrated combination, 2% system
  budget, group-aware validation halves, tie-safe thresholds, explanation of every alert.
- S4 Zero-day v3: per-domain L3 layers on raw data + novelty on evidence vectors; v2
  unseen-attack protocol (remove attack types from training).
- S5 Temporal correlator + response module wired (copy from v2; retire `windowing/`).
- Milestone M2 report.

## Progress
(worker updates this section)
- 2026-10-22 S1 motion witnesses: REVIEW. A1/A2/A4/A5 met, A3 (sigma honesty on val) NOT MET, A6 ROAD unit plausible; report reports/WP6_S1.md.
- 2026-10-22 S2 which domain lies: REVIEW. NOT MET (FA 4.4% KITTI / 5.4% comma; KITTI blame 49%); comma blame 97%; coordinated gps_can caught 81% vs GPS domain 50%; report reports/WP6_S2.md.
- 2026-10-22 S2 APPROVED with misses. S2b (validation only) REVIEW: PARTIAL; held-out FA KITTI 1.24% / comma 1.10% (inst |z| chosen), detection 57.5% / 88.1%, wrong blame 3.4% / 1.4%; report reports/WP6_S2b.md.
- 2026-10-24 S3 fusion over 5 domains (LiDAR interim): REVIEW. PARTIAL: test FA tick K 6.36% / C 6.31% (NOT MET, rule 3%), mean det K 82.5%, cross gain +25 pts, 100% alarms explained, G5 not met; report reports/WP6_S3.md.
